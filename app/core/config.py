from __future__ import annotations
import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database URL — Postgres ready; falls back to SQLite for dev
# Example for Postgres: postgresql+psycopg://user:pass@localhost:5432/meetings
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/meetings.db")

# App identity (for ICS UID, etc.)
APP_ID = os.getenv("APP_ID", "meeting-collector")