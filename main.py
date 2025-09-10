import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, func
from typing import Sequence
import logging

# App components
from app.db.init_db import init_db
from scheduler import start_scheduler
from app.db.session import SessionLocal
from app.db.models import User


# Routers
from app.api.auth import router as auth_router
from web.pages import router as pages_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.emails import router as emails_router
from app.api.v1.notifications import router as notifications_router, reminders_scheduler_loop
from app.api.v1.profile import router as profile_router

# Load secret key
from app.core.config import SESSION_SECRET

# Admin-only access routes
ADMIN_ONLY_PREFIXES: Sequence[str] = (
    "/auth/settings",           # σελίδα ρυθμίσεων admin
    "/auth/api/access",         # grants/revokes (αν έχετε ακόμη αυτά τα routes)
    "/api/v1/admin",            # μελλοντικός admin router
    "/auth/admin",              # όλα τα admin UI routes
    "/api/v1/admin"
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()
#
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False)
# Static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
# Routes
app.include_router(auth_router)             # εδώ είναι το /auth απο το auth.py
app.include_router(pages_router)            # /, /accounts (HTML pages)
app.include_router(accounts_router)         # /api/v1/accounts
app.include_router(meetings_router)         # /api/v1/meetings/*
app.include_router(emails_router)           # /api/v1/emails/*
app.include_router(notifications_router)   # /api/v1/notifications
app.include_router(profile_router)          #/api/v1/profile


# init DB (δημιουργεί tables αν λείπουν)
init_db()

def _no_users_exist() -> bool:
    with SessionLocal() as db:
        return (db.execute(select(func.count(User.id))).scalar() or 0) == 0

# def _no_users_exist() -> bool:
#     with SessionLocal() as db:
#         return db.execute(select(User.id).limit(1)).first() is None

def _get_user(request: Request) -> User | None:
    if "session" not in request.scope:
        return None
    uid = request.session.get("uid")
    if not uid:
        return None
    with SessionLocal() as db:
        return db.get(User, uid)

# Αν τρέχεις με gunicorn/uvicorn workers>1, θα ξεκινήσει ένας scheduler ανά worker.
# Για τώρα που τεστάρουμε, κράτα 1 worker.
# Για production, θα το κάνουμε leader-only ή external scheduler (Celery/APScheduler).

# start scheduler (optional during early auth UI testing)
if not _no_users_exist():
    start_scheduler()


@app.on_event("startup")
async def _start_schedulers():
    # ξεκίνα το reminders loop (fire-and-forget task)
    #asyncio.create_task(reminders_scheduler_loop())
    # ξεκίνα το reminders loop (fire-and-forget task)
    t = asyncio.create_task(reminders_scheduler_loop(), name="reminders-scheduler")
    logging.getLogger(__name__).info("Started reminders scheduler task: %s", t.get_name())

@app.exception_handler(StarletteHTTPException)
async def auth_redirect_handler(request: Request, exc: StarletteHTTPException):
    # Αν endpoint σήκωσε 401 ΚΑΙ ο client ζητά HTML → redirect
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        dest = "/auth/first-run" if _no_users_exist() else "/auth/login"
        return RedirectResponse(dest, status_code=302)
    # API/JSON: κράτα το JSON 401
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

# TODO Do not remove until testing again by erasing db
# @app.middleware("http")
# async def first_run_redirect(request: Request, call_next):
#     # Άφησε ελεύθερα τα /static και /auth/*
#     p = request.url.path
#     if p.startswith("/static") or p.startswith("/auth"):
#         return await call_next(request)
#
#     # Αν ΔΕΝ υπάρχουν χρήστες, στείλε ΟΛΟΥΣ στο /auth/first-run
#     if _no_users_exist() and p != "/auth/first-run":
#         return RedirectResponse("/auth/first-run", status_code=302)
#
#     return await call_next(request)


@app.middleware("http")
async def first_run_and_rbac(request: Request, call_next):
    p = request.url.path

    # ΠΑΝΤΑ άφηνε static
    if p.startswith("/static"):
        return await call_next(request)

    # === Στάδιο A: FIRST-RUN GUARD ===
    if _no_users_exist():
        # Επίτρεψε ΜΟΝΟ το /auth/first-run (GET/POST) όταν δεν υπάρχουν users
        if p.startswith("/auth/first-run"):
            return await call_next(request)
        return RedirectResponse("/auth/first-run", status_code=302)

    # === Στάδιο B: RBAC (admin vs user) σε paths ===
    # (μόλις υπάρχουν users)
    user = _get_user(request)
    # Αν δεν έχει session, άστο να πέσει στο handler -> 401 -> θα το πιάσει ο exception handler
    if user and not user.is_admin:
        for pref in ADMIN_ONLY_PREFIXES:
            if p.startswith(pref):
                # Αν δεν είναι admin και πάει σε admin path, κόψ' τον ευγενικά
                return RedirectResponse("/", status_code=302)

    return await call_next(request)