"""Sticky notes on the map ("our first campsite"), usually made on a photo stack. Everyone sees them; children
cannot add, change or remove any."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.deps import current_user, require_editor
from ..db.models import MapNote, Role, User
from ..db.session import get_db

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    text: str = Field(min_length=1, max_length=500)
    photo_id: str | None = Field(None, pattern=r"^[0-9a-f-]{36}$")


class NoteUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def note_out(n: MapNote, db: Session) -> dict:
    author = db.get(User, n.created_by) if n.created_by else None
    return {
        "id": n.id,
        "lat": n.lat,
        "lon": n.lon,
        "text": n.text,
        "photo_id": n.photo_id,
        "created_at": n.created_at.isoformat(),
        "author": author.display_name if author else None,
        "created_by": n.created_by,
    }


@router.get("")
def list_notes(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [note_out(n, db) for n in db.scalars(select(MapNote).order_by(MapNote.created_at))]


@router.post("", status_code=201)
def create_note(body: NoteIn, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    n = MapNote(lat=body.lat, lon=body.lon, text=body.text.strip(), photo_id=body.photo_id, created_by=user.id)
    db.add(n)
    db.commit()
    return note_out(n, db)


def _note(db: Session, note_id: int) -> MapNote:
    n = db.get(MapNote, note_id)
    if n is None:
        raise HTTPException(404, "Note not found")
    return n


def _own(n: MapNote, user: User) -> None:
    if n.created_by != user.id and user.role != Role.admin:
        raise HTTPException(403, "Only its author or an administrator can change this note")


@router.patch("/{note_id}")
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    n = _note(db, note_id)
    _own(n, user)
    n.text = body.text.strip()
    db.commit()
    return note_out(n, db)


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    n = _note(db, note_id)
    _own(n, user)
    db.delete(n)
    db.commit()
