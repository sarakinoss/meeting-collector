# app/db/crud.py
from __future__ import annotations
from typing import Iterable, Optional
from datetime import datetime
from dateutil import parser as dateparser

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Meeting, Email, MeetingEmail
from sqlalchemy import select, func

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s: return None
    try:
        return dateparser.parse(s)
    except Exception:
        return None

def store_meetings_to_db(meeting_list: Iterable[dict], db: Session | None = None) -> None:
    """
    Upsert meetings into the SQLAlchemy Meeting table.
    Compatible with the old call site that passed a list of dicts coming from the parser.
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        for m in meeting_list:
            uid = m.get("meet_id") or (m.get("meet_link") or "").strip() or None
            if not uid:
                # skip rows without any stable id/link
                continue

            # find existing by uid
            row = db.execute(select(Meeting).where(Meeting.uid == uid)).scalar_one_or_none()
            if row is None:
                row = Meeting(uid=uid)
                db.add(row)

            # map fields
            row.platform   = m.get("meet_platform")
            row.title      = m.get("msg_subject") or m.get("title")
            row.link       = m.get("meet_link")
            row.start      = _parse_dt(m.get("meet_date"))
            row.end        = _parse_dt(m.get("meet_end_date"))
            row.organizer  = m.get("msg_sender")
            row.attendees  = m.get("meet_attendants") or m.get("msg_attendants")
            row.parse_reason  = m.get("parse_reason")
            row.parse_snippet = m.get("parse_snippet")
            row.last_msg_datetime = _parse_dt(m.get("msg_date"))

        db.commit()
    finally:
        if own_session:
            db.close()


# def store_meetings_to_db(meeting_list: Iterable[dict], db: Session | None = None) -> None:
#     """
#     Upsert meetings in the Meeting table και δέσε τα σχετικά emails (MeetingEmail).
#     Δουλεύει με την ίδια λίστα dicts από τον parser.
#     """
#     own_session = False
#     if db is None:
#         db = SessionLocal()
#         own_session = True
#
#     try:
#         for m in meeting_list:
#             uid = m.get("meet_id") or (m.get("meet_link") or "").strip() or None
#             if not uid:
#                 continue
#
#             # find/create meeting
#             row = db.execute(select(Meeting).where(Meeting.uid == uid)).scalar_one_or_none()
#             if row is None:
#                 row = Meeting(uid=uid)
#                 db.add(row)
#
#             # map πεδία meeting
#             row.platform   = m.get("meet_platform")
#             row.title      = m.get("msg_subject") or m.get("title")
#             row.link       = m.get("meet_link")
#             row.start      = _parse_dt(m.get("meet_date"))
#             row.end        = _parse_dt(m.get("meet_end_date"))
#             row.organizer  = m.get("msg_sender")
#             row.attendees  = m.get("meet_attendants") or m.get("msg_attendants")
#             row.parse_reason  = m.get("parse_reason")
#             row.parse_snippet = m.get("parse_snippet")
#             row.last_msg_datetime = _parse_dt(m.get("msg_date"))
#
#             # βεβαιώσου ότι υπάρχει row.id πριν φτιάξουμε σχέσεις
#             db.flush()
#
#             # δέσιμο σχετικών emails (από msg_id ή related_messages)
#             related = m.get("related_messages")
#             if not related:
#                 mid = m.get("msg_id")
#                 related = [mid] if mid else []
#
#             for message_id in related:
#                 if not message_id:
#                     continue
#                 em = db.execute(select(Email).where(Email.message_id == message_id)).scalar_one_or_none()
#                 if not em:
#                     continue
#                 exists = db.execute(
#                     select(MeetingEmail).where(
#                         MeetingEmail.meeting_id == row.id,
#                         MeetingEmail.email_id == em.id,
#                     )
#                 ).first()
#                 if not exists:
#                     db.add(MeetingEmail(meeting_id=row.id, email_id=em.id, role=None))
#
#         db.commit()
#     finally:
#         if own_session:
#             db.close()


# def get_all_meetings_as_dict(db: Session | None = None) -> list[dict]:
#     """
#     Returns meetings in the exact shape your UI expects (old helper compatibility).
#     """
#     own_session = False
#     if db is None:
#         db = SessionLocal()
#         own_session = True
#     try:
#         rows = db.execute(select(Meeting).order_by(Meeting.start.is_(None), Meeting.start.desc())).scalars().all()
#         out = []
#         for r in rows:
#             out.append({
#                 "meet_id": r.uid or str(r.id),
#                 "meet_platform": r.platform,
#                 "meet_link": r.link,
#                 "meet_date": r.start.isoformat() if r.start else None,
#                 "meet_end_date": r.end.isoformat() if r.end else None,
#                 "msg_subject": r.title,
#                 "msg_sender": r.organizer,
#                 "msg_attendants": r.attendees,
#                 "msg_account": None,   # fill once we join Email table
#                 "msg_folder": None,
#                 "msg_id": None,
#                 "msg_date": r.last_msg_datetime.isoformat() if r.last_msg_datetime else None,
#             })
#         return out
#     finally:
#         if own_session:
#             db.close()
def get_all_meetings_as_dict(db: Session | None = None) -> list[dict]:
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        rows = db.execute(
            select(Meeting).order_by(Meeting.start.is_(None), Meeting.start.desc())
        ).scalars().all()

        out: list[dict] = []
        for r in rows:
            # Ο parser κρατά το τελευταίο email -> αναμένουμε 1 σύνδεση
            em = (
                db.query(Email)
                .join(MeetingEmail, MeetingEmail.email_id == Email.id)
                .filter(MeetingEmail.meeting_id == r.id)
                .first()
            )

            out.append({
                "msg_account": em.account if em else None,
                "msg_folder": em.folder if em else None,
                "msg_id": em.message_id if em else None,
                "msg_date": r.last_msg_datetime.isoformat() if r.last_msg_datetime else None,
                "msg_subject": r.title,
                "msg_sender": r.organizer,
                "msg_attendants": r.attendees,

                "meet_platform": r.platform,
                "meet_id": r.uid or str(r.id),
                "meet_attendants": r.attendees,   # ο parser το δίνει χωριστά
                "meet_date": r.start.isoformat() if r.start else None,
                "meet_link": r.link,

                "related_messages": [em.message_id] if em and em.message_id else [],
            })
        return out
    finally:
        if own_session:
            db.close()


