import uvicorn
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.db.crud import get_all_meetings_as_dict, store_meetings_to_db
from scheduler import start_scheduler

from app.db.init_db import init_db
from app.api.status import router as status_router


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# Init DB tables (safe to call on every boot)
init_db()


# Templates & static
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# Routes
app.include_router(status_router)


@app.on_event("startup")
def startup():
    print("🚀 Starting Meeting Collector...")
    init_db()
    start_scheduler()

# Serve to webpage
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Get all meetings as key-values pairs structure
    meetings = get_all_meetings_as_dict()
    # Render meetings in html template.
    return templates.TemplateResponse("index.html", {"request": request, "meetings": meetings})

# API endpoint
#  GET http://localhost:8080/meetings
@app.get("/meetings", response_class=JSONResponse)
async def get_meetings():
    return get_all_meetings_as_dict()

#TODO add attributes/parameters on API Calls 

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)




