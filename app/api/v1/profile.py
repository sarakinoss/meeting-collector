# app/api/v1/profile.py
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
import imaplib
import re

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User, UserPreferences, MailAccount, MailAccountFolderPref
from app.core.crypto import decrypt  # χρησιμοποιείς ήδη decrypt()

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])

LIST_SPLIT = re.compile(r'\((?P<attrs>[^)]*)\) (?P<rest>.*)')

import imaplib, re  # αν δεν υπάρχουν ήδη

# Mapping flags -> ανθρώπινη ετικέτα για εμφάνιση
SPECIAL_LABELS = {
    "\\inbox":   "Inbox",
    "\\drafts":  "Drafts",
    "\\sent":    "Sent",
    "\\archive": "Archives",
    "\\all":     "Archives",   # RFC 6154 \All (π.χ. Gmail "All Mail")
    "\\junk":    "Junk",
    "\\trash":   "Trash",
}
SPECIAL_ORDER = ["\\inbox","\\drafts","\\sent","\\archive","\\all","\\junk","\\trash"]

def _parse_list_line(line: bytes) -> tuple[list[str], str]:
    """LIST/XLIST line -> (attributes lowercased, mailbox name)."""
    s = line.decode("utf-8", "ignore")
    m = re.search(r"\((?P<attrs>[^)]*)\)\s+\"(?P<delim>[^\"]*)\"\s+(?P<name>.+)$", s)
    if not m:
        q = re.findall(r"\"([^\"]+)\"", s)
        name = q[-1] if q else s
        return ([], name)
    attrs = [a.strip().lower() for a in m.group("attrs").split() if a.strip()]
    name = m.group("name").strip()
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    return (attrs, name)

def _extract_special_from_list(list_data: list[bytes]) -> list[dict]:
    """Μαζεύει τους system folders από LIST/XLIST lines."""
    found: dict[str, str] = {}
    for line in list_data or []:
        attrs, box = _parse_list_line(line)
        low = set(attrs)
        for flag, _ in SPECIAL_LABELS.items():
            if flag in low:
                found.setdefault(flag, box)
        if box.upper() == "INBOX":
            found.setdefault("\\inbox", box)

    out: list[dict] = []
    for flag in SPECIAL_ORDER:
        if flag in found:
            out.append({"name": found[flag], "label": SPECIAL_LABELS[flag]})

    if not out:
        # fallback: τουλάχιστον INBOX
        for line in list_data or []:
            _, box = _parse_list_line(line)
            if box.upper() == "INBOX":
                out = [{"name": box, "label": "Inbox"}]
                break
    return out

def _coarse_guess_system_folders(names: list[str]) -> list[dict]:
    """
    Τελευταίο μέτρο όταν ΔΕΝ έχουμε SPECIAL-USE flags.
    Προσπαθούμε να εντοπίσουμε system folders από το όνομα (τελευταίο segment).
    """
    def last(seg: str) -> str:
        # πάρε τελευταίο κομμάτι από πιθανές ιεραρχίες ("INBOX/Συναντήσεις", "INBOX.Sent", κ.λπ.)
        for delim in ("/", ".", "\\"):
            if delim in seg:
                seg = seg.split(delim)[-1]
        return seg.lower()

    want = {
        "inbox":   {"inbox"},
        "drafts":  {"draft", "drafts"},
        "sent":    {"sent", "sent mail", "sent items", "outbox"},
        "junk":    {"junk", "spam", "bulk"},
        "trash":   {"trash", "deleted", "bin"},
        "archive": {"archive", "archives", "all mail", "all"},
    }
    picked: dict[str, str] = {}
    for n in names:
        ln = last(n)
        up = n.upper()
        if up == "INBOX":
            picked.setdefault("inbox", n)
            continue
        for key, alts in want.items():
            if any(alt == ln for alt in alts):
                picked.setdefault(key, n)

    out = []
    order = ["inbox","drafts","sent","archive","junk","trash"]
    labels = {"inbox":"Inbox","drafts":"Drafts","sent":"Sent","archive":"Archives","junk":"Junk","trash":"Trash"}
    for k in order:
        if k in picked:
            out.append({"name": picked[k], "label": labels[k]})
    return out

def _imap_list_special(host: str, port: int|None, use_ssl: bool, user: str, password: str) -> list[dict]:
    """
    Ανοίγει IMAP, τρέχει LIST (+ XLIST αν υπάρχει),
    και επιστρέφει ΜΟΝΟ τους system folders [{name,label},...].
    """
    port = port or (993 if use_ssl else 143)
    list_lines: list[bytes] = []
    try:
        cls = imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4
        M = cls(host, port)
        try:
            M.login(user, password)
            typ, data = M.list("", "*")
            if typ == "OK" and data:
                list_lines.extend([d for d in data if d])
            # XLIST (π.χ. Gmail)
            try:
                typ2, dat2 = M._simple_command("XLIST", '""', '"*"')
                typ2, dat2 = M._untagged_response(typ2, dat2, "XLIST")
                if typ2 == "OK" and dat2:
                    list_lines.extend([d for d in dat2 if d])
            except Exception:
                pass
        finally:
            try: M.logout()
            except Exception: pass
    except Exception:
        return []
    return _extract_special_from_list(list_lines)









# ------------------ Helpers ------------------

def _account_of_user_or_404(db: Session, user_id: int, account_id: int) -> MailAccount:
    acc = db.get(MailAccount, account_id)
    if not acc or str(acc.owner) != str(user_id):   # owner παραμένει string στο schema σου
        raise HTTPException(status_code=404, detail="Account not found")
    return acc

def _imap_list(host: str, port: Optional[int], use_ssl: bool, user: str, password: str) -> List[str]:
    """
    Επιστρέφει λίστα ονομάτων φακέλων IMAP (απλό LIST).
    """
    folders: List[str] = []
    if use_ssl:
        port = port or 993
        M = imaplib.IMAP4_SSL(host, port)
    else:
        port = port or 143
        M = imaplib.IMAP4(host, port)
        try:
            M.starttls()
        except Exception:
            pass

    try:
        M.login(user, password)
        typ, data = M.list()
    finally:
        try:
            M.logout()
        except Exception:
            pass

    if typ != "OK" or not data:
        return folders

    for raw in data:
        if not raw:
            continue
        line = raw.decode(errors="ignore")
        # πάρε το τελευταίο quoted κομμάτι
        name = line.rsplit('"', 2)[1] if '"' in line else line.split()[-1]
        if name:
            folders.append(name)
    # dedupe + φυσική ταξινόμηση
    return sorted(set(folders), key=str.casefold)

# ------------------ PREFS (retention) ------------------

@router.get("/prefs")
def get_profile_prefs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prefs = db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    ).scalar_one_or_none()
    return {
        "prof_retention_months": (prefs.prof_retention_months if prefs else None)
    }

@router.put("/prefs")
def update_profile_prefs(
    payload: dict = Body(..., example={"prof_retention_months": 12}),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    retention = payload.get("prof_retention_months", None)
    prefs = db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    ).scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
    prefs.prof_retention_months = retention
    db.commit(); db.refresh(prefs)
    return {"prof_retention_months": prefs.prof_retention_months}

# ------------------ Accounts (του χρήστη) ------------------

@router.get("/accounts")
def list_my_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(MailAccount.id, MailAccount.display_name, MailAccount.email)
        .where(MailAccount.owner == str(user.id))
        .order_by(MailAccount.id.asc())
    ).all()
    return [{"id": r[0], "display_name": r[1], "email": r[2]} for r in rows]

# ------------------ Folders (IMAP LIST) ------------------

@router.post("/accounts/{account_id}/folders/refresh")
def refresh_folders(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    acc = _account_of_user_or_404(db, user.id, account_id)

    host = acc.imap_host
    if not host:
        raise HTTPException(status_code=400, detail="IMAP not configured")
    username = acc.imap_user or acc.email
    try:
        password = decrypt(acc.imap_password_enc) if acc.imap_password_enc else None
    except Exception:
        password = None
    if not (username and password):
        raise HTTPException(status_code=400, detail="IMAP credentials incomplete")

    use_ssl = bool(acc.imap_ssl)
    port = acc.imap_port

    available = _imap_list_special(host=host, port=port, use_ssl=use_ssl, user=username, password=password)

    if not available:
        raw = _imap_list(host=host, port=port, use_ssl=use_ssl, user=username, password=password)
        available = _coarse_guess_system_folders(raw)

    # φέρε ήδη selected για να τα προ-τικάρεις
    # ====== ΒΕΡΣΙΟΝ A (αν ΤΟ ΜΟΝΤΕΛΟ έχει mail_account_id + folder_name) ======
    selected = db.execute(
        select(MailAccountFolderPref.folder)
        .where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
        )
    ).scalars().all()
    # ====== ΒΕΡΣΙΟΝ B (αν το μοντέλο έχει account_id + folder_name) ======
    # selected = db.execute(
    #     select(MailAccountFolderPref.folder)
    #     .where(
    #         MailAccountFolderPref.user_id == user.id,
    #         MailAccountFolderPref.account_id == account_id,
    #     )
    # ).scalars().all()

    return {"available": available, "selected": list(selected)}

@router.get("/accounts/{account_id}/folders")
def get_selected_folders(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _account_of_user_or_404(db, user.id, account_id)

    # ====== ΒΕΡΣΙΟΝ A ======
    rows = db.execute(
        select(MailAccountFolderPref.folder)
        .where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
        )
    ).scalars().all()
    # ====== ΒΕΡΣΙΟΝ B ======
    # rows = db.execute(
    #     select(MailAccountFolderPref.folder)
    #     .where(
    #         MailAccountFolderPref.user_id == user.id,
    #         MailAccountFolderPref.account_id == account_id,
    #     )
    # ).scalars().all()

    return {"selected": list(rows)}

@router.post("/accounts/{account_id}/folders")
def set_selected_folders(
    account_id: int,
    payload: dict = Body(..., example={"folders": ["INBOX", "Sent"]}),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _account_of_user_or_404(db, user.id, account_id)
    folders = payload.get("folders") or []
    if not isinstance(folders, list):
        raise HTTPException(status_code=400, detail="folders must be a list")

    # καθάρισε παλιά
    # ====== ΒΕΡΣΙΟΝ A ======
    db.execute(
        delete(MailAccountFolderPref).where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
        )
    )
    # ====== ΒΕΡΣΙΟΝ B ======
    # db.execute(
    #     delete(MailAccountFolderPref).where(
    #         MailAccountFolderPref.user_id == user.id,
    #         MailAccountFolderPref.account_id == account_id,
    #     )
    # )

    clean = []
    seen = set()
    for f in folders:
        f2 = (f or "").strip()
        if f2 and f2 not in seen:
            seen.add(f2)
            clean.append(f2)

    # εισαγωγή νέων
    # ====== ΒΕΡΣΙΟΝ A ======
    db.bulk_save_objects([
        MailAccountFolderPref(
            user_id=user.id,
            mail_account_id=account_id,
            folder=name
        ) for name in clean
    ])
    # ====== ΒΕΡΣΙΟΝ B ======
    # db.bulk_save_objects([
    #     MailAccountFolderPref(
    #         user_id=user.id,
    #         account_id=account_id,
    #         folder_name=name
    #     ) for name in clean
    # ])

    db.commit()
    return {"ok": True, "selected": clean}
