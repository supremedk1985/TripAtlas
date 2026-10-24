"""Import positions from files (GPX, Google location history, GeoJSON) into a tracker."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.deps import require_editor, tracker_for, visible_trackers
from ..db.models import ImportJob, User
from ..db.session import get_db
from ..importers import IMPORTERS, detect_format
from ..importers.gpx import iter_gpx
from ..services.jobs import jobs
from ..services.positions import add_points_counted, thin
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
    job = ImportJob(
        user_id=user.id, tracker_id=tracker.id, kind=fmt, filename=(file.filename or "")[:300], status="running"
    )
    db.add(job)
    db.commit()
    try:
        if fmt == "gpx":
            source = iter_gpx(file.file)   # straight from the uploaded file, point by point
        else:
            data = await file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, "File too large")
            source = iter(IMPORTERS[fmt](data))
        read = 0

        def counted(points):
            nonlocal read
            for p in points:
                read += 1
                yield p

        added, kept = await run_in_threadpool(add_points_counted, db, tracker, thin(counted(source)), fmt)
    except Exception as e:  # any parser error is the file's fault — report it
        db.rollback()   # nothing of a broken file stays: the batches written so far are undone
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
