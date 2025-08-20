# app/api/endpoints.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import email as pyemail
import email.policy
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
#from sqlalchemy import select, Session
from sqlalchemy import select, func

from pydantic import BaseModel, Field, EmailStr

from email_parser import extract_meetings_all_accounts
from app.db.session import get_db
from app.db.models import JobState, Meeting, Email, MeetingEmail, MailAccount, User
from app.db.crud import get_all_meetings_as_dict, store_meetings_to_db
from app.schemas.accounts import AccountIn, AccountOut
from app.api.deps import require_user, get_current_user
from app.core.crypto import encrypt, decrypt


# ---------- Templates για το "/" ----------
BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

# Apply auth dependency to all routes in this router EXCEPT root pages that we manually allow
router = APIRouter()

# ---------- ROOT (requires auth) ----------
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

# ---------- Accounts UI (requires auth) ----------
@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(
    select(MailAccount).where(MailAccount.owner == str(user.id)).order_by(MailAccount.id.desc())
    ).scalars().all()
    return templates.TemplateResponse("accounts.html", {"request": request, "accounts": rows})

# ---------- Accounts API (per-user) ----------
@router.get("/api/accounts")
async def list_accounts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(MailAccount).where(MailAccount.owner == str(user.id)).order_by(MailAccount.id.desc())).scalars().all()
    def mask(_): return "••••••" if _ else None
    return [{
        "id": r.id,
        "display_name": r.display_name,
        "email": r.email,
        "smtp_host": r.smtp_host, "smtp_port": r.smtp_port, "smtp_ssl": r.smtp_ssl,
        "smtp_user": r.smtp_user, "smtp_password": mask(r.smtp_password_enc),
        "imap_host": r.imap_host, "imap_port": r.imap_port, "imap_ssl": r.imap_ssl,
        "imap_user": r.imap_user, "imap_password": mask(r.imap_password_enc),
        "enabled": r.enabled
    } for r in rows]


@router.post("/accounts", status_code=201)
async def create_account(payload: AccountIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    # same email allowed across users; uniqueness only per owner here
    exists = db.execute(
        select(MailAccount).where(MailAccount.owner == str(user.id), MailAccount.email == payload.email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists for this user")

    row = MailAccount(
        display_name=payload.display_name,
        email=payload.email,
        smtp_host=payload.smtp_host, smtp_port=payload.smtp_port, smtp_ssl=payload.smtp_ssl,
        smtp_user=payload.smtp_user, smtp_password_enc=encrypt(payload.smtp_password) if payload.smtp_password else None,
        imap_host=payload.imap_host, imap_port=payload.imap_port, imap_ssl=payload.imap_ssl,
        imap_user=payload.imap_user, imap_password_enc=encrypt(payload.imap_password) if payload.imap_password else None,
        enabled=True,
        owner=str(user.id),
    )
    db.add(row); db.commit()
    return {"id": row.id}

@router.delete("/api/accounts/{account_id}", status_code=204)
async def delete_account(account_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = db.get(MailAccount, account_id)
    if not row or row.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row); db.commit()
    return

# @router.post("/full-parse", status_code=202)
# def run_full_parse():
#     # Τρέχει σε background thread για να μη μπλοκάρει το UI
#     def _job():
#         meetings = extract_meetings_all_accounts(force_full=True)
#         store_meetings_to_db(meetings)
#     threading.Thread(target=_job, daemon=True).start()
#     return {"status": "full_parse_triggered"}

@router.post("/full-parse")
async def trigger_full_parse(user = Depends(require_user)):
    # τρέχει ασύγχρονα για να μη μπλοκάρει το request
    threading.Thread(target=extract_meetings_all_accounts, daemon=True).start()
    return {"status": "full_parse_triggered"}

# ============================
# ========== STATUS ==========
# ============================
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

# ==============================
# ========== MEETINGS ==========
# ==============================

# ---------- helper: pick latest related email per meeting ----------
def _latest_email_for_meeting(db: Session, meeting_id: int) -> Optional[Email]:
    # join meeting_emails -> emails και πάρε το πιο πρόσφατο (received_at ή internaldate)
    q = (
        db.query(Email)
        .join(MeetingEmail, MeetingEmail.email_id == Email.id)
        .filter(MeetingEmail.meeting_id == meeting_id)
        .order_by(Email.received_at.desc().nullslast(), Email.internaldate.desc().nullslast(), Email.id.desc())
    )
    return q.first()

# ---------- MEETINGS ----------
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
        "email_id": em.id if em else None,                 # ← για UI buttons
        "message_id": em.message_id if em else None,       # χρήσιμο για debug
        "received_at": em.received_at.isoformat() if em and em.received_at else None,
        "internaldate": em.internaldate.isoformat() if em and em.internaldate else None,
    }
# def _meeting_to_ui(m: Meeting) -> Dict[str, Optional[str]]:
#     return {
#         "meet_id": m.uid or str(m.id),
#         "meet_platform": m.platform,
#         "meet_link": m.link,
#         "meet_date": m.start.isoformat() if m.start else None,
#         "meet_end_date": m.end.isoformat() if m.end else None,
#         "msg_subject": m.title,
#         "msg_sender": m.organizer,
#         "msg_attendants": m.attendees,
#         "msg_account": None,   # θα συμπληρωθούν όταν γίνει join με Email
#         "msg_folder": None,
#     }

@router.get("/meetings")
def list_meetings():
    return get_all_meetings_as_dict()

@router.get("/meetings-db")
def list_meetings(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = db.execute(select(Meeting)).scalars().all()
    return [_meeting_to_ui(db, m) for m in rows]

# def list_meetings(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
#     rows = db.execute(select(Meeting)).scalars().all()
#     return [_meeting_to_ui(m) for m in rows]

# ================================================
# ========== EMAILS: download & preview ==========
#=================================================
# def _safe_file_response(path: str) -> FileResponse:
#     # Aπλή προφύλαξη: δεν επιτρέπουμε διαδρομές εκτός project
#     p = Path(path).resolve()
#     if not p.exists() or not p.is_file():
#         raise HTTPException(status_code=404, detail="EML not found")
#     # (Προαιρετικά) περιορισμός κάτω από /data/eml
#     # eml_root = (BASE_DIR / "data" / "eml").resolve()
#     # if eml_root not in p.parents:
#     #     raise HTTPException(status_code=403, detail="Forbidden path")
#     return FileResponse(str(p), media_type="message/rfc822", filename=p.name)
#
# @router.get("/emails/{email_id}/download")
# def download_eml(email_id: int, db: Session = Depends(get_db)):
#     em = db.get(Email, email_id)
#     if not em or not em.eml_path:
#         raise HTTPException(status_code=404, detail="Email not found")
#     return _safe_file_response(em.eml_path)
#
def _extract_best_part(msg: email.message.Message) -> tuple[str, str]:
    """
    Επιστρέφει (kind, content). kind='html' ή 'text'.
    Προτιμά text/html, αλλιώς text/plain. Αποφεύγουμε attachments.
    """
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment":
                continue
            if ctype == "text/html":
                try:
                    return "html", part.get_content()
                except Exception:
                    pass
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment":
                continue
            if ctype == "text/plain":
                try:
                    return "text", part.get_content()
                except Exception:
                    pass
    else:
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/html":
            try:
                return "html", msg.get_content()
            except Exception:
                pass
        if ctype == "text/plain":
            try:
                return "text", msg.get_content()
            except Exception:
                pass
    return "text", "(no previewable part)"

_SCRIPT_TAG_RE = re.compile(r"<\s*script\b.*?>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)
_EVENT_ATTR_RE = re.compile(r"\son\w+\s*=\s*\".*?\"", re.IGNORECASE | re.DOTALL)

def _sanitize_html(s: str) -> str:
    """
    Απλή απολύμανση: αφαιρούμε <script>…</script> και inline event handlers.
    (Αν θέλεις αυστηρότερο, εγκαθιστούμε bleach.)
    """
    s = _SCRIPT_TAG_RE.sub("", s)
    s = _EVENT_ATTR_RE.sub("", s)
    return s
#
# @router.get("/emails/{email_id}/preview", response_class=HTMLResponse)
# def preview_email(email_id: int, db: Session = Depends(get_db)):
#     em = db.get(Email, email_id)
#     if not em or not em.eml_path:
#         raise HTTPException(status_code=404, detail="Email not found")
#     p = Path(em.eml_path).resolve()
#     if not p.exists():
#         raise HTTPException(status_code=404, detail="EML file not found")
#
#     with p.open("rb") as f:
#         msg = email.message_from_binary_file(f, policy=email.policy.default)
#
#     kind, content = _extract_best_part(msg)
#
#     if kind == "html":
#         safe = _sanitize_html(content or "")
#         # Τυλίγουμε με ένα ελαφρύ frame για να μην “σκοτώσει” το UI
#         return HTMLResponse(
#             "<!doctype html><meta charset='utf-8'>"
#             "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}"
#             "iframe,img,video{max-width:100%;} table{max-width:100%;} pre{white-space:pre-wrap;}</style>"
#             f"{safe}"
#         )
#     else:
#         return HTMLResponse(
#             "<!doctype html><meta charset='utf-8'>"
#             "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}"
#             "pre{white-space:pre-wrap;}</style>"
#             f"<pre>{(content or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')}</pre>"
#         )



@router.get("/emails/by-mid/{mid}/download")
def download_eml_by_mid(mid: str, db: Session = Depends(get_db)):
    em = db.execute(select(Email).where(Email.message_id == mid)).scalar_one_or_none()
    if not em or not em.eml_path:
        raise HTTPException(status_code=404, detail="Email not found")
    p = Path(em.eml_path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="EML file not found")
    return FileResponse(str(p), media_type="message/rfc822", filename=p.name)

@router.get("/emails/by-mid/{mid}/preview", response_class=HTMLResponse)
def preview_email_by_mid(mid: str, db: Session = Depends(get_db)):
    em = db.execute(select(Email).where(Email.message_id == mid)).scalar_one_or_none()
    if not em or not em.eml_path:
        raise HTTPException(status_code=404, detail="Email not found")
    p = Path(em.eml_path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="EML file not found")

    with p.open("rb") as f:
        msg = pyemail.message_from_binary_file(f, policy=email.policy.default)

    kind, content = _extract_best_part(msg)
    if kind == "html":
        safe = _sanitize_html(content or "")
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'>"
            "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}iframe,img,video{max-width:100%;}table{max-width:100%;}pre{white-space:pre-wrap;}</style>"
            f"{safe}"
        )
    esc = (content or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}pre{white-space:pre-wrap;}</style>"
        f"<pre>{esc}</pre>"
    )

