# app/collector/save_eml.py (ή μέσα στο ίδιο module του collector)
from pathlib import Path
from app.core.config import DATA_DIR  # ή ορίζεις BASE_DIR/path μόνος σου

def save_eml_bytes(account: str, message_id: str, raw_bytes: bytes) -> str:
    safe_account = (account or "unknown").replace("/", "_")
    eml_dir = DATA_DIR / "eml" / safe_account
    eml_dir.mkdir(parents=True, exist_ok=True)
    fname = (message_id or "no-message-id").replace("/", "_").replace("<","").replace(">","")
    path = eml_dir / f"{fname}.eml"
    path.write_bytes(raw_bytes)
    return str(path)
