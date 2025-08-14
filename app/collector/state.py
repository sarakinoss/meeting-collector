from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import JobState, JobStatus

class CollectorState:
    def __init__(self):
        self.db: Session = SessionLocal()

    def set(self, status: JobStatus, message: str | None = None, progress: int | None = None):
        js = self.db.query(JobState).first()
        if not js:
            js = JobState()
            self.db.add(js)
        js.touch(status=status, message=message, progress=progress)
        if status == JobStatus.running:
            js.last_run = datetime.now(timezone.utc)
        self.db.commit()

    def close(self):
        self.db.close()