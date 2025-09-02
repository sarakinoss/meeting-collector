# app/api/v1/emails.py
from __future__ import annotations
from pathlib import Path
import re
import email as pyemail
import email.policy

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Email
from app.api.deps import require_user  # προστατεύουμε τα αρχεία σου

router = APIRouter(prefix="/api/v1/emails", tags=["Emails"])

# TODO Remove duplicate methods and use them.
# TODO Comment code.


def _safe_file_response(path: str) -> FileResponse:
    p = Path(path).resolve()
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="EML not found")
    return FileResponse(str(p), media_type="message/rfc822", filename=p.name)

# ---- Helpers to pick “best” body part and sanitize ----
def _extract_best_part(msg: pyemail.message.Message) -> tuple[str, str]:
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

_SCRIPT_TAG_RE = re.compile(r"<\s*script\b.*?>.*?<\s*/\s*script\s*>",
                            re.IGNORECASE | re.DOTALL)
_EVENT_ATTR_RE = re.compile(r"\son\w+\s*=\s*\".*?\"",
                            re.IGNORECASE | re.DOTALL)

def _sanitize_html(s: str) -> str:
    s = _SCRIPT_TAG_RE.sub("", s)
    s = _EVENT_ATTR_RE.sub("", s)
    return s

# ---- by numeric email id ----
@router.get("/{email_id}/download")
def download_eml(email_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    em = db.get(Email, email_id)
    if not em or not em.eml_path:
        raise HTTPException(status_code=404, detail="Email not found")
    return _safe_file_response(em.eml_path)

@router.get("/{email_id}/preview", response_class=HTMLResponse)
def preview_email(email_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    em = db.get(Email, email_id)
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
            "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}"
            "iframe,img,video{max-width:100%;}table{max-width:100%;}pre{white-space:pre-wrap;}</style>"
            f"{safe}"
        )

    esc = (content or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}pre{white-space:pre-wrap;}</style>"
        f"<pre>{esc}</pre>"
    )

# ---- by Message-ID (mid) ----
@router.get("/by-mid/{mid}/download")
def download_eml_by_mid(mid: str, user=Depends(require_user), db: Session = Depends(get_db)):
    em = db.execute(select(Email).where(Email.message_id == mid)).scalar_one_or_none()
    if not em or not em.eml_path:
        raise HTTPException(status_code=404, detail="Email not found")
    return _safe_file_response(em.eml_path)

@router.get("/by-mid/{mid}/preview", response_class=HTMLResponse)
def preview_email_by_mid(mid: str, user=Depends(require_user), db: Session = Depends(get_db)):
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
            "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}"
            "iframe,img,video{max-width:100%;}table{max-width:100%;}pre{white-space:pre-wrap;}</style>"
            f"{safe}"
        )

    esc = (content or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<style>body{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}pre{white-space:pre-wrap;}</style>"
        f"<pre>{esc}</pre>"
    )
