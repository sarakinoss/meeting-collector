from __future__ import annotations
import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database URL — Postgres ready; falls back to SQLite for dev
# Example for Postgres: postgresql+psycopg://user:pass@localhost:5432/meetings
#DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/meetings.db")

# Master secret για κρυπτογράφηση δεδομένων (Fernet) και κρυπτογράφηση κωδικών
# CRYPTO_SECRET = σταθερό στον χρόνο (για να μπορείς να διαβάζεις παλιά encrypted πεδία).
CRYPTO_SECRET = os.getenv("CRYPTO_SECRET", "_c6mUul1I6pwipdaLr_AP_z4CAfsg0H9M7Rv3Vg64aXIizmLQRkEUF3X2jpQ_AGxHeNpDJCkEjy_DBgsENHO_Q")

# Secret για sessions (cookies)
# SESSION_SECRET = μπορεί να περιστραφεί πιο εύκολα (θα κάνει logout τους χρήστες, αλλά δεν σπάει δεδομένα).
SESSION_SECRET = os.getenv("SESSION_SECRET", "wMH6zk_YqmngApUMX55ydsLI0LZ8yQVBMIVmt1ToBzpDoNiv4mFZicfb5pEDjSICn3kC_qZATpQHLlNSdxoLsA")


# App identity (for ICS UID, etc.)
APP_ID = os.getenv("APP_ID", "meeting-collector")
# Database URL — Postgres
DATABASE_URL = "postgresql+psycopg://admin:Mp!n!ch!s@localhost:5432/meetings"



# 🔐 Master secret για κρυπτογράφηση κωδικών
#SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_LONG_RANDOM_SECRET")