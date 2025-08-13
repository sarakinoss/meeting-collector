
# ✅ main.py: Web Interface Server
# This is the entry point for your web application (built using FastAPI). It:

# Initializes the database (by calling init_db())

# Starts the background scheduler (start_scheduler())

# Exposes a web dashboard at / to view upcoming meetings.
# http://localhost:8080/
# → Displays HTML with a list of meetings from the database

# Expose a an API Endpoint 
#   GET http://localhost:8080/meetings

# main.py
# └── FastAPI App
#     ├── Startup
#     │   ├── init_db()
#     │   └── start_scheduler()
#     ├── GET /
#     │   └── Render HTML via Jinja2 (web/templates/index.html)
#     └── GET /meetings
#         └── Return JSON from SQLite: meetings.db


from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import sqlite3

from app.db import init_db, get_all_meetings_as_dict
from scheduler import start_scheduler

app = FastAPI()
templates = Jinja2Templates(directory="web/templates")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

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




