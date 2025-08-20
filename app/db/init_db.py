from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import inspect, select
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert
from app.db.session import engine, SessionLocal
from app.db.models import Base, JobState, JobName
from sqlalchemy.orm import Session

# Creates tables if not present and ensures a row for the collector job exists

# def init_db() -> None:
#     Base.metadata.create_all(bind=engine)
#     with Session(engine, future=True) as db:
#         if not db.get(JobState, 1):
#             js = JobState(name=JobName.collector)
#             db.add(js)
#             db.commit()

# def init_db():
#     Base.metadata.create_all(bind=engine)
#
#     now = datetime.now(timezone.utc)
#     with SessionLocal() as db:
#         stmt = insert(JobState).values(
#             name="collector",
#             status="idle",
#             message=None,
#             progress=0,
#             last_run=None,
#             updated_at=now,
#         )
#         # Αν υπάρχει ήδη row με ίδιο 'name', μην κάνεις τίποτα
#         stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
#         db.execute(stmt)
#         db.commit()

def init_db():
    Base.metadata.create_all(bind=engine)

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        exists = db.execute(
            select(JobState.id).where(JobState.name == "collector")
        ).first()
        if not exists:
            db.add(JobState(
                name="collector",
                status="idle",
                message=None,
                progress=0,
                last_run=None,
                updated_at=now
            ))
            try:
                db.commit()
            except IntegrityError:
                # Σε σπάνιο race condition (διπλή διεργασία) το αγνοούμε
                db.rollback()