from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

# Dependency for FastAPI routes
from typing import Iterator

def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()