from __future__ import annotations
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, Integer, Enum
from datetime import datetime, timezone
import enum

Base = declarative_base()

class JobName(str, enum.Enum):
    collector = "collector"

class JobStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    error = "error"
    stopped = "stopped"

class JobState(Base):
    __tablename__ = "job_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[JobName] = mapped_column(Enum(JobName), unique=True, index=True, default=JobName.collector)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.idle, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def touch(self, status: JobStatus | None = None, message: str | None = None, progress: int | None = None):
        if status is not None:
            self.status = status
        if message is not None:
            self.message = message
        if progress is not None:
            self.progress = progress
        self.updated_at = datetime.now(timezone.utc)

class Email(Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account: Mapped[str | None] = mapped_column(String(64))
    folder: Mapped[str | None] = mapped_column(String(256))
    message_id: Mapped[str | None] = mapped_column(String(512), unique=True, index=True)
    subject: Mapped[str | None] = mapped_column(Text)
    sender: Mapped[str | None] = mapped_column(Text)
    recipients: Mapped[str | None] = mapped_column(Text)
    internaldate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eml_path: Mapped[str | None] = mapped_column(Text)
    has_calendar: Mapped[bool] = mapped_column(Boolean, default=False)

class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str | None] = mapped_column(String(512), index=True)  # normalized meeting id or ICS UID
    platform: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    organizer: Mapped[str | None] = mapped_column(Text)
    attendees: Mapped[str | None] = mapped_column(Text)
    parse_reason: Mapped[str | None] = mapped_column(String(32))
    parse_snippet: Mapped[str | None] = mapped_column(Text)
    last_msg_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class MeetingEmail(Base):
    __tablename__ = "meeting_emails"
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), primary_key=True)
    role: Mapped[str | None] = mapped_column(String(16))  # invite/update/cancel