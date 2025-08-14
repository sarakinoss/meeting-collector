from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, select, inspect
from app.db.session import get_db
from app.db.models import JobState, Meeting

router = APIRouter()

@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    js = db.query(JobState).first()
    #total_meetings = db.query(func.count(Meeting.id)).scalar() if db.bind.has_table("meetings") else 0

    #total_meetings = db.execute(select(func.count(Meeting.id))).scalar() or 0

    ins = inspect(db.get_bind())
    if ins.has_table(Meeting.__tablename__):
        total_meetings = db.execute(select(func.count(Meeting.id))).scalar() or 0
    else:
        total_meetings = 0

    return {
        "collector": {
            "status": js.status if js else "idle",
            "message": js.message if js else None,
            "progress": js.progress if js else 0,
            "last_run": js.last_run.isoformat() if js and js.last_run else None,
            "updated_at": js.updated_at.isoformat() if js else None,
        },
        "counts": {"meetings": total_meetings},
    }