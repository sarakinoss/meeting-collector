from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# App components
from app.db.init_db import init_db
from scheduler import start_scheduler

# Routers
from app.api.endpoints import router as api_router
from app.api.auth import router as auth_router
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import User

# Load secret key
#try:
from app.core.config import SESSION_SECRET
#except Exception:
    #SECRET_KEY = "dev-secret-change-me" # TODO: set from env

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

# static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# init DB (δημιουργεί tables αν λείπουν)
init_db()


def _no_users_exist() -> bool:
    with SessionLocal() as db:
        return db.execute(select(User.id).limit(1)).first() is None
# start scheduler (optional during early auth UI testing)
if not _no_users_exist():
    start_scheduler()

# include ΟΛΑ τα endpoints από ένα router (ΧΩΡΙΣ prefix)
# include routers (auth first so "/login" catches unauth'd navigation)
app.include_router(auth_router)     # έχει prefix /auth — δεν ακουμπά το /
app.include_router(api_router)      # εδώ ζει το /



@app.middleware("http")
async def first_run_redirect(request: Request, call_next):
    # Άφησε ελεύθερα τα /static και /auth/*
    p = request.url.path
    if p.startswith("/static") or p.startswith("/auth"):
        return await call_next(request)

    # Αν ΔΕΝ υπάρχουν χρήστες, στείλε ΟΛΟΥΣ στο /auth/first-run
    if _no_users_exist() and p != "/auth/first-run":
        return RedirectResponse("/auth/first-run", status_code=302)

    return await call_next(request)

@app.exception_handler(StarletteHTTPException)
async def auth_redirect_handler(request: Request, exc: StarletteHTTPException):
    # Αν endpoint σήκωσε 401 ΚΑΙ ο client ζητά HTML → redirect
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        dest = "/auth/first-run" if _no_users_exist() else "/auth/login"
        return RedirectResponse(dest, status_code=302)
    # API/JSON: κράτα το JSON 401
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)