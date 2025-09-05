from __future__ import annotations
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, Integer, Enum
from datetime import datetime, timezone
import enum

Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    sso_provider: Mapped[str | None] = mapped_column(String(32))
    sso_subject: Mapped[str | None] = mapped_column(String(128))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class MailAccount(Base):
    __tablename__ = "mail_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    display_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    # IMAP (parsing)
    imap_host: Mapped[str | None] = mapped_column(String(255))
    imap_port: Mapped[int | None] = mapped_column(Integer, default=993)
    imap_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    imap_user: Mapped[str | None] = mapped_column(String(128))
    imap_password_enc: Mapped[str | None] = mapped_column(Text)

    # SMTP (confirmations)
    smtp_host: Mapped[str | None] = mapped_column(String(255))
    smtp_port: Mapped[int | None] = mapped_column(Integer, default=465)
    smtp_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_user: Mapped[str | None] = mapped_column(String(128))
    smtp_password_enc: Mapped[str | None] = mapped_column(Text)

    # Flags / ownership
    can_parse: Mapped[bool] = mapped_column(Boolean, default=True)
    can_send: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    owner: Mapped[str | None] = mapped_column(String(128))  # optional, for future SSO mapping

    last_full_parse_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_incremental_parse_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class UserMailAccess(Base):
    __tablename__ = "user_mail_access"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    mail_account_id: Mapped[int] = mapped_column(ForeignKey("mail_accounts.id"), primary_key=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    can_parse: Mapped[bool] = mapped_column(Boolean, default=True)
    can_send: Mapped[bool] = mapped_column(Boolean, default=False)

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

class UserPreferences(Base):
    __tablename__ = "userPreferences"  # όπως ζήτησες

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    # Notifications: daily summary
    not_daily_hour: Mapped[str]  = mapped_column(String(5), nullable=False, default="09:00")  # 'HH:MM'
    not_days:       Mapped[str]  = mapped_column(Text, nullable=False, default="")           # CSV: 'mon,tue,...'

    # Notifications: reminder πριν το meeting
    not_prior_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)             # NULL = off

    # SMTP account per user (προαιρετικά πεδία)
    not_smtp_host:     Mapped[str | None] = mapped_column(String(255))
    not_smtp_port:     Mapped[int | None] = mapped_column(Integer)
    not_user_smtp:     Mapped[str | None] = mapped_column(String(255))
    not_pass_smtp:     Mapped[str | None] = mapped_column(Text)  # (μπορούμε αργότερα να το κάνουμε *_enc)

    # Προαιρετικά: security mode (none/ssl/starttls)
    # not_smtp_security: Mapped[str] = mapped_column(String(16), nullable=False, default="none")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))