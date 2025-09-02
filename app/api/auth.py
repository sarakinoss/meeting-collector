from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db, SessionLocal
from app.db.models import User, UserMailAccess
from app.api.deps import  require_user, require_admin
from app.core.security import verify_password, hash_password


BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

router = APIRouter(prefix="/auth")

# def _no_users_exist() -> bool:
#     with SessionLocal() as db:
#         return db.execute(select(User.id).limit(1)).first() is None

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


# @router.get("/admin/users", response_class=HTMLResponse)
# async def admin_users_page(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
#     rows = db.execute(select(User).order_by(User.id.asc())).scalars().all()
#     return templates.TemplateResponse("admin_users.html", {"request": request, "users": rows})

# @router.get("/admin/users", response_class=HTMLResponse, name="admin_users_page")
# async def admin_users_page(
#     request: Request,
#     db: Session = Depends(get_db),
#     ok: str | None = None,
#     err: str | None = None,
#     admin: User = Depends(require_admin)
# ):
#     users = db.execute(select(User).order_by(User.id.asc())).scalars().all()
#     return templates.TemplateResponse(
#         "admin_users.html",
#         {"request": request, "users": users, "ok": ok, "err": err},
#     )
@router.get("/admin/users", response_class=HTMLResponse, name="admin_users_page")
async def admin_users_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = db.execute(select(User).order_by(User.id.asc())).scalars().all()
    # ---- πάρ’ το flash και εξαφάνισέ το από το session
    flash = request.session.pop("flash", None) if "session" in request.scope else None
    ok = flash.get("ok") if isinstance(flash, dict) else None
    err = flash.get("err") if isinstance(flash, dict) else None
    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "users": users, "ok": ok, "err": err},
    )

# # TODO refresh same page showing new add
# @router.post("/admin/users")
# async def admin_create_user(
#     request: Request,
#     username: str = Form(...),
#     email: str = Form(""),
#     password: str = Form(...),
#     is_admin: bool = Form(False),
#     db: Session = Depends(get_db),
#     admin: User = Depends(require_admin)
# ):
#     if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
#         return RedirectResponse("/admin/users?err=username", status_code=302)
#     u = User(username=username, email=email or None, password_hash=hash_password(password), is_admin=bool(is_admin))
#     db.add(u); db.commit()
#     return RedirectResponse("/admin/users?ok=1", status_code=302)

# --- POST: δημιουργία χρήστη ---
# @router.post("/admin/users")
# async def admin_create_user(
#     request: Request,
#     username: str = Form(...),
#     email: str = Form(""),
#     password: str = Form(...),
#     is_admin: str = Form("false"),                 # "true"/"false" από <select>
#     db: Session = Depends(get_db),
#     admin: User = Depends(require_admin),
# ):
#     # έλεγχος μοναδικότητας
#     if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
#         # dest = request.url_for("admin_users_page") + "?err=username"
#         dest = request.url_for("admin_users_page").include_query_params(err=username)
#         return RedirectResponse(dest, status_code=303)
#
#     is_admin_bool = str(is_admin).lower() in ("1", "true", "on", "yes")
#     u = User(
#         username=username,
#         email=(email or None),
#         password_hash=hash_password(password),
#         is_admin=is_admin_bool,
#     )
#     db.add(u)
#     db.commit()
#
#     # dest = request.url_for("admin_users_page") + "?ok=1"
#     dest = request.url_for("admin_users_page").include_query_params(ok="1")
#     return RedirectResponse(dest, status_code=303)
@router.post("/admin/users")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    is_admin: str = Form("false"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        # έλεγχος μοναδικότητας
        exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if exists:
            if "session" in request.scope:
                request.session["flash"] = {"err": "username"}  # ή μήνυμα στα ελληνικά
            return RedirectResponse(request.url_for("admin_users_page"), status_code=303)

        is_admin_bool = str(is_admin).lower() in ("1", "true", "on", "yes")
        u = User(
            username=username,
            email=(email or None),
            password_hash=hash_password(password),
            is_admin=is_admin_bool,
        )
        db.add(u)
        db.commit()

        if "session" in request.scope:
            request.session["flash"] = {"ok": "1"}
        return RedirectResponse(request.url_for("admin_users_page"), status_code=303)

    except Exception as e:
        db.rollback()
        if "session" in request.scope:
            request.session["flash"] = {"err": str(e)}
        return RedirectResponse(request.url_for("admin_users_page"), status_code=303)

@router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int,
                            db: Session = Depends(get_db),
                            admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    # μην επιτρέπεις να διαγράψει κάποιος τον εαυτό του
    if u.id == admin.id:
        raise HTTPException(status_code=400, detail="Δεν μπορείς να διαγράψεις τον εαυτό σου.")

    # μην αφήσεις να χαθεί ο τελευταίος admin
    if u.is_admin:
        admins_count = db.execute(select(User).where(User.is_admin == True)).scalars().all()
        if len(admins_count) <= 1:
            raise HTTPException(status_code=400, detail="Πρέπει να υπάρχει τουλάχιστον ένας admin.")
    db.delete(u)
    db.commit()
    return {"ok": True}

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



# ---------- Settings Page ----------
# @router.get("/settings", response_class=HTMLResponse)
# async def settings_page(request: Request, user: User = Depends(require_user)):
#     return templates.TemplateResponse("settings.html", {"request": request, "user": user})

@router.get("/settings", response_class=HTMLResponse, name="settings_page")
async def settings_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})



@router.post("/api/access/{mail_account_id}/{user_id}")
def grant_access(mail_account_id: int, user_id: int, db: Session = Depends(get_db)):
    exists = db.execute(select(UserMailAccess).where(
        UserMailAccess.user_id == user_id,
        UserMailAccess.mail_account_id == mail_account_id
    )).first()
    if not exists:
        db.add(UserMailAccess(user_id=user_id, mail_account_id=mail_account_id, is_owner=False, can_parse=True, can_send=False))
        db.commit()
    return {"ok": True}

@router.delete("/api/access/{mail_account_id}/{user_id}")
def revoke_access(mail_account_id: int, user_id: int, db: Session = Depends(get_db)):
    row = db.get(UserMailAccess, {"user_id": user_id, "mail_account_id": mail_account_id})
    if row:
        db.delete(row); db.commit()
    return {"ok": True}


# ---------- TODO SSO placeholders (to implement next) ----------
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