# app/web/pages.py
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import MailAccount, User
from app.api.deps import require_user

# app/web/pages.py -> parents[1] == app/
BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

router = APIRouter()

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(MailAccount)
            .where(MailAccount.owner == str(user.id))
            .order_by(MailAccount.id.desc())
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse("accounts.html", {"request": request, "accounts": rows})


@router.get("/auth/settings", response_class=HTMLResponse, name="settings_page")
@router.get("/auth/settings/{section}", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    section: str | None = None,
    user: User = Depends(require_user),
):
    active = section or "email-accounts"
    # Στο μέλλον θα περάσουμε επιπλέον data ανά ενότητα. Για την Email Accounts, το JS μιλά με /api/v1/accounts.
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "active": active,
        },
    )