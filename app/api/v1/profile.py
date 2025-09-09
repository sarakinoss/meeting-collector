# app/api/v1/profile.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import imaplib, ssl
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.db.session import SessionLocal, get_db  # αν έχεις ήδη get_db, χρησιμοποίησέ το
from app.api.deps import get_current_user
from app.db.models import UserPreferences, MailAccount, MailAccountFolderPref, User

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])

# @router.get("/prefs") ...
# @router.put("/prefs") ...
# @router.get("/accounts") ...
# @router.get("/accounts/{account_id}/folders") ...
# @router.post("/accounts/{account_id}/folders") ...
# @router.post("/accounts/{account_id}/folders/refresh") ...

# ------------------ Schemas ------------------

class ProfilePrefsIn(BaseModel):
    prof_retention_months: Optional[int] = Field(None, ge=1, le=60)

class ProfilePrefsOut(ProfilePrefsIn):
    pass

class AccountOut(BaseModel):
    id: int
    display_name: Optional[str] = None
    email: Optional[str] = None

class FoldersSetIn(BaseModel):
    folders: List[str] = Field(default_factory=list)

class FoldersGetOut(BaseModel):
    selected: List[str] = Field(default_factory=list)

class FoldersRefreshOut(BaseModel):
    available: List[str] = Field(default_factory=list)
    selected: List[str] = Field(default_factory=list)

# ------------------ Helpers ------------------

def _ensure_account_belongs_to_user(db: Session, user_id: int, account_id: int) -> MailAccount:
    acc = db.execute(
        select(MailAccount).where(MailAccount.id == account_id)
    ).scalar_one_or_none()
    if not acc or acc.owner != user_id:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc

def _imap_list_folders(host: str, port: int | None, use_ssl: bool, username: str, password: str) -> List[str]:
    """
    Επιστρέφει λίστα φακέλων IMAP (top-level). Απλό LIST parse.
    """
    folders: List[str] = []
    try:
        if use_ssl:
            port = port or 993
            with imaplib.IMAP4_SSL(host, port) as M:
                M.login(username, password)
                typ, data = M.list()
        else:
            port = port or 143
            with imaplib.IMAP4(host, port) as M:
                M.starttls()  # αν ο server δεν υποστηρίζει, μπορεί να ρίξει exception
                M.login(username, password)
                typ, data = M.list()

        if typ != "OK" or data is None:
            return folders

        # data: [b'(\\HasNoChildren) "/" "INBOX"', ...]
        for raw in data:
            if not raw:
                continue
            line = raw.decode(errors="ignore")
            # Πάρε το τελευταίο quoted κομμάτι ως mail folder name
            # π.χ. ... "/" "INBOX"  -> INBOX
            # π.χ. ... "/" "Sent"   -> Sent
            name = line.rsplit('"', 2)[1] if '"' in line else line.split()[-1]
            if name:
                folders.append(name)
    except Exception:
        # Σκόπιμα “σιωπηλά” για το UI (θα δείξεις banner αν θες)
        pass
    # Μικρό dedupe/ταξινόμηση
    folders = sorted(list({f.strip(): None for f in folders if f.strip()}.keys()), key=str.casefold)
    return folders

# ------------------ Routes ------------------

@router.get("/prefs", response_model=ProfilePrefsOut)
def get_profile_prefs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prefs = db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    ).scalar_one_or_none()
    return ProfilePrefsOut(
        prof_retention_months=prefs.prof_retention_months if prefs else None
    )

@router.put("/prefs", response_model=ProfilePrefsOut)
def update_profile_prefs(
    payload: ProfilePrefsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    prefs = db.execute(
        select(UserPreferences).where(UserPreferences.user_id == user.id)
    ).scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)

    prefs.prof_retention_months = payload.prof_retention_months
    db.commit(); db.refresh(prefs)
    return ProfilePrefsOut(prof_retention_months=prefs.prof_retention_months)

@router.get("/accounts", response_model=List[AccountOut])
def list_my_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(MailAccount.id, MailAccount.display_name, MailAccount.email)
        .where(MailAccount.owner == user.id)
        .order_by(MailAccount.id.asc())
    ).all()
    return [AccountOut(id=r[0], display_name=r[1], email=r[2]) for r in rows]

@router.get("/accounts/{account_id}/folders", response_model=FoldersGetOut)
def get_selected_folders(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_account_belongs_to_user(db, user.id, account_id)
    rows = db.execute(
        select(MailAccountFolderPref.folder)
        .where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
            MailAccountFolderPref.include.is_(True),
        )
    ).scalars().all()
    return FoldersGetOut(selected=list(rows))

@router.post("/accounts/{account_id}/folders", response_model=FoldersGetOut)
def set_selected_folders(
    account_id: int,
    payload: FoldersSetIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_account_belongs_to_user(db, user.id, account_id)
    # Καθάρισε παλιά
    db.execute(
        delete(MailAccountFolderPref).where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
        )
    )
    # Εισαγωγή νέων (dedupe/trim)
    clean = []
    seen = set()
    for f in payload.folders:
        f2 = (f or "").strip()
        if f2 and f2 not in seen:
            seen.add(f2)
            clean.append(f2)
    if clean:
        db.bulk_save_objects([
            MailAccountFolderPref(
                user_id=user.id,
                mail_account_id=account_id,
                folder=f2,
                include=True,
            ) for f2 in clean
        ])
    db.commit()
    return FoldersGetOut(selected=clean)

@router.post("/accounts/{account_id}/folders/refresh", response_model=FoldersRefreshOut)
def refresh_available_folders(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    acc = _ensure_account_belongs_to_user(db, user.id, account_id)

    # Ανάκτηση διαπιστευτηρίων για IMAP
    host = acc.imap_host
    port = acc.imap_port
    use_ssl = bool(acc.imap_ssl)
    username = acc.imap_user or acc.email  # fallback: email
    password = acc.imap_password

    if not (host and username and password):
        raise HTTPException(status_code=400, detail="Incomplete IMAP credentials")

    available = _imap_list_folders(
        host=host, port=port, use_ssl=use_ssl,
        username=username, password=password
    )

    # Επιστροφή και των ήδη επιλεγμένων
    selected = db.execute(
        select(MailAccountFolderPref.folder).where(
            MailAccountFolderPref.user_id == user.id,
            MailAccountFolderPref.mail_account_id == account_id,
            MailAccountFolderPref.include.is_(True),
        )
    ).scalars().all()

    return FoldersRefreshOut(available=available, selected=list(selected))



