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
from ..services.jobs import jobs
from ..services.positions import add_points

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_BYTES = 300 * 1024 * 1024   # Google Takeout files of a decade reach ~200 MB


@router.post("")
async def upload(tracker_id: int = Form(...), file: UploadFile = File(...), format: str | None = Form(None),
                 db: Session = Depends(get_db), user: User = Depends(require_editor)):
    tracker = tracker_for(db, user, tracker_id)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large")
    fmt = format or detect_format(file.filename or "", data)
    if fmt not in IMPORTERS:
        raise HTTPException(400, "Unknown file format — supported: GPX, Google location history (JSON), GeoJSON")
    job = ImportJob(user_id=user.id, tracker_id=tracker.id, kind=fmt, filename=(file.filename or "")[:300], status="running")
    db.add(job)
    db.commit()
    try:
        points = await run_in_threadpool(IMPORTERS[fmt], data)
        added = await run_in_threadpool(add_points, db, tracker, points, fmt)
    except Exception as e:  # noqa: BLE001 — any parser error is the file's fault, report it
        job.status, job.message = "failed", f"Could not read the file: {e}"[:500]
        db.commit()
        raise HTTPException(400, job.message)
    job.status, job.added, job.skipped = "done", added, len(points) - added
    db.commit()
    jobs.trigger()
    return {"id": job.id, "format": fmt, "points": len(points), "added": added, "skipped": len(points) - added}


@router.get("")
def history(db: Session = Depends(get_db), user: User = Depends(require_editor)):
    ids = [t.id for t in visible_trackers(db, user)]
    rows = db.scalars(select(ImportJob).where(ImportJob.tracker_id.in_(ids)).order_by(ImportJob.created_at.desc()).limit(50))
    return [{"id": j.id, "tracker_id": j.tracker_id, "kind": j.kind, "filename": j.filename, "status": j.status,
             "added": j.added, "skipped": j.skipped, "message": j.message, "created_at": j.created_at} for j in rows]
