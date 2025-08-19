from __future__ import annotations
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db, SessionLocal
from app.db.models import User, MailAccount
from app.api.deps import get_current_user, require_user, require_admin
from app.core.security import verify_password, hash_password


BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

router = APIRouter(prefix="/auth")

def _no_users_exist() -> bool:
    with SessionLocal() as db:
        return db.execute(select(User.id).limit(1)).first() is None

@router.get("/first-run", response_class=HTMLResponse)
async def first_run_page(request: Request, db: Session = Depends(get_db)):
    # αν υπάρχει ήδη χρήστης, μην επιτρέπεις πρόσβαση
    have_user = db.execute(select(User.id).limit(1)).first()
    if have_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("first_run.html", {"request": request})

@router.post("/first-run")
async def first_run_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    have_user = db.execute(select(User.id).limit(1)).first()
    if have_user:
        return RedirectResponse("/", status_code=302)

    if not username or not password:
        return templates.TemplateResponse(
            "first_run.html",
            {"request": request, "error": "Συμπλήρωσε όνομα χρήστη και κωδικό."},
            status_code=400,
        )

    # μοναδικότητα username/email
    u_exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    e_exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if u_exists or e_exists:
        return templates.TemplateResponse(
            "first_run.html",
            {"request": request, "error": "Το username ή το email υπάρχει ήδη."},
            status_code=400,
        )

    u = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_admin=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    request.session["uid"] = u.id
    return RedirectResponse(request.url_for("settings_page"), status_code=302)

# @router.get("/first-run")
# async def first_run_form(request: Request):
#     if not _no_users_exist():
#         # admin υπάρχει ήδη: ΜΗΝ επιτρέπεις ξανά first-run
#         return RedirectResponse("/", status_code=302)  # ή raise HTTPException(404, "Not found")
#     # render φόρμα δημιουργίας admin
#     ...
#
# @router.post("/first-run")
# async def first_run_create_admin(request: Request):
#     if not _no_users_exist():
#         return RedirectResponse("/", status_code=302)  # ή 404
#     # 1) φτιάξε admin
#     # 2) κάνε auto-login γράφοντας request.session["uid"] = new_user.id
#     return RedirectResponse("/", status_code=302)

@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.execute(select(User).order_by(User.id.asc())).scalars().all()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": rows})

@router.post("/admin/users")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        return RedirectResponse("/admin/users?err=username", status_code=302)
    u = User(username=username, email=email or None, password_hash=hash_password(password), is_admin=bool(is_admin))
    db.add(u); db.commit()
    return RedirectResponse("/admin/users?ok=1", status_code=302)

# ---------- Login / Logout ----------
@router.get("/login", response_class=HTMLResponse, name="login_page")
async def login_page(request: Request):
    # If already logged in → redirect home
    if request.session.get("uid"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db),
):
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        # Back to login with flash message (simplified)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Λάθος στοιχεία. Δοκίμασε ξανά."},
            status_code=401,
        )
    # Success
    request.session["uid"] = user.id
    return RedirectResponse("/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(request.url_for("login_page"), status_code=302)


# ---------- SSO placeholders (to implement next) ----------
@router.get("/sso/{provider}")
async def sso_start(provider: str):
    # TODO: Implement OAuth2 with Authlib (Google/Microsoft)
    raise HTTPException(status_code=501, detail="SSO not implemented yet")


@router.get("/sso/{provider}/callback")
async def sso_callback(provider: str, request: Request, db: Session = Depends(get_db)):
    raise HTTPException(status_code=501, detail="SSO not implemented yet")


# ---------- ME (current user JSON) ----------
@router.get("/me")
async def me(user: User = Depends(require_user)):
    return {"id": user.id, "username": user.username, "email": user.email}

# ---------- Settings Page ----------
# @router.get("/settings", response_class=HTMLResponse)
# async def settings_page(request: Request, user: User = Depends(require_user)):
#     return templates.TemplateResponse("settings.html", {"request": request, "user": user})

@router.get("/settings", response_class=HTMLResponse, name="settings_page")
async def settings_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})
