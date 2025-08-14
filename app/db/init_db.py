from __future__ import annotations
from sqlalchemy import inspect
from app.db.session import engine
from app.db.models import Base, JobState, JobName
from sqlalchemy.orm import Session

# Creates tables if not present and ensures a row for the collector job exists

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine, future=True) as db:
        if not db.get(JobState, 1):
            js = JobState(name=JobName.collector)
            db.add(js)
            db.commit()