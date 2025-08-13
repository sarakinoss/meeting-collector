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

MODE = "ALL"  # or "UNSEEN" or "SINCE" or "ALL"
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

ACCOUNTS = load_accounts_from_file()

# -- Logging Setup --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("meeting_collector.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# -- Meeting Regex --
# MEETING_REGEX = r"https://[a-zA-Z0-9_.\-]+\.(zoom\.us|teams\.microsoft\.com|meet\.google\.com)/[\w\-/\?=&#%]+"

# -- Meeting Patterns --
meeting_patterns = {
    "teams": r"https://teams\.microsoft\.com/l/meetup-join/[\w\-\%\?\=\&\/\.:]+",
    "zoom": r"https://[a-zA-Z0-9_.]*zoom\.us/j/[0-9\?\=a-zA-Z0-9_\-&]+",
    "google": r"https://meet\.google\.com/[a-z\-]+"
}






def extract_meet_date(msg, text_body, html_body, link=None):
    meet_date = None
    candidate_texts = []

    for body in [text_body, html_body]:
        if not body:
            continue
        body = body.replace("&nbsp;", " ")
        candidate_texts.append(body)

    from bs4 import BeautifulSoup
    for i, text in enumerate(candidate_texts):
        if html_body and i == 1:
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup.find_all(style=True):
                if "display:none" in tag["style"]:
                    tag.decompose()
            for details in soup.find_all("details"):
                details.unwrap()
            text = soup.get_text()

        # If link is given, focus on context around link
        if link and link in text:
            index = text.find(link)
            context_window = 300
            text_snippet = text[max(0, index - context_window): index + context_window]
        else:
            text_snippet = text

        date_patterns = [
            r"(?:When|Date|Time|Ημερομηνία|Στις)[:\s>]*([^\n\r<]+)",
            r"(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s+\d+\s+\S+\s+\d{4}.*?"
        ]
        
        greek_to_english = {
            "Δευτέρα": "Monday", "Τρίτη": "Tuesday", "Τετάρτη": "Wednesday", "Πέμπτη": "Thursday",
            "Παρασκευή": "Friday", "Σάββατο": "Saturday", "Κυριακή": "Sunday",
            "Ιανουαρίου": "January", "Φεβρουαρίου": "February", "Μαρτίου": "March", "Απριλίου": "April",
            "Μαΐου": "May", "Ιουνίου": "June", "Ιουλίου": "July", "Αυγούστου": "August",
            "Σεπτεμβρίου": "September", "Οκτωβρίου": "October", "Νοεμβρίου": "November", "Δεκεμβρίου": "December"
        }
        
        def translate_greek_date(text):
            for gr, en in greek_to_english.items():
                text = text.replace(gr, en)
            return text

        for pat in date_patterns:
            match = re.search(pat, text_snippet, flags=re.IGNORECASE)
            logging.info(f'✅ Match Found: {match.group(0)}')
        if match:
                if match.lastindex:
                    line = match.group(1).strip()
                else:
                    line = match.group(0).strip()
                line = translate_greek_date(line)
                try:
                    parsed = dateparser.parse(line, fuzzy=True)
                    min_valid_date = datetime.now() - timedelta(days=180)
                    if parsed >= min_valid_date:
                        return parsed.strftime("%a, %d %b %Y %H:%M:%S %z")
                except Exception:
                    continue

    # Fallback to .ics
    if msg.is_multipart():
        for part in msg.walk():
            cd = part.get("Content-Disposition", "")
            if "attachment" in cd and part.get_filename() and part.get_filename().endswith(".ics"):
                try:
                    ics_data = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    dtstart = re.search(r"DTSTART(?:;[^:=]*)?[:=](\d{8}T\d{6}Z?)", ics_data)
                    if dtstart:
                        raw = dtstart.group(1)
                        parsed = dateparser.parse(raw)
                        return parsed.strftime("%a, %d %b %Y %H:%M:%S %z")
                except Exception:
                    continue

    return None


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
                                    logging.info(f'✅ Match Found: {match.group(0)}')
                                    
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





