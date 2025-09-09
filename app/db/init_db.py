from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import inspect, select
from sqlalchemy import select, text
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

# Τι κάνει το init
#
# Στο init_db.py, η init_db() καλεί μία φορά Base.metadata.create_all(bind=engine) ⇒ δημιουργεί ό,τι πίνακες λείπουν, δεν κάνει drop/επαν-αρχικοποίηση. Μετά εξασφαλίζει να υπάρχει ένα row στο job_state για το collector.
#
# Το Base και όλα τα μοντέλα είναι στο app.db.models και τα βλέπει το create_all. Άρα αν προσθέσουμε καινούργιο model εκεί, ο πίνακας θα δημιουργηθεί αυτόματα στο επόμενο init_db().
#
# Το engine/session ορίζονται κεντρικά στο session.py με create_engine(DATABASE_URL) και SessionLocal, οκ.

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


def dev_upgrade_schema_for_notifications_and_folders():
    """
    DEV-only helper: Φτιάχνει/συμπληρώνει τα απαραίτητα tables/στήλες ΧΩΡΙΣ migrations.
    Ασφαλές να τρέξει πολλές φορές (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
    """
    ddl = """
    -- 1) MailAccountFolderPref (νέος πίνακας)
    CREATE TABLE IF NOT EXISTS mail_account_folder_prefs (
        id               SERIAL PRIMARY KEY,
        user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        mail_account_id  INTEGER NOT NULL REFERENCES mail_accounts(id) ON DELETE CASCADE,
        folder           TEXT    NOT NULL,
        include          BOOLEAN NOT NULL DEFAULT TRUE,
        CONSTRAINT uq_mfp UNIQUE (user_id, mail_account_id, folder)
    );
    -- TODO: CREATE INDEX CONCURRENTLY idx_mfp_user_acc ON mail_account_folder_prefs(user_id, mail_account_id);

    -- 2) UserPreferences — πρόσθετες στήλες notifications/SMTP (ασφαλή if-not-exists)
    ALTER TABLE "userPreferences"
        ADD COLUMN IF NOT EXISTS not_prior_minutes INTEGER,
        ADD COLUMN IF NOT EXISTS not_smtp_host    VARCHAR(255),
        ADD COLUMN IF NOT EXISTS not_smtp_port    INTEGER,
        ADD COLUMN IF NOT EXISTS not_user_smtp    VARCHAR(255),
        ADD COLUMN IF NOT EXISTS not_pass_smtp    TEXT,
        ADD COLUMN IF NOT EXISTS not_receiver     VARCHAR(255);
    -- TODO: CREATE INDEX CONCURRENTLY idx_userprefs_user ON "userPreferences"(user_id);
    """

    with engine.begin() as conn:
        conn.execute(text(ddl))