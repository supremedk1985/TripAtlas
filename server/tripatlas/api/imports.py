"""Import positions from files (GPX, Google location history, GeoJSON) into a tracker — uploaded by hand, or sent by
an app after every recording (`/push`, with the tracker's import key instead of a sign-in)."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.deps import require_editor, tracker_for, visible_trackers
from ..auth.security import import_key_hash, push_throttle
from ..db.models import ImportJob, Tracker, User
from ..db.session import get_db
from ..importers import IMPORTERS, detect_format
from ..importers.gpx import iter_gpx
from ..services.jobs import jobs
from ..services.positions import IMPORT_SAME_POINT_S, add_points_counted, thin
from .schemas import iso_utc

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_BYTES = 300 * 1024 * 1024  # Google Takeout files of a decade reach ~200 MB (read into memory)
MAX_GPX_BYTES = 2 * 1024 * 1024 * 1024  # GPX is read as a stream: a bike app's export of every ride is big


@router.post("")
async def upload(
    tracker_id: int = Form(...),
    file: UploadFile = File(...),
    format: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    tracker = tracker_for(db, user, tracker_id)
    head = await file.read(4096)
    await file.seek(0)
    fmt = format or detect_format(file.filename or "", head)
    size = file.size if file.size is not None else 0
    if size > (MAX_GPX_BYTES if fmt == "gpx" else MAX_BYTES):
        raise HTTPException(413, "File too large")
    if fmt not in IMPORTERS:
        raise HTTPException(400, "Unknown file format — supported: GPX, Google location history (JSON), GeoJSON")
    if fmt != "gpx":
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "File too large")
    return await _run(db, tracker, fmt, file.filename or "", user.id, file.file if fmt == "gpx" else data)


# One recording at a time: a ride, a day. Larger files go through the upload above.
MAX_PUSH_BYTES = 100 * 1024 * 1024


@router.post("/push")
async def push(request: Request, name: str = "", format: str | None = None, db: Session = Depends(get_db)):
    """An app sends one recording: `Authorization: Bearer <import key of the tracker>`, the file as the request body
    (GPX, GeoJSON or Google JSON; `?name=ride.gpx` or `?format=gpx` if the type is not obvious). Positions that are
    already there are skipped, so sending the same ride twice does no harm."""
    ip = request.client.host if request.client else "?"
    if push_throttle.blocked(f"ip:{ip}"):
        raise HTTPException(429, "Too many wrong keys — try again in 15 minutes")
    auth = request.headers.get("authorization", "")
    key = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    tracker = db.scalar(select(Tracker).where(Tracker.import_key_hash == import_key_hash(key))) if key else None
    if tracker is None:
        push_throttle.failed(f"ip:{ip}")
        raise HTTPException(401, "Unknown import key")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_PUSH_BYTES:
            raise HTTPException(413, "File too large")
    if not data:
        raise HTTPException(400, "Empty file")
    ctype = request.headers.get("content-type", "")
    fmt = format or ("gpx" if "gpx" in ctype else None) or detect_format(name or "upload", bytes(data[:4096]))
    if fmt is None and b"<gpx" in data[:4096]:
        fmt = "gpx"  # GPX sent without a name or type
    if fmt not in IMPORTERS:
        raise HTTPException(400, "Unknown file format — supported: GPX, Google location history (JSON), GeoJSON")
    return await _run(db, tracker, fmt, name or f"push.{fmt}", None, io.BytesIO(data) if fmt == "gpx" else bytes(data))


async def _run(db: Session, tracker: Tracker, fmt: str, filename: str, user_id: int | None, data) -> dict:
    """Read the file into the tracker; GPX `data` is a file object read point by point, the others bytes."""
    job = ImportJob(user_id=user_id, tracker_id=tracker.id, kind=fmt, filename=filename[:300], status="running")
    db.add(job)
    db.commit()
    try:
        source = iter_gpx(data) if fmt == "gpx" else iter(IMPORTERS[fmt](data))
        read = 0

        def counted(points):
            nonlocal read
            for p in points:
                read += 1
                yield p

        added, kept = await run_in_threadpool(
            add_points_counted, db, tracker, thin(counted(source)), fmt, 2000, IMPORT_SAME_POINT_S
        )
    except Exception as e:  # any parser error is the file's fault — report it
        db.rollback()  # nothing of a broken file stays: the batches written so far are undone
        job = db.get(ImportJob, job.id)
        job.status, job.message = "failed", f"Could not read the file: {e}"[:500]
        db.commit()
        raise HTTPException(400, job.message) from e
    job.status, job.added, job.skipped = "done", added, kept - added
    db.commit()
    jobs.trigger()
    # points = read from the file; kept = after thinning to one per 10 s; skipped = already there (duplicates)
    return {"id": job.id, "format": fmt, "points": read, "kept": kept, "added": added, "skipped": kept - added}


@router.get("")
def history(db: Session = Depends(get_db), user: User = Depends(require_editor)):
    ids = [t.id for t in visible_trackers(db, user)]
    rows = db.scalars(
        select(ImportJob).where(ImportJob.tracker_id.in_(ids)).order_by(ImportJob.created_at.desc()).limit(50)
    )
    return [
        {
            "id": j.id,
            "tracker_id": j.tracker_id,
            "kind": j.kind,
            "filename": j.filename,
            "status": j.status,
            "added": j.added,
            "skipped": j.skipped,
            "message": j.message,
            "created_at": iso_utc(j.created_at),
        }
        for j in rows
    ]
