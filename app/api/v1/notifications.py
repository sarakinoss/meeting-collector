# app/api/v1/notifications.py
from __future__ import annotations
import re
import asyncio
import os, smtplib, ssl
from email.message import EmailMessage
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db.session import get_db, SessionLocal
from app.db.models import UserPreferences, Meeting, SentNotification
from app.api.deps import require_user

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

# ---- helpers ----
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")           # 'HH:MM'
_DAYS_OK = {"mon","tue","wed","thu","fri","sat","sun"}

TZ_NAME = "Europe/Athens"

def _csv_to_list(csv: str | None) -> List[str]:
    return [x for x in (csv or "").split(",") if x]

def _list_to_csv(lst: List[str] | None) -> str:
    return ",".join(lst or [])

def _ensure_prefs(db: Session, user_id: int) -> UserPreferences:
    row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).one_or_none()
    if row is None:
        row = UserPreferences(user_id=user_id, not_daily_hour="07:00", not_days="")
        db.add(row); db.commit(); db.refresh(row)
    return row

# ---- schemas ----
class NotifPrefsIn(BaseModel):
    not_daily_hour: str = Field(..., description="HH:MM (24h)")
    not_days: List[str] = Field(default_factory=list)
    not_prior_minutes: Optional[int] = Field(default=None, description="None/off or 5/10/15/30/60")

    not_smtp_host: Optional[str] = None
    not_smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    not_user_smtp: Optional[str] = None
    not_pass_smtp: Optional[str] = None

    not_receiver: Optional[EmailStr] = None

    def validate_all(self):
        if not _TIME_RE.match(self.not_daily_hour):
            raise ValueError("Invalid time format; expected HH:MM")
        bad = [d for d in self.not_days if d not in _DAYS_OK]
        if bad:
            raise ValueError(f"Invalid day(s): {bad}. Allowed: {sorted(_DAYS_OK)}")
        if self.not_prior_minutes is not None and self.not_prior_minutes not in (5,10,15,30,60):
            raise ValueError("not_prior_minutes must be 5,10,15,30,60 or null")

class NotifPrefsOut(BaseModel):
    not_daily_hour: str
    not_days: List[str]
    not_prior_minutes: Optional[int]

    not_smtp_host: Optional[str]
    not_smtp_port: Optional[int]
    not_user_smtp: Optional[str]
    # ΣΚΟΠΙΜΑ δεν επιστρέφουμε password για λόγους ασφάλειας
    not_pass_set: bool = False

    not_receiver: Optional[EmailStr]

# ---- routes ----
@router.get("", response_model=NotifPrefsOut)
def get_prefs(user=Depends(require_user), db: Session = Depends(get_db)):
    row = _ensure_prefs(db, user.id)
    return NotifPrefsOut(
        not_daily_hour=row.not_daily_hour,
        not_days=_csv_to_list(row.not_days),
        not_prior_minutes=row.not_prior_minutes,
        not_smtp_host=row.not_smtp_host,
        not_smtp_port=row.not_smtp_port,
        not_user_smtp=row.not_user_smtp,
        not_pass_set=bool(row.not_pass_smtp),
        not_receiver=row.not_receiver,
    )

@router.put("", response_model=NotifPrefsOut)
def save_prefs(payload: NotifPrefsIn, user=Depends(require_user), db: Session = Depends(get_db)):
    try:
        payload.validate_all()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    row = _ensure_prefs(db, user.id)
    row.not_daily_hour     = payload.not_daily_hour
    row.not_days           = _list_to_csv(payload.not_days)
    row.not_prior_minutes  = payload.not_prior_minutes

    row.not_smtp_host      = payload.not_smtp_host
    row.not_smtp_port      = payload.not_smtp_port
    row.not_user_smtp      = payload.not_user_smtp
    # Αν δοθεί νέο password, το αντικαθιστούμε· αν όχι, αφήνουμε το παλιό
    if payload.not_pass_smtp is not None:
        row.not_pass_smtp  = payload.not_pass_smtp

    row.not_receiver       = payload.not_receiver

    db.add(row); db.commit(); db.refresh(row)

    return NotifPrefsOut(
        not_daily_hour=row.not_daily_hour,
        not_days=_csv_to_list(row.not_days),
        not_prior_minutes=row.not_prior_minutes,
        not_smtp_host=row.not_smtp_host,
        not_smtp_port=row.not_smtp_port,
        not_user_smtp=row.not_user_smtp,
        not_pass_set=bool(row.not_pass_smtp),
        not_receiver=row.not_receiver,
    )



# --- helper για αποστολή ---
def _send_mail_via_smtp(
    host: str, port: int, username: str, password: str,
    sender: str, to: str, subject: str, body: str,
    auth_mode: str = "password",  # μελλοντικό hook για 'oauth2'
):
    if auth_mode == "oauth2":
        # TODO: υλοποίηση XOAUTH2 όταν προστεθούν tokens
        raise RuntimeError("OAuth2 not implemented yet")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as s:
            s.login(username, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            try:
                s.starttls(context=ssl.create_default_context())
            except smtplib.SMTPException:
                pass  # αν ο server δεν δέχεται STARTTLS προχώρα σκέτο
            s.login(username, password)
            s.send_message(msg)

# --- schema για test request ---
class NotifTestIn(BaseModel):
    to: Optional[EmailStr] = None

class NotifTestOut(BaseModel):
    ok: bool
    to: EmailStr

# --- route: δοκιμαστική αποστολή ---
@router.post("/test", response_model=NotifTestOut)
def test_send(
    payload: NotifTestIn = Body(default=None),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    row = _ensure_prefs(db, user.id)

    # Resolve SMTP (user prefs -> env defaults)
    host = row.not_smtp_host or os.getenv("NOTIF_SMTP_HOST")
    port = row.not_smtp_port or (int(os.getenv("NOTIF_SMTP_PORT", "0")) or None)
    usern = row.not_user_smtp or os.getenv("NOTIF_SMTP_USER")
    passwd = row.not_pass_smtp or os.getenv("NOTIF_SMTP_PASS")

    if not (host and port and usern and passwd):
        raise HTTPException(status_code=400, detail="Incomplete SMTP configuration")

    # Resolve receiver (prefs -> env -> smtp user)
    to = (payload.to or row.not_receiver or
          os.getenv("NOTIF_DEFAULT_RECEIVER") or usern)

    subject = "Meeting Collector – Test notification"
    body = (
        "Αυτό είναι δοκιμαστικό μήνυμα από το Meeting Collector.\n\n"
        "Η αποστολή έγινε επιτυχώς μέσω των ρυθμίσεων SMTP που έχουν οριστεί."
    )

    try:
        _send_mail_via_smtp(
            host=host, port=int(port), username=usern, password=passwd,
            sender=usern, to=to, subject=subject, body=body,
            auth_mode=os.getenv("NOTIF_SMTP_AUTH", "password")  # hook για oauth2 αργότερα
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP error: {e!s}")

    return NotifTestOut(ok=True, to=to)






class DailyNowOut(BaseModel):
    ok: bool
    to: EmailStr
    count: int
    date: str  # YYYY-MM-DD (local)

def _resolve_smtp_and_receiver(db, user):
    import os
    row = _ensure_prefs(db, user.id)
    host  = row.not_smtp_host or os.getenv("NOTIF_SMTP_HOST")
    port  = row.not_smtp_port or (int(os.getenv("NOTIF_SMTP_PORT", "0")) or None)
    usern = row.not_user_smtp or os.getenv("NOTIF_SMTP_USER")
    passwd= row.not_pass_smtp or os.getenv("NOTIF_SMTP_PASS")
    if not (host and port and usern and passwd):
        raise HTTPException(status_code=400, detail="Incomplete SMTP configuration")
    to = row.not_receiver or os.getenv("NOTIF_DEFAULT_RECEIVER") or usern
    return host, int(port), usern, passwd, to

def _today_range_utc(tz_name="Europe/Athens"):
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    start_local = datetime(now_local.year, now_local.month, now_local.day, 0, 0, tzinfo=tz)
    end_local   = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), start_local.date(), tz

@router.post("/daily-now", response_model=DailyNowOut)
def send_daily_summary_now(user=Depends(require_user), db: Session = Depends(get_db)):
    # 1) SMTP & receiver
    host, port, usern, passwd, to = _resolve_smtp_and_receiver(db, user)

    # 2) Meetings for "today" (Europe/Athens)
    start_utc, end_utc, day_local, tz = _today_range_utc("Europe/Athens")

    # Manual Test snippet
    # tz = ZoneInfo("Europe/Athens")
    # start_utc = datetime(2025, 9, 9, 0, 0, tzinfo=tz)
    # end_utc = start_utc + timedelta(days=1)


    rows = (
        db.query(Meeting)
        .filter(Meeting.start.isnot(None))
        .filter(Meeting.start >= start_utc, Meeting.start < end_utc)
        .order_by(Meeting.start.asc().nulls_last())
        .all()
    )

    # 3) Compose body (localize hours to Athens)
    if rows:
        lines = [f"Σύνοψη συναντήσεων για {day_local.isoformat()} (Europe/Athens)", ""]
        for m in rows:
            t = m.start.astimezone(tz).strftime("%H:%M") if m.start else "—"
            title = (m.title or "").strip() or "(χωρίς θέμα)"
            plat = (m.platform or "").strip()
            link = (m.link or "").strip()
            item = f"• {t} — {title}"
            if plat: item += f" [{plat}]"
            if link: item += f"\n   {link}"
            lines.append(item)
        lines.append("\n— Meeting Collector")
        body = "\n".join(lines)
        subj = f"Meeting Collector — Ημερήσια σύνοψη ({day_local.isoformat()})"
    else:
        body = (
            f"Ημερήσια σύνοψη για {day_local.isoformat()} (Europe/Athens)\n\n"
            "Δεν έχει οριστεί κανένα meeting για σήμερα προς το παρόν.\n\n— Meeting Collector"
        )
        subj = f"Meeting Collector — Ημερήσια σύνοψη ({day_local.isoformat()})"

    # 4) Send
    try:
        _send_mail_via_smtp(
            host=host, port=port, username=usern, password=passwd,
            sender=usern, to=to, subject=subj, body=body,
            auth_mode=os.getenv("NOTIF_SMTP_AUTH", "password")
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP error: {e!s}")

    return DailyNowOut(ok=True, to=to, count=len(rows), date=day_local.isoformat())

class RemindersNowOut(BaseModel):
    ok: bool
    to: EmailStr
    count: int
    target_local: str        # HH:MM
    window_local: tuple[str, str]  # (from,to) HH:MM
    sent_ids: List[int]

@router.post("/reminders-now", response_model=RemindersNowOut)
def send_reminders_now(user=Depends(require_user), db: Session = Depends(get_db)):
    # 1) SMTP & receiver
    host, port, usern, passwd, to = _resolve_smtp_and_receiver(db, user)

    # 2) Φόρτωσε προτιμήσεις (πόσα λεπτά πριν)
    prefs = _ensure_prefs(db, user.id)
    prior = prefs.not_prior_minutes
    if not prior:
        raise HTTPException(status_code=400, detail="Reminders are disabled (not_prior_minutes is null/off)")

    # 3) Υπολογισμός στόχου/παραθύρου στην Athens TZ
    tz = ZoneInfo("Europe/Athens")
    now_local = datetime.now(tz)
    # Manual Test
    # now_local = datetime(2025, 9, 24, 0, 0, tzinfo=tz)

    target_local = now_local + timedelta(minutes=prior)
    # ανοχή +/- 2 λεπτά για να «πιάσει» κοντινά starts
    tol = timedelta(minutes=15)
    win_start_local = target_local - tol
    win_end_local   = target_local + tol

    # Μετατροπή window σε UTC για το query
    win_start_utc = win_start_local.astimezone(timezone.utc)
    win_end_utc   = win_end_local.astimezone(timezone.utc)

    # 4) Βρες meetings που ξεκινούν μέσα στο παράθυρο
    rows = (
        db.query(Meeting)
        .filter(Meeting.start.isnot(None))
        .filter(Meeting.start >= win_start_utc, Meeting.start < win_end_utc)
        .order_by(Meeting.start.asc().nulls_last())
        .all()
    )

    sent_ids: List[int] = []

    # 5) Στείλε ένα email ανά meeting
    for m in rows:
        start_l = m.start.astimezone(tz) if m.start else None
        title   = (m.title or "").strip() or "(χωρίς θέμα)"
        plat    = (m.platform or "").strip()
        link    = (m.link or "").strip()

        # πόσα λεπτά απομένουν; (στρογγυλεμένα προς τα κάτω)
        remain_min = max(0, int((start_l - now_local).total_seconds() // 60)) if start_l else prior

        subject = f"Υπενθύμιση: {title} σε {remain_min}′ (στις {start_l.strftime('%H:%M') if start_l else '—'})"
        lines = [f"Υπενθύμιση meeting σε {remain_min} λεπτά."]
        if start_l:
            lines.append(f"Ώρα έναρξης: {start_l.strftime('%H:%M')} (Europe/Athens)")
        if plat:
            lines.append(f"Πλατφόρμα: {plat}")
        if link:
            lines.append(f"Σύνδεσμος: {link}")
        lines.append("\n— Meeting Collector")

        try:
            _send_mail_via_smtp(
                host=host, port=port, username=usern, password=passwd,
                sender=usern, to=to, subject=subject, body="\n".join(lines),
                auth_mode=os.getenv("NOTIF_SMTP_AUTH", "password")
            )
            sent_ids.append(m.id)
        except Exception as e:
            # Δεν «σπάμε» όλη τη διαδικασία για ένα failure — απλώς συνέχισε
            # (προαιρετικά: log)
            continue

    return RemindersNowOut(
        ok=True,
        to=to,
        count=len(sent_ids),
        target_local=target_local.strftime("%H:%M"),
        window_local=(win_start_local.strftime("%H:%M"), win_end_local.strftime("%H:%M")),
        sent_ids=sent_ids
    )


def _floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def _minute_bounds_utc(target_local_minute: datetime, tz: ZoneInfo):
    start_local = _floor_to_minute(target_local_minute)
    end_local   = start_local + timedelta(minutes=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def _get_user_prefs_with_reminders(db: Session):
    return db.query(UserPreferences).filter(UserPreferences.not_prior_minutes.isnot(None)).all()

def _resolve_smtp_for_row(row: UserPreferences):
    import os
    host  = row.not_smtp_host or os.getenv("NOTIF_SMTP_HOST")
    port  = row.not_smtp_port or (int(os.getenv("NOTIF_SMTP_PORT", "0")) or None)
    usern = row.not_user_smtp or os.getenv("NOTIF_SMTP_USER")
    passwd= row.not_pass_smtp or os.getenv("NOTIF_SMTP_PASS")
    if not (host and port and usern and passwd):
        raise RuntimeError("Incomplete SMTP configuration")
    to = row.not_receiver or os.getenv("NOTIF_DEFAULT_RECEIVER") or usern
    return host, int(port), usern, passwd, to

def reminders_tick_once():
    """Τρέχει ΜΙΑ φορά: βρίσκει τι πρέπει να σταλεί στο τρέχον λεπτό και το στέλνει μία φορά."""
    db = SessionLocal()
    try:
        tz = ZoneInfo(TZ_NAME)
        now_local = datetime.now(tz)
        #now_local = datetime(2025, 7, 23, 14, 54, tzinfo=tz)
        prefs_rows = _get_user_prefs_with_reminders(db)

        for prefs in prefs_rows:
            prior = prefs.not_prior_minutes
            if not prior:
                continue

            # στόχος = now + prior, «δεμένος» στο λεπτό
            target_local = _floor_to_minute(now_local + timedelta(minutes=prior))
            #target_local = datetime(2025, 7, 23, 17, 54, tzinfo=tz)
            ustart_utc, uend_utc = _minute_bounds_utc(target_local, tz)

            # Meetings που ξεκινούν ΣΕ ΑΥΤΟ το λεπτό
            meetings = (
                db.query(Meeting)
                  .filter(Meeting.start.isnot(None))
                  .filter(and_(Meeting.start >= ustart_utc, Meeting.start < uend_utc))
                  .order_by(Meeting.start.asc().nulls_last())
                  .all()
            )
            if not meetings:
                continue

            # SMTP resolve (per user prefs)
            try:
                host, port, usern, passwd, to = _resolve_smtp_for_row(prefs)
            except Exception:
                continue  # skip αυτόν τον χρήστη αν λείπουν SMTP

            for m in meetings:
                # Dedup: έχει σταλεί ήδη γι’ αυτό το meeting/χρήστη/λεπτό;
                exists = db.query(SentNotification).filter(
                    SentNotification.user_id == prefs.user_id,
                    SentNotification.meeting_id == m.id,
                    SentNotification.kind == "reminder",
                    SentNotification.scheduled_for == target_local.astimezone(timezone.utc)
                ).one_or_none()
                if exists:
                    continue

                # Compose
                start_l = m.start.astimezone(tz) if m.start else None
                remain_min = max(0, int((start_l - now_local).total_seconds() // 60)) if start_l else prior
                subject = f"Υπενθύμιση: {(m.title or '').strip() or '(χωρίς θέμα)'} σε {remain_min}′ (στις {start_l.strftime('%H:%M') if start_l else '—'})"
                lines = [
                    f"Υπενθύμιση meeting σε {remain_min} λεπτά.",
                    f"Ώρα έναρξης: {start_l.strftime('%H:%M')} ({TZ_NAME})" if start_l else "Ώρα έναρξης: —"
                ]
                if (m.platform or "").strip():
                    lines.append(f"Πλατφόρμα: {m.platform.strip()}")
                if (m.link or "").strip():
                    lines.append(f"Σύνδεσμος: {m.link.strip()}")
                lines.append("\n— Meeting Collector")

                try:
                    _send_mail_via_smtp(
                        host=host, port=port, username=usern, password=passwd,
                        sender=usern, to=to, subject=subject, body="\n".join(lines),
                        auth_mode=os.getenv("NOTIF_SMTP_AUTH", "password")
                    )
                    db.add(SentNotification(
                        user_id=prefs.user_id,
                        meeting_id=m.id,
                        kind="reminder",
                        scheduled_for=target_local.astimezone(timezone.utc),
                        sent_at=datetime.now(timezone.utc)
                    ))
                    db.commit()
                except Exception:
                    db.rollback()
                    # (προαιρετικά: log)
                    continue
    finally:
        db.close()

async def reminders_scheduler_loop():
    """Τρέχει για πάντα: συγχρονίζεται στην αρχή του κάθε λεπτού και καλεί το tick."""
    while True:
        now = datetime.now(timezone.utc)
        # ύπνος μέχρι την αρχή του επόμενου λεπτού
        sleep_s = 60 - (now.second + now.microsecond/1_000_000)
        await asyncio.sleep(max(0.01, sleep_s))
        reminders_tick_once()