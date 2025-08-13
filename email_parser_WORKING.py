import email
import re
import json
from pathlib import Path
from email.header import decode_header
from datetime import datetime
import logging
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
import socket
import time
from dateutil import parser as dateparser
import re
from dateutil import tz
from bs4 import BeautifulSoup

from datetime import datetime, timedelta

from email import message_from_bytes
from email.message import Message
from dateutil import parser as dateparser

#TODO Mark found email with meetings as RED in order to distiguish at a glance.
#TODO For the same meeting ID it has to keep the last message meeting date like sent@16/4/25, 08:50 Libra

MODE = "SINCE"  # or "UNSEEN" or "SINCE" or "ALL"
#TODO Grab last parsing date from database to avoid full mailbox parse and set it to SINCE_DATE
SINCE_DATE = "01-Jun-2024"
UNTIL_DATE = datetime.now().strftime("%d-%b-%Y")


def load_accounts_from_file(filepath="accounts.json"):
    path = Path(filepath)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    else:
        logging.warning(f"⚠️ Accounts file not found: {filepath}")
        return []

#ACCOUNTS = load_accounts_from_file()

# -- Logging Setup --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("meeting_collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


def extract_meetings():
    meetings = []
    meetings_by_id = {}  # New dictionary to group by meeting ID

    # Iterate email accounts
    for acc in load_accounts_from_file():
        logging.info(f"\n🔍 Connecting to {acc['email']}")
        try:
            with IMAPClient(acc["host"]) as mail:
                mail.login(acc["email"], acc["password"])

                # time.sleep(2.5)
                folders = mail.list_folders()

                # Iterate account folders and subfolders with their flags and delimiters
                # Flags: \\HasChildren, \\HasNoChildren \\Flagged \\Junk
                # Delimiter /
                for  flags, delimiter, folder_name in folders:
                    #logging.info(f"\n📁 Folder: {folder_name}")

                    # if folder_name != "INBOX":
                    #     continue  # ❌ skip subfolders

                    try:
                        try:
                            mail.select_folder(folder_name, readonly=True)
                            #print(f"✅ Accessed: {folder_name}")
                        except Exception as e:
                            print(f"⚠️ Failed to access {folder_name}: {e}")

                        # Choose mode
                        if MODE == "ALL":
                            data = mail.search(["ALL"])
                        elif MODE == "UNSEEN":
                            data = mail.search(["UNSEEN"])
                        elif MODE == "SINCE":
                            # data = mail.search(f'(SINCE "{SINCE_DATE}")')
                            # data = mail.search(["SINCE", SINCE_DATE])
                            data = mail.search(["SEEN", "SINCE", SINCE_DATE])
                            #data = mail.search(["SINCE", SINCE_DATE, "BEFORE", UNTIL_DATE])
                            # result, data = mail.search(None, f'(SINCE "01-Jun-2025" BEFORE "25-Jun-2025")') 
                        else:
                            raise ValueError(f"Invalid mode: {MODE}")

                        #  Start parsing mail content with header infos
                        if data:
                            messages = mail.fetch(data, ["BODY.PEEK[]"])
                            for msg_id, body_data in messages.items():
                                body = body_data.get(b'BODY[]') or body_data.get(b'BODY.PEEK[]')
                                if not body:
                                    logging.warning(f"⚠️ No body for message ID {msg_id}")
                                    continue
                                
                                msg = email.message_from_bytes(body)

                                # Metadata
                                #subject = msg.get("Subject", "No Subject")
                                
                                #Subject Extract - Method 1 (Works)
                                subject = decode_mime_header(msg.get("Subject", "No Subject"))
                                #Subject Extract - Method 2 (Also Works)
                                #subject = clean_subject(msg.get("Subject", "No Subject"))
                                
                                msg_date = msg.get("Date", "")
                                sender = msg.get("From", "")
                                to = decode_mime_header( msg.get("To", "") )
                                cc = decode_mime_header( msg.get("Cc", "") )
                                bcc = decode_mime_header( msg.get("Bcc", "") )
                                msg_attendants = ", ".join(filter(None, [to, cc, bcc]))
                                message_id = msg.get("Message-ID", "")

                                # Extract body
                                body = ""
                                
                                text_body = ""
                                html_body = ""
                                
                                # if msg.is_multipart():
                                #     for part in msg.walk():
                                #         content_type = part.get_content_type()
                                #         if content_type in ["text/plain", "text/html"]:
                                #             charset = part.get_content_charset() or "utf-8"
                                #             try:
                                #                 body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                #                 break
                                #             except Exception:
                                #                 continue
                                # else:
                                #     body = msg.get_payload(decode=True).decode(errors="ignore")
                                
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
                                
                                #search_source = text_body or html_body # Choose the first non empty
                                search_source = (text_body or "") + "\n" + (html_body or "") # Concat both
                                
                                for plat, pat in meeting_patterns.items():
                                    #match = re.search(pat, body)
                                    match = re.search(pat, search_source)
                                    if match:
                                        platform = plat
                                        link = match.group(0)
                                        meeting_id = link.split("/")[-1].split("?")[0]
                                        #break
                                    
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
 
                                    # Parse the message's date (for comparison) to datetime
                                    try:
                                        msg_datetime = dateparser.parse(msg_date)
                                    except Exception:
                                        msg_datetime = None

                                    if meeting_id not in meetings_by_id:
                                        # First time seeing this meeting_id
                                        meetings_by_id[meeting_id] = {
                                            "msg_account": acc["email"],
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





                                    # meetings.append({
                                    #     "msg_account": acc["email"],
                                    #     "msg_folder": folder_name,
                                    #     "msg_id": message_id,
                                    #     "msg_date": msg_date,
                                    #     "msg_subject": subject,
                                    #     "msg_sender": sender,
                                    #     "msg_attendants": msg_attendants,

                                    #     "meet_platform": platform,
                                    #     "meet_id": meeting_id,
                                    #     "meet_attendants": extract_clean_meet_attendants(search_source),
                                    #     "meet_date": meet_date,
                                    #     "meet_link": link

                                    # })

                    except Exception as e:
                        logging.warning(f"⚠️ Error accessing folder '{folder_name}': {e}")
    
        except Exception as e:
            logging.warning(f"❌ Connection error with {acc['email']}: {e}")
            
        except IMAPClientError as e:
            print("IMAP error:", e)

        except socket.gaierror as e:
            print("Network error (DNS or host not found):", e)


    # Final collected results
    meetings = list(meetings_by_id.values())
    return meetings



# -- Meeting Regex --
# MEETING_REGEX = r"https://[a-zA-Z0-9_.\-]+\.(zoom\.us|teams\.microsoft\.com|meet\.google\.com)/[\w\-/\?=&#%]+"

# -- Meeting Patterns --
meeting_patterns = {
    "teams": r"https://teams\.microsoft\.com/l/meetup-join/[\w\-\%\?\=\&\/\.:]+",
    "zoom": r"https://[a-zA-Z0-9_.]*zoom\.us/j/[0-9\?\=a-zA-Z0-9_\-&]+",
    "google": r"https://meet\.google\.com/[a-z\-]+"
}



from dateutil import tz, parser as dateparser
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

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
        "Δευτέρα":"Monday","Τρίτη":"Tuesday","Τετάρτη":"Wednesday","Πέμπτη":"Thursday",
        "Παρασκευή":"Friday","Σάββατο":"Saturday","Κυριακή":"Sunday",
        "Ιανουαρίου":"January","Φεβρουαρίου":"February","Μαρτίου":"March","Απριλίου":"April",
        "Μαΐου":"May","Ιουνίου":"June","Ιουλίου":"July","Αυγούστου":"August",
        "Σεπτεμβρίου":"September","Οκτωβρίου":"October","Νοεμβρίου":"November","Δεκεμβρίου":"December",
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






# def extract_meet_date(msg, text_body, html_body):

#     candidate_texts = []

#     # 1. Try plain and html bodies
#     for body in [text_body, html_body]:
#         if not body:
#             continue
#         body = body.replace("&nbsp;", " ")
#         candidate_texts.append(body)
        
        
#     # Add full HTML text as final fallback (already parsed by BeautifulSoup)
#     if html_body:
#         soup = BeautifulSoup(html_body, "html.parser")

#         # Unwrap hidden collapsible blocks (like <details> or <div style="display:none">)
#         for tag in soup.find_all(style=True):
#             if "display:none" in tag["style"].replace(" ", "").lower():
#                 tag.unwrap()

#         for tag in soup.find_all("details"):
#             tag.unwrap()

#         clean_html = soup.get_text(separator="\n")
#         candidate_texts.append(clean_html)

#     # 2. Look for date patterns
#     date_patterns = [
#         r"(?:When|Date|Time|Ημερομηνία|Στις)[\s:>]*(.+)",
#         r"(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s+\d+\s+\S+\s+\d{4}.*?",
#         r"(Friday|Monday|Tuesday|Wednesday|Thursday|Saturday|Sunday),?\s+\w+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}(?:\s?[AP]M)?.*"
#     ]
    
#     greek_to_english = {
#         "Δευτέρα": "Monday", "Τρίτη": "Tuesday", "Τετάρτη": "Wednesday", "Πέμπτη": "Thursday",
#         "Παρασκευή": "Friday", "Σάββατο": "Saturday", "Κυριακή": "Sunday",
#         "Ιανουαρίου": "January", "Φεβρουαρίου": "February", "Μαρτίου": "March", "Απριλίου": "April",
#         "Μαΐου": "May", "Ιουνίου": "June", "Ιουλίου": "July", "Αυγούστου": "August",
#         "Σεπτεμβρίου": "September", "Οκτωβρίου": "October", "Νοεμβρίου": "November", "Δεκεμβρίου": "December"
#     }
    
#     def translate_greek_date(text):
#         for gr, en in greek_to_english.items():
#             text = text.replace(gr, en)
#         return text

#     for text in candidate_texts:
#         for pat in date_patterns:
#             match = re.search(pat, text, flags=re.IGNORECASE)
#             if match:
#                 # line = match.group(1).strip()
#                 if match.lastindex:  # if there's a capture group
#                     line = match.group(1).strip()
#                 else:
#                     line = match.group(0).strip()
                
#                 line = translate_greek_date(line)
#                 try:
#                     parsed = dateparser.parse(line, fuzzy=True)
#                     min_valid_date = datetime.now() - timedelta(days=180)  # 6 months window
#                     if parsed >= min_valid_date:
#                         return parsed.strftime("%a, %d %b %Y %H:%M:%S %z")
#                         #return parsed
#                 except Exception:
#                     continue
    
#     # valid_dates = []
#     # for text in candidate_texts:
#     #     for pat in date_patterns:
#     #         matches = re.finditer(pat, text, flags=re.IGNORECASE)
#     #         for match in matches:
#     #             if match.lastindex:
#     #                 raw = match.group(1).strip()
#     #             else:
#     #                 raw = match.group(0).strip()

#     #             raw = translate_greek_date(raw)
#     #             try:
#     #                 parsed = dateparser.parse(raw, fuzzy=True)
#     #                 if parsed:
#     #                     valid_dates.append(parsed)
#     #             except Exception:
#     #                 continue

#     # # Keep only future-ish dates (6 months window)
#     # threshold = datetime.now() - timedelta(days=180)
#     # valid_dates = [d for d in valid_dates if d >= threshold]

#     # if valid_dates:
#     #     return min(valid_dates).strftime("%a, %d %b %Y %H:%M:%S %z")


#     # 3. Fallback to .ics file (DTSTART)
#     if msg.is_multipart():
#         for part in msg.walk():
#             cd = part.get("Content-Disposition", "")
#             if "attachment" in cd and part.get_filename() and part.get_filename().endswith(".ics"):
#                 try:
#                     ics_data = part.get_payload(decode=True).decode("utf-8", errors="ignore")
#                     dtstart = re.search(r"DTSTART(?:;[^:=]*)?[:=](\d{8}T\d{6}Z?)", ics_data)
#                     if dtstart:
#                         raw = dtstart.group(1)
#                         parsed = dateparser.parse(raw)
                        
                        
#                         # ⏱ Normalize to local time zone
#                         local_tz = tz.tzlocal()
#                         parsed = parsed.astimezone(local_tz)
                        
#                         #return parsed
#                         return parsed.strftime("%a, %d %b %Y %H:%M:%S %z")
#                 except Exception:
#                     continue

#     return None




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
        e.strip().lower()                 # Normalize email: remove whitespace and lowercase
        for e in emails
            if not e.startswith("part")      # Exclude generic partials or placeholders (e.g., "part123@...")
            and not re.match(                # Exclude system-generated MS Teams thread addresses
                r"^19_meeting_.*@thread\.v2$", e
            )
    ]
    # Remove duplicates using set(), sort them alphabetically, and join with ",<br> " for display
    return ", ".join(sorted(set(cleaned)))





