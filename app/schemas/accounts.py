from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field

class AccountIn(BaseModel):
    display_name: str | None = None
    email: EmailStr
    # IMAP (required for parsing)
    imap_host: str
    imap_port: int = 993
    imap_ssl: bool = True
    imap_user: str | None = None
    imap_password: str = Field(min_length=1)
    # SMTP (optional, for confirmations later)
    smtp_host: str | None = None
    smtp_port: int | None = 465
    smtp_ssl: bool | None = True
    smtp_user: str | None = None
    smtp_password: str | None = None
    # Flags
    can_parse: bool = True
    can_send: bool = False
    enabled: bool = True

class AccountOut(BaseModel):
    id: int
    display_name: str | None
    email: EmailStr
    imap_host: str | None
    imap_port: int | None
    imap_ssl: bool | None
    imap_user: str | None
    smtp_host: str | None
    smtp_port: int | None
    smtp_ssl: bool | None
    smtp_user: str | None
    can_parse: bool
    can_send: bool
    enabled: bool

    class Config:
        from_attributes = True