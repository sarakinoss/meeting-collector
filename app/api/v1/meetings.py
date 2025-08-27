# app/api/v1/meetings.py
from __future__ import annotations
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.db.session import get_db
from app.db.models import JobState, Meeting, Email, MeetingEmail
from app.db.crud import get_all_meetings_as_dict, store_meetings_to_db
from email_parser import extract_meetings_all_accounts

router = APIRouter(prefix="/api/v1/meetings", tags=["Meetings"])

# ---------- STATUS ----------
@router.get("/status")
def get_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    js = db.query(JobState).first()
    total_meetings = db.execute(select(func.count(Meeting.id))).scalar() or 0
    status_val = getattr(js.status, "value", js.status) if js else "idle"
    return {
        "collector": {
            "status": status_val,
            "message": js.message if js else None,
            "progress": js.progress if js else 0,
            "last_run": js.last_run.isoformat() if js and js.last_run else None,
            "updated_at": js.updated_at.isoformat() if js else None,
        },
        "counts": {"meetings": total_meetings},
    }

# ---------- ACTIONS ----------
@router.post("/actions/parse")
def trigger_parse(force_full: bool = False, user=Depends(require_user)):
    """
    Ξεκινά άμεσα parsing όλων των ενεργών accounts.
    Αν force_full=True, αγνοεί τα incremental timestamps.
    Τρέχει σε background thread και ΑΠΟΘΗΚΕΥΕΙ στο DB.
    """
    def _job():
        meetings = extract_meetings_all_accounts(force_full=force_full)
        store_meetings_to_db(meetings)
    threading.Thread(target=_job, daemon=True).start()
    return {"status": "parse_triggered", "force_full": bool(force_full)}

# ---------- HELPERS (latest related email per meeting) ----------
def _latest_email_for_meeting(db: Session, meeting_id: int) -> Optional[Email]:
    q = (
        db.query(Email)
        .join(MeetingEmail, MeetingEmail.email_id == Email.id)
        .filter(MeetingEmail.meeting_id == meeting_id)
        .order_by(
            Email.received_at.desc().nullslast(),
            Email.internaldate.desc().nullslast(),
            Email.id.desc()
        )
    )
    return q.first()

def _meeting_to_ui(db: Session, m: Meeting) -> Dict[str, Optional[str | int]]:
    em = _latest_email_for_meeting(db, m.id)
    return {
        "meet_id": m.uid or str(m.id),
        "meet_platform": m.platform,
        "meet_link": m.link,
        "meet_date": m.start.isoformat() if m.start else None,
        "meet_end_date": m.end.isoformat() if m.end else None,
        "msg_subject": m.title,
        "msg_sender": m.organizer,
        "msg_attendants": m.attendees,
        "msg_account": em.account if em else None,
        "msg_folder": em.folder if em else None,
        "email_id": em.id if em else None,
        "message_id": em.message_id if em else None,
        "received_at": em.received_at.isoformat() if em and em.received_at else None,
        "internaldate": em.internaldate.isoformat() if em and em.internaldate else None,
    }

# ---------- LISTS ----------
@router.get("")
def list_meetings_legacy_shape(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """ Σχήμα όπως το περίμενε ήδη το UI (χρησιμοποιεί τον helper στο crud). """
    return get_all_meetings_as_dict(db)

@router.get("/db")
def list_meetings_db_view(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = db.execute(select(Meeting)).scalars().all()
    return [_meeting_to_ui(db, m) for m in rows]
