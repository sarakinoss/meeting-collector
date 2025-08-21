import re
import email
import socket
import logging

from bs4 import BeautifulSoup

from datetime import datetime, timezone, timedelta
from dateutil import tz, parser as dateparser

from email.header import decode_header
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.db.models import MailAccount, UserMailAccess
from app.db.session import SessionLocal

from app.core.crypto import decrypt
from app.collector.save_eml import save_eml_bytes

from email.utils import parsedate_to_datetime
from app.db.session import SessionLocal
from app.db.models import Email, Meeting
from app.db import crud


# TODO Mark found email with meetings as RED in order to distiguish at a glance.
# TODO For the same meeting ID it has to keep the last message meeting date like sent@16/4/25, 08:50 Libra

MODE = "SINCE"  # or "UNSEEN" or "SINCE" or "ALL"
# TODO Grab last parsing date from database to avoid full mailbox parse and set it to SINCE_DATE
SINCE_DATE = "01-Jun-2024"
UNTIL_DATE = datetime.now().strftime("%d-%b-%Y")


def get_active_imap_accounts(db: Session) -> list[MailAccount]:
    q = select(MailAccount).where(MailAccount.enabled == True, MailAccount.can_parse == True,
                                  MailAccount.imap_host != None)
    return db.execute(q).scalars().all()


def extract_meetings_all_accounts(*, force_full: bool = False) -> list[dict]:
    results: list[dict] = []
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        accounts = get_active_imap_accounts(db)
        for acc in accounts:
            since = None if force_full else (acc.last_incremental_parse_at or acc.last_full_parse_at)
            # Fallback: your existing default SINCE_DATE if both None
            acc_email = acc.email
            host, port, use_ssl = acc.imap_host, (acc.imap_port or 993), bool(acc.imap_ssl)
            username = acc.imap_user or acc.email
            # password = decrypt(acc.imap_password_enc) or ""
            # ΜΕΤΑ (safe fallback)
            raw = acc.imap_password_enc or ""
            looks_like_fernet = raw.startswith("gAAAA")  # αρκεί ως cheap heuristic
            password = decrypt(raw) if looks_like_fernet else raw

            # Use existing function that parses one account, parameterize creds
            meetings = extract_meetings_for_account(
                email_address=acc_email,
                imap_host=host,
                imap_port=port,
                imap_ssl=use_ssl,
                imap_user=username,
                imap_password=password,
                since_dt=since,
            )
            # # merge into global results (your existing format)
            # for k, v in meetings.items():
            #     results[k] = v

            results.extend(meetings)

            # update per-account incremental timestamp on success
            acc.last_incremental_parse_at = now
            db.add(acc)
        db.commit()
    return results


# -- Logging Setup --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("meeting_collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


# def get_imap_accounts_for_parsing(db, *, user_id: int | None = None) -> list[MailAccount]:
#     q = select(MailAccount).where(
#         MailAccount.enabled.is_(True),
#         MailAccount.can_parse.is_(True),
#         MailAccount.imap_host.is_not(None),
#     )
#     if user_id is not None:
#         q = (
#             select(MailAccount)
#             .join(UserMailAccess, UserMailAccess.mail_account_id == MailAccount.id)
#             .where(
#                 UserMailAccess.user_id == user_id,
#                 UserMailAccess.can_parse.is_(True),
#                 MailAccount.enabled.is_(True),
#                 MailAccount.can_parse.is_(True),
#                 MailAccount.imap_host.is_not(None),
#             )
#         )
#     return db.execute(q).scalars().all()


def extract_meetings_for_account(*,
                                 email_address: str,
                                 imap_host: str,
                                 imap_port: int = 993,
                                 imap_ssl: bool = True,
                                 imap_user: str | None = None,
                                 imap_password: str = "",
                                 since_dt: datetime | None = None,
                                 ):
    meetings = []
    meetings_by_id = {}  # New dictionary to group by meeting ID

    # Effective SINCE date string for IMAP (fallback to existing constant)
    effective_since = None
    if since_dt is not None:
        try:
            effective_since = since_dt.strftime("%d-%b-%Y")
        except Exception:
            effective_since = None

    # Iterate email accounts
    # for acc in load_accounts_from_file():
    login_user = (imap_user or email_address)
    if not imap_password:
        logging.error(f"❌ Empty IMAP password after decryption for {email_address}. Check encryption/CRYPTO_SECRET.")
        return []

    logging.info(f"\n🔍 Connecting to {email_address} via {imap_host}:{imap_port} ssl={imap_ssl}")
    try:
        # 1) Άνοιξε IMAP με σωστό port/ssl
        # with IMAPClient(imap_host, port=imap_port, ssl=imap_ssl) as mail:
        with IMAPClient(imap_host) as mail:

            mail.login(email_address, imap_password)

            # # 2) Κάνε login με imap_user (fallback στο email αν αποτύχει)
            # try:
            #     mail.login(login_user, imap_password)
            # except Exception as e1:
            #     if login_user != email_address:
            #         logging.warning(f"⚠️ Login failed with '{login_user}', retrying with '{email_address}': {e1}")
            #         mail.login(email_address, imap_password)
            #     else:
            #         raise

            # helpful diagnostics
            try:
                logging.info(f"Capabilities: {mail.capabilities()}")
                try:
                    logging.info(f"Namespaces: {mail.namespace()}")
                except Exception:
                    pass
            except Exception:
                pass

            # time.sleep(2.5)
            folders = mail.list_folders()

            def is_selectable(flags: tuple[str, ...] | list[str]) -> bool:
                # Αν περιέχει \Noselect δεν είναι “ανοίξιμος”
                flags_lower = {f.lower() for f in flags or []}
                return r'\noselect' not in flags_lower

            # (προαιρετικό) ρυθμιζόμενη whitelist
            preferred = {
                "INBOX",
                "[Gmail]/All Mail", "[Gmail]/Sent Mail", "[Gmail]/Important", "[Gmail]/Starred",
                "Sent", "Archive"
            }
            # Iterate account folders and subfolders with their flags and delimiters
            # Flags: \\HasChildren, \\HasNoChildren \\Flagged \\Junk
            # Delimiter /
            for flags, delimiter, folder_name in folders:
                if not is_selectable(flags):
                    # π.χ. [Gmail] container → skip
                    logging.debug(f"Skipping noselection folder: {folder_name} {flags}")
                    continue
                # logging.info(f"\n📁 Folder: {folder_name}")

                # if folder_name != "INBOX":
                #     continue  # ❌ skip subfolders

                # (προαιρετικό) Αν θες να περιορίσεις:
                # if preferred and folder_name not in preferred:
                #     continue

                try:
                    try:
                        mail.select_folder(folder_name, readonly=True)
                        # print(f"✅ Accessed: {folder_name}")
                    except Exception as e:
                        print(f"⚠️ Failed to access {folder_name}: {e}")
                        continue

                    # # Choose mode
                    # if MODE == "ALL":
                    #     data = mail.search(["ALL"])
                    # elif MODE == "UNSEEN":
                    #     data = mail.search(["UNSEEN"])
                    # elif MODE == "SINCE":
                    #     # data = mail.search(f'(SINCE "{SINCE_DATE}")')
                    #     # data = mail.search(["SINCE", SINCE_DATE])
                    #     data = mail.search(["SEEN", "SINCE", SINCE_DATE])
                    #     # data = mail.search(["SINCE", SINCE_DATE, "BEFORE", UNTIL_DATE])
                    #     # result, data = mail.search(None, f'(SINCE "01-Jun-2025" BEFORE "25-Jun-2025")')
                    # else:
                    #     raise ValueError(f"Invalid mode: {MODE}")
                    # # 5) Χρησιμοποίησε το effective_since στο search (αλλιώς ALL)
                    # if effective_since:
                    #     # Παράδειγμα: μόνο SEEN από since-date (ή άλλα κριτήρια αν θέλεις)
                    #     data = mail.search(["SINCE", effective_since])
                    #     # π.χ. μόνο UNSEEN από since:
                    #     # data = mail.search(["UNSEEN", "SINCE", effective_since])
                    # else:
                    #     data = mail.search(["ALL"])
                    #
                    # if not data:
                    #     continue

                    # Effective SINCE date
                    since_crit = None
                    if since_dt is not None:
                        try:
                            since_crit = since_dt.date()  # ← ΣΗΜΑΝΤΙΚΟ: date, όχι '20-Aug-2025' string
                        except Exception:
                            since_crit = None

                    # ...
                    if since_crit:
                        # π.χ. μόνο UNSEEN από since
                        ids = mail.search(["UNSEEN", "SINCE", since_crit])
                    else:
                        ids = mail.search(["ALL"])

                    if not ids:
                        continue

                    #  Start parsing mail content with header infos
                    if ids:
                        messages = mail.fetch(ids, ["BODY.PEEK[]"])
                        for msg_id, body_data in messages.items():
                            body = body_data.get(b'BODY[]') or body_data.get(b'BODY.PEEK[]')
                            if not body:
                                logging.warning(f"⚠️ No body for message ID {msg_id}")
                                continue

                            msg = email.message_from_bytes(body)

                            # Metadata
                            # subject = msg.get("Subject", "No Subject")

                            # Subject Extract - Method 1 (Works)
                            subject = decode_mime_header(msg.get("Subject", "No Subject"))
                            # Subject Extract - Method 2 (Also Works)
                            # subject = clean_subject(msg.get("Subject", "No Subject"))

                            msg_date = msg.get("Date", "")
                            sender = msg.get("From", "")
                            to = decode_mime_header(msg.get("To", ""))
                            cc = decode_mime_header(msg.get("Cc", ""))
                            bcc = decode_mime_header(msg.get("Bcc", ""))
                            msg_attendants = ", ".join(filter(None, [to, cc, bcc]))
                            message_id = msg.get("Message-ID", "")

                            # Extract body
                            body = ""

                            text_body = ""
                            html_body = ""

                            if msg.is_multipart():
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    charset = part.get_content_charset() or "utf-8"
                                    try:
                                        # if content_type == "text/plain" and not text_body:
                                        #     text_body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                        # elif content_type == "text/html" and not html_body:
                                        #     html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                        if content_type == "text/plain":
                                            text_body += part.get_payload(decode=True).decode(charset, errors="ignore")
                                        elif content_type == "text/html":
                                            html_body += part.get_payload(decode=True).decode(charset, errors="ignore")
                                    except Exception:
                                        continue
                            else:
                                # If it's not multipart, treat as plain text
                                try:
                                    text_body = msg.get_payload(decode=True).decode(errors="ignore")
                                except Exception:
                                    pass

                            # Match meetings based on patterns
                            platform = None
                            link = None
                            meeting_id = None

                            # search_source = text_body or html_body # Choose the first non empty
                            search_source = (text_body or "") + "\n" + (html_body or "")  # Concat both

                            for plat, pat in meeting_patterns.items():
                                # match = re.search(pat, body)
                                match = re.search(pat, search_source)
                                if match:
                                    platform = plat
                                    link = match.group(0)
                                    meeting_id = link.split("/")[-1].split("?")[0]
                                    # break

                                    # fallback for teams ID from body text
                                    if platform == "teams" and meeting_id == "0":
                                        id_match = re.search(r"Meeting ID:\s*([\d\s]+)", search_source)
                                        if id_match:
                                            meeting_id = id_match.group(1).replace(" ", "")
                                    break

                            # For mails that contain meeting link
                            if link:

                                logging.info(f"✅ Meeting found: {link} \n @ {folder_name}")

                                meet_date = extract_meet_date(msg, text_body, html_body)

                                # --- Save EML + upsert Email row (for preview/download) ---
                                try:
                                    # 1) save raw .eml
                                    eml_path = save_eml_bytes(email_address, message_id, body)

                                    # 2) upsert Email in DB
                                    try:
                                        received_dt = dateparser.parse(msg_date) if msg_date else None
                                    except Exception:
                                        received_dt = None

                                    with SessionLocal() as db:
                                        row = db.execute(select(Email).where(
                                            Email.message_id == message_id)).scalar_one_or_none()
                                        if row is None:
                                            row = Email(message_id=message_id)
                                            db.add(row)

                                        row.account = email_address
                                        row.folder = folder_name
                                        row.subject = subject
                                        row.sender = sender
                                        row.recipients = msg_attendants
                                        row.internaldate = None  # δεν το έχουμε εδώ από IMAPClient
                                        row.received_at = received_dt  # από το Date header
                                        row.has_calendar = True  # εδώ είμαστε σε mail με meeting link
                                        row.eml_path = eml_path  # ★ σημαντικό για preview/download

                                        db.commit()
                                except Exception as e:
                                    logging.warning(f"EML save/upsert failed for {message_id}: {e}")
                                # --- end EML upsert ---

                                # Parse the message's date (for comparison) to datetime
                                try:
                                    msg_datetime = dateparser.parse(msg_date)
                                except Exception:
                                    msg_datetime = None

                                if meeting_id not in meetings_by_id:
                                    # First time seeing this meeting_id
                                    meetings_by_id[meeting_id] = {
                                        "msg_account": email_address,
                                        "msg_folder": folder_name,
                                        "msg_id": message_id,
                                        "msg_date": msg_date,
                                        "msg_subject": subject,
                                        "msg_sender": sender,
                                        "msg_attendants": msg_attendants,
                                        "meet_platform": platform,
                                        "meet_id": meeting_id,
                                        "meet_attendants": extract_clean_meet_attendants(text_body + html_body),
                                        "meet_date": meet_date,
                                        "meet_link": link,
                                        "related_messages": [message_id]
                                    }
                                else:
                                    existing = meetings_by_id[meeting_id]
                                    existing_date = existing.get("meet_date")
                                    try:
                                        existing_datetime = dateparser.parse(existing_date) if existing_date else None
                                    except Exception:
                                        existing_datetime = None

                                    # Update only if new message has a newer date
                                    if not existing_datetime or (msg_datetime and msg_datetime > existing_datetime):
                                        existing.update({
                                            "msg_folder": folder_name,
                                            "msg_id": message_id,
                                            "msg_date": msg_date,
                                            "msg_subject": subject,
                                            "msg_sender": sender,
                                            "msg_attendants": msg_attendants,
                                            "meet_date": meet_date,
                                            "meet_link": link
                                        })

                                    # Always track the message as related
                                    existing["related_messages"].append(message_id)

                except Exception as e:
                    logging.warning(f"⚠️ Error accessing folder '{folder_name}': {e}")

    except Exception as e:
        logging.warning(f"❌ Connection error with {email_address}: {e}")

    except IMAPClientError as e:
        print("IMAP error:", e)

    except socket.gaierror as e:
        print("Network error (DNS or host not found):", e)

    # Final collected results
    meetings = list(meetings_by_id.values())
    return meetings

# helper για ημερομηνίες (αν είναι string)
def _to_dt(s):
    if not s: return None
    try:
        dt = dateparser.parse(s)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

import re
_uuid_like = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}@.+$", re.I)

def canonicalize_attendees(s: str | None) -> str | None:
    if not s: return None
    parts = [p.strip() for p in s.split(",")]
    parts = [p for p in parts if not _uuid_like.match(p)]
    # αφαιρέσεις διπλότυπα, μικροκαθαρισμοί
    seen = set(); out = []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return ", ".join(out) if out else None

# def extract_meetings():
#     meetings = []
#     meetings_by_id = {}  # New dictionary to group by meeting ID
#
#     # Iterate email accounts
#     for acc in load_accounts_from_file():
#         logging.info(f"\n🔍 Connecting to {acc['email']}")
#         try:
#             with IMAPClient(acc["host"]) as mail:
#                 mail.login(acc["email"], acc["password"])
#
#                 # time.sleep(2.5)
#                 folders = mail.list_folders()
#
#                 # Iterate account folders and subfolders with their flags and delimiters
#                 # Flags: \\HasChildren, \\HasNoChildren \\Flagged \\Junk
#                 # Delimiter /
#                 for  flags, delimiter, folder_name in folders:
#                     #logging.info(f"\n📁 Folder: {folder_name}")
#
#                     # if folder_name != "INBOX":
#                     #     continue  # ❌ skip subfolders
#
#                     try:
#                         try:
#                             mail.select_folder(folder_name, readonly=True)
#                             #print(f"✅ Accessed: {folder_name}")
#                         except Exception as e:
#                             print(f"⚠️ Failed to access {folder_name}: {e}")
#
#                         # Choose mode
#                         if MODE == "ALL":
#                             data = mail.search(["ALL"])
#                         elif MODE == "UNSEEN":
#                             data = mail.search(["UNSEEN"])
#                         elif MODE == "SINCE":
#                             # data = mail.search(f'(SINCE "{SINCE_DATE}")')
#                             # data = mail.search(["SINCE", SINCE_DATE])
#                             data = mail.search(["SEEN", "SINCE", SINCE_DATE])
#                             #data = mail.search(["SINCE", SINCE_DATE, "BEFORE", UNTIL_DATE])
#                             # result, data = mail.search(None, f'(SINCE "01-Jun-2025" BEFORE "25-Jun-2025")')
#                         else:
#                             raise ValueError(f"Invalid mode: {MODE}")
#
#                         #  Start parsing mail content with header infos
#                         if data:
#                             messages = mail.fetch(data, ["BODY.PEEK[]"])
#                             for msg_id, body_data in messages.items():
#                                 body = body_data.get(b'BODY[]') or body_data.get(b'BODY.PEEK[]')
#                                 if not body:
#                                     logging.warning(f"⚠️ No body for message ID {msg_id}")
#                                     continue
#
#                                 msg = email.message_from_bytes(body)
#
#                                 # Metadata
#                                 #subject = msg.get("Subject", "No Subject")
#
#                                 #Subject Extract - Method 1 (Works)
#                                 subject = decode_mime_header(msg.get("Subject", "No Subject"))
#                                 #Subject Extract - Method 2 (Also Works)
#                                 #subject = clean_subject(msg.get("Subject", "No Subject"))
#
#                                 msg_date = msg.get("Date", "")
#                                 sender = msg.get("From", "")
#                                 to = decode_mime_header( msg.get("To", "") )
#                                 cc = decode_mime_header( msg.get("Cc", "") )
#                                 bcc = decode_mime_header( msg.get("Bcc", "") )
#                                 msg_attendants = ", ".join(filter(None, [to, cc, bcc]))
#                                 message_id = msg.get("Message-ID", "")
#
#                                 # Extract body
#                                 body = ""
#
#                                 text_body = ""
#                                 html_body = ""
#
#                                 if msg.is_multipart():
#                                     for part in msg.walk():
#                                         content_type = part.get_content_type()
#                                         charset = part.get_content_charset() or "utf-8"
#                                         try:
#                                             # if content_type == "text/plain" and not text_body:
#                                             #     text_body = part.get_payload(decode=True).decode(charset, errors="ignore")
#                                             # elif content_type == "text/html" and not html_body:
#                                             #     html_body = part.get_payload(decode=True).decode(charset, errors="ignore")
#                                             if content_type == "text/plain":
#                                                 text_body += part.get_payload(decode=True).decode(charset, errors="ignore")
#                                             elif content_type == "text/html":
#                                                 html_body += part.get_payload(decode=True).decode(charset, errors="ignore")
#                                         except Exception:
#                                             continue
#                                 else:
#                                     # If it's not multipart, treat as plain text
#                                     try:
#                                         text_body = msg.get_payload(decode=True).decode(errors="ignore")
#                                     except Exception:
#                                         pass
#
#                                 # Match meetings based on patterns
#                                 platform = None
#                                 link = None
#                                 meeting_id = None
#
#                                 #search_source = text_body or html_body # Choose the first non empty
#                                 search_source = (text_body or "") + "\n" + (html_body or "") # Concat both
#
#                                 for plat, pat in meeting_patterns.items():
#                                     #match = re.search(pat, body)
#                                     match = re.search(pat, search_source)
#                                     if match:
#                                         platform = plat
#                                         link = match.group(0)
#                                         meeting_id = link.split("/")[-1].split("?")[0]
#                                         #break
#
#                                         # fallback for teams ID from body text
#                                         if platform == "teams" and meeting_id == "0":
#                                             id_match = re.search(r"Meeting ID:\s*([\d\s]+)", search_source)
#                                             if id_match:
#                                                 meeting_id = id_match.group(1).replace(" ", "")
#                                         break
#
#                                 # For mails that contain meeting link
#                                 if link:
#
#                                     logging.info(f"✅ Meeting found: {link} \n @ {folder_name}")
#
#                                     meet_date = extract_meet_date(msg, text_body, html_body)
#
#                                     # --- Save EML + upsert Email row (for preview/download) ---
#                                     try:
#                                         # 1) save raw .eml
#                                         eml_path = save_eml_bytes(acc["email"], message_id, body)
#
#                                         # 2) upsert Email in DB
#                                         try:
#                                             received_dt = dateparser.parse(msg_date) if msg_date else None
#                                         except Exception:
#                                             received_dt = None
#
#                                         with SessionLocal() as db:
#                                             row = db.execute(select(Email).where(
#                                                 Email.message_id == message_id)).scalar_one_or_none()
#                                             if row is None:
#                                                 row = Email(message_id=message_id)
#                                                 db.add(row)
#
#                                             row.account = acc["email"]
#                                             row.folder = folder_name
#                                             row.subject = subject
#                                             row.sender = sender
#                                             row.recipients = msg_attendants
#                                             row.internaldate = None  # δεν το έχουμε εδώ από IMAPClient
#                                             row.received_at = received_dt  # από το Date header
#                                             row.has_calendar = True  # εδώ είμαστε σε mail με meeting link
#                                             row.eml_path = eml_path  # ★ σημαντικό για preview/download
#
#                                             db.commit()
#                                     except Exception as e:
#                                         logging.warning(f"EML save/upsert failed for {message_id}: {e}")
#                                     # --- end EML upsert ---
#
#                                     # Parse the message's date (for comparison) to datetime
#                                     try:
#                                         msg_datetime = dateparser.parse(msg_date)
#                                     except Exception:
#                                         msg_datetime = None
#
#                                     if meeting_id not in meetings_by_id:
#                                         # First time seeing this meeting_id
#                                         meetings_by_id[meeting_id] = {
#                                             "msg_account": acc["email"],
#                                             "msg_folder": folder_name,
#                                             "msg_id": message_id,
#                                             "msg_date": msg_date,
#                                             "msg_subject": subject,
#                                             "msg_sender": sender,
#                                             "msg_attendants": msg_attendants,
#                                             "meet_platform": platform,
#                                             "meet_id": meeting_id,
#                                             "meet_attendants": extract_clean_meet_attendants(text_body + html_body),
#                                             "meet_date": meet_date,
#                                             "meet_link": link,
#                                             "related_messages": [message_id]
#                                         }
#                                     else:
#                                         existing = meetings_by_id[meeting_id]
#                                         existing_date = existing.get("meet_date")
#                                         try:
#                                             existing_datetime = dateparser.parse(existing_date) if existing_date else None
#                                         except Exception:
#                                             existing_datetime = None
#
#                                         # Update only if new message has a newer date
#                                         if not existing_datetime or (msg_datetime and msg_datetime > existing_datetime):
#                                             existing.update({
#                                                 "msg_folder": folder_name,
#                                                 "msg_id": message_id,
#                                                 "msg_date": msg_date,
#                                                 "msg_subject": subject,
#                                                 "msg_sender": sender,
#                                                 "msg_attendants": msg_attendants,
#                                                 "meet_date": meet_date,
#                                                 "meet_link": link
#                                             })
#
#                                         # Always track the message as related
#                                         existing["related_messages"].append(message_id)
#
#                     except Exception as e:
#                         logging.warning(f"⚠️ Error accessing folder '{folder_name}': {e}")
#
#         except Exception as e:
#             logging.warning(f"❌ Connection error with {acc['email']}: {e}")
#
#         except IMAPClientError as e:
#             print("IMAP error:", e)
#
#         except socket.gaierror as e:
#             print("Network error (DNS or host not found):", e)
#
#
#     # Final collected results
#     meetings = list(meetings_by_id.values())
#     return meetings

# -- Meeting Patterns --
meeting_patterns = {
    "teams": r"https://teams\.microsoft\.com/l/meetup-join/[\w\-\%\?\=\&\/\.:]+",
    "zoom": r"https://[a-zA-Z0-9_.]*zoom\.us/j/[0-9\?\=a-zA-Z0-9_\-&]+",
    "google": r"https://meet\.google\.com/[a-z\-]+"
}


def extract_meet_date(msg, text_body, html_body):
    LOCAL_TZ = tz.gettz("Europe/Athens")

    def norm(s: str) -> str:
        if not s:
            return ""
        s = (s.replace("&nbsp;", " ")
             .replace("\u200b", "")
             .replace("\xa0", " ")
             .replace("–", "-"))  # normalize en-dash to hyphen
        # Greek AM/PM → English
        s = re.sub(r"\bπ\.?\s*μ\.?\b", "AM", s, flags=re.IGNORECASE)
        s = re.sub(r"\bμ\.?\s*μ\.?\b", "PM", s, flags=re.IGNORECASE)
        return s

    greek_to_english = {
        "Δευτέρα": "Monday", "Τρίτη": "Tuesday", "Τετάρτη": "Wednesday", "Πέμπτη": "Thursday",
        "Παρασκευή": "Friday", "Σάββατο": "Saturday", "Κυριακή": "Sunday",
        "Ιανουαρίου": "January", "Φεβρουαρίου": "February", "Μαρτίου": "March", "Απριλίου": "April",
        "Μαΐου": "May", "Ιουνίου": "June", "Ιουλίου": "July", "Αυγούστου": "August",
        "Σεπτεμβρίου": "September", "Οκτωβρίου": "October", "Νοεμβρίου": "November", "Δεκεμβρίου": "December",
    }

    def gr2en(s: str) -> str:
        for gr, en in greek_to_english.items():
            s = re.sub(rf"\b{gr}\b", en, s)
        return s

    # Collect candidate text (plain, html text, hidden blocks unwrapped)
    candidates = []
    if text_body:
        candidates.append(norm(text_body))
    if html_body:
        candidates.append(norm(html_body))
        soup = BeautifulSoup(html_body, "html.parser")
        for tag in soup.find_all(style=True):
            if "display:none" in (tag.get("style") or "").replace(" ", "").lower():
                tag.unwrap()
        for tag in soup.find_all("details"):
            tag.unwrap()
        candidates.append(norm(soup.get_text(separator="\n")))

    # Pre-compile the range splitter (fixes previous use of flags= in re.split)
    _range_splitter = re.compile(r"\s*-\s*|\s+to\s+", re.IGNORECASE)

    # Helper to parse a single line (split ranges like "15:00 - 15:30")
    def parse_line(raw: str):
        raw = gr2en(norm(raw))
        raw = _range_splitter.split(raw, maxsplit=1)[0].strip()
        try:
            dt = dateparser.parse(raw, fuzzy=True, dayfirst=True)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=LOCAL_TZ)
            return dt.astimezone(LOCAL_TZ) if dt else None
        except Exception:
            return None

    # Prefer obvious “date lines” first
    lead_patterns = [
        r"(?:When|Date|Time|Start|Ημερομηνία|Ώρα|Στις)\s*[:>-]\s*(.+)",
        r"((?:Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s+\d{1,2}\s+\S+\s+\d{4}\s+\d{1,2}:\d{2}.*)",
        r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\w+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}.*)",
        r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}\s+\d{1,2}:\d{2}(?:\s?(?:AM|PM))?)",
        r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})",
    ]

    # Use the email's Date as a rough lower bound to filter bogus past parses
    email_dt = None
    try:
        email_dt = dateparser.parse(msg.get("Date", ""))
    except Exception:
        pass

    for txt in candidates:
        for pat in lead_patterns:
            for m in re.finditer(pat, txt, flags=re.IGNORECASE):
                s = m.group(1) if m.lastindex else m.group(0)
                dt = parse_line(s)
                if dt and (email_dt is None or dt >= (email_dt - timedelta(hours=12))):
                    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

    # ICS parsing (inline text/calendar OR attachment; TZID/HHMM/HHMMSS/Z; all-day)
    def unfold_ics(s: str) -> str:
        # RFC5545 line unfolding
        return re.sub(r"(?:\r?\n)[ \t]", "", s)

    WINDOWS_TZ_TO_IANA = {
        "GTB Standard Time": "Europe/Athens",
        # add more if you meet them…
    }

    parts_iter = msg.walk() if msg.is_multipart() else [msg]
    for part in parts_iter:
        ctype = (part.get_content_type() or "").lower()
        cd = (part.get("Content-Disposition") or "")
        # accept any text/calendar OR any attachment (even without .ics name)
        is_ics = (ctype == "text/calendar") or ("attachment" in cd.lower())
        if not is_ics:
            continue

        try:
            ics_raw = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            continue

        ics = unfold_ics(ics_raw)

        # search inside each VEVENT (avoid VTIMEZONE DTSTART lines)
        for vevent in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics, flags=re.DOTALL | re.IGNORECASE):
            m = re.search(
                r'^DTSTART(?:(?:;TZID="?([^":;]+)"?)|(?:;VALUE=DATE))?:(\d{8})(?:T(\d{4}|\d{6}))?(Z?)\r?$',
                vevent, flags=re.MULTILINE
            )
            if not m:
                continue

            tzid, yyyymmdd, hhmmss, zflag = m.groups()
            y, mo, d = int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8])
            if hhmmss:
                h, mi = int(hhmmss[:2]), int(hhmmss[2:4])
                s = int(hhmmss[4:6]) if len(hhmmss) == 6 else 0
            else:
                # all-day → pick 09:00 local as default
                h, mi, s = 9, 0, 0

            # resolve timezone
            if zflag == "Z":
                src_tz = tz.UTC
            elif tzid:
                iana = WINDOWS_TZ_TO_IANA.get(tzid, tzid)
                src_tz = tz.gettz(iana) or tz.gettz("Europe/Athens")
            else:
                src_tz = tz.gettz("Europe/Athens")

            dt = datetime(y, mo, d, h, mi, s, tzinfo=src_tz).astimezone(LOCAL_TZ)
            return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

    return None


def parse_folder_name(line: bytes) -> str:
    match = re.search(r'"([^"]+)"\s*$', line.decode())
    return match.group(1) if match else None


# Subject Extract - Method 1 (Works)
def decode_mime_header(header_value):
    parts = decode_header(header_value)
    decoded = ""
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded += part
    return decoded


# This function extracts email addresses from mail body
# Filters out unwanted system-generated addresses (like Microsoft Teams threads),
# Normalizes the emails (lowercase, stripped), removes duplicates,
# and returns them as a comma-separated values.
def extract_clean_meet_attendants(body):
    # Define a regular expression to match typical email addresses
    email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    # Find all email addresses in the body using the regex pattern
    emails = re.findall(email_regex, body)
    # Clean and filter the email addresses
    cleaned = [
        e.strip().lower()  # Normalize email: remove whitespace and lowercase
        for e in emails
        if not e.startswith("part")  # Exclude generic partials or placeholders (e.g., "part123@...")
           and not re.match(  # Exclude system-generated MS Teams thread addresses
            r"^19_meeting_.*@thread\.v2$", e
        )
    ]
    # Remove duplicates using set(), sort them alphabetically, and join with ",<br> " for display
    return ", ".join(sorted(set(cleaned)))
