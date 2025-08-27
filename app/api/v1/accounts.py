# app/api/v1/accounts.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import MailAccount, User
from app.api.deps import require_user
from app.core.crypto import encrypt
from app.schemas.accounts import AccountIn  # κρατάμε το υπάρχον schema

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import imaplib, ssl
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import MailAccount, User
from app.api.deps import require_user
from app.core.crypto import decrypt  # <- ΠΡΟΣΟΧΗ: import decryp

router = APIRouter(prefix="/api/v1/accounts", tags=["Accounts"])


class ImapTestIn(BaseModel):
    email: str
    imap_host: str
    imap_port: Optional[int] = None
    imap_ssl: Optional[bool] = True
    imap_user: Optional[str] = None
    imap_password: str


ImapTestIn.model_rebuild()  # <-- σημαντικό σε reload/circular cases


def _mask(secret_enc: str | None) -> str | None:
    return "••••••" if secret_enc else None


@router.get("", summary="List all accounts for current user")
async def list_accounts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(MailAccount)
            .where(MailAccount.owner == str(user.id))
            .order_by(MailAccount.id.desc())
        )
        .scalars()
        .all()
    )
    return [{
        "id": r.id,
        "display_name": r.display_name,
        "email": r.email,
        "smtp_host": r.smtp_host, "smtp_port": r.smtp_port, "smtp_ssl": r.smtp_ssl,
        "smtp_user": r.smtp_user, "smtp_password": _mask(r.smtp_password_enc),
        "imap_host": r.imap_host, "imap_port": r.imap_port, "imap_ssl": r.imap_ssl,
        "imap_user": r.imap_user, "imap_password": _mask(r.imap_password_enc),
        "enabled": r.enabled,
        "can_parse": r.can_parse,
        "last_full_parse_at": r.last_full_parse_at.isoformat() if r.last_full_parse_at else None,
        "last_incremental_parse_at": r.last_incremental_parse_at.isoformat() if r.last_incremental_parse_at else None,
    } for r in rows]


@router.get("/parse-enabled", summary="List only parse-enabled accounts")
async def list_parse_enabled(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(MailAccount)
            .where(MailAccount.owner == str(user.id))
            .order_by(MailAccount.id.desc())
        )
        .scalars()
        .all()
    )
    out = []
    for r in rows:
        if not (r.enabled and r.can_parse):
            continue
        out.append({
            "id": r.id,
            "email": r.email,
            "display_name": r.display_name,
            "parse_enabled": True,
            "last_full_parse_at": r.last_full_parse_at.isoformat() if r.last_full_parse_at else None,
            "last_incremental_parse_at": r.last_incremental_parse_at.isoformat() if r.last_incremental_parse_at else None,
        })
    return out


@router.post("/test-connection")
async def test_connection(data: ImapTestIn):
    user = data.imap_user or data.email
    use_ssl = bool(data.imap_ssl) if data.imap_ssl is not None else False
    port = int(data.imap_port) if data.imap_port is not None else (993 if use_ssl else 143)

    # Προτίμηση: IMAPClient όπως ο parser. Fallback: imaplib
    try:
        try:
            from imapclient import IMAPClient  # type: ignore
            server = IMAPClient(host=data.imap_host, port=port, ssl=use_ssl)
            # ο parser κάνει login με email ως username
            server.login(user, data.imap_password)
            server.logout()
            return {"detail": "IMAP σύνδεση επιτυχής"}
        except ImportError:
            import imaplib
            M = imaplib.IMAP4_SSL(data.imap_host, port) if use_ssl else imaplib.IMAP4(data.imap_host, port)
            M.login(user, data.imap_password)
            M.logout()
            return {"detail": "IMAP σύνδεση επιτυχής"}
    except Exception as e:
        # στείλε «καθαρό» μήνυμα για να το δει το banner σου
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")


@router.post("/{account_id}/test-connection")
async def test_connection_for_account(
        account_id: int,
        user: User = Depends(require_user),
        db: Session = Depends(get_db),
):
    row = db.get(MailAccount, account_id)
    if not row or row.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Not found")

    # Credentials από τη βάση
    email = row.email
    host = row.imap_host
    port = row.imap_port or (993 if row.imap_ssl else 143)
    use_ssl = bool(row.imap_ssl)
    username = row.imap_user or email
    try:
        password = decrypt(row.imap_password_enc) if row.imap_password_enc else None
    except Exception:
        password = None

    if not (email and host and password):
        raise HTTPException(status_code=400, detail="Incomplete IMAP credentials")

    # Προτίμηση: IMAPClient όπως ο parser. Fallback: imaplib.
    try:
        try:
            from imapclient import IMAPClient
            server = IMAPClient(host=host, port=port, ssl=use_ssl)
            server.login(username, password)  # parser-style: username = email
            server.logout()
            return {"ok": True, "detail": "IMAP σύνδεση επιτυχής"}
        except ImportError:
            import imaplib
            M = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
            M.login(username, password)
            M.logout()
            return {"ok": True, "detail": "IMAP σύνδεση επιτυχής"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")


@router.post("", status_code=201, summary="Create account")
async def create_account(payload: AccountIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    exists = db.execute(
        select(MailAccount).where(MailAccount.owner == str(user.id), MailAccount.email == payload.email)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists for this user")

    row = MailAccount(
        display_name=payload.display_name,
        email=payload.email,
        smtp_host=payload.smtp_host, smtp_port=payload.smtp_port, smtp_ssl=payload.smtp_ssl,
        smtp_user=payload.smtp_user,
        smtp_password_enc=encrypt(payload.smtp_password) if payload.smtp_password else None,
        imap_host=payload.imap_host, imap_port=payload.imap_port, imap_ssl=payload.imap_ssl,
        imap_user=payload.imap_user,
        imap_password_enc=encrypt(payload.imap_password) if payload.imap_password else None,
        enabled=True,
        owner=str(user.id),
    )
    db.add(row);
    db.commit();
    db.refresh(row)
    return {"id": row.id}


@router.delete("/{account_id}", status_code=204, summary="Delete account")
async def delete_account(account_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = db.get(MailAccount, account_id)
    if not row or row.owner != str(user.id):
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row);
    db.commit()
    return
