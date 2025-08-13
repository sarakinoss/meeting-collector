import imaplib
import email
import re
import codecs
import json
from pathlib import Path
from email.header import decode_header
from datetime import datetime
import logging
from dateutil import parser as dateparser
from imapclient.imap_utf7 import decode as imap_utf7_decode
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
import socket
import time

import imapclient


MODE = "ALL"  # or "UNSEEN" or "SINCE" or "ALL"
#TODO Grab last parsing date from database to avoid full mailbox parse and set it to since
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

# -- Simple Parser (Logic from working minimal version) --
def extract_meetings():
    meetings = []

    # Iterate email accounts
    for acc in ACCOUNTS:
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
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type in ["text/plain", "text/html"]:
                                            charset = part.get_content_charset() or "utf-8"
                                            try:
                                                body = part.get_payload(decode=True).decode(charset, errors="ignore")
                                                break
                                            except Exception:
                                                continue
                                else:
                                    body = msg.get_payload(decode=True).decode(errors="ignore")


                                # Match meetings based on patterns
                                platform = None
                                link = None
                                meeting_id = None
                                
                                for plat, pat in meeting_patterns.items():
                                    match = re.search(pat, body)
                                    if match:
                                        platform = plat
                                        link = match.group(0)
                                        meeting_id = link.split("/")[-1].split("?")[0]
                                        #break
                                    
                                        # fallback for teams ID from body text
                                        if platform == "teams" and meeting_id == "0":
                                            id_match = re.search(r"Meeting ID:\s*([\d\s]+)", body)
                                            if id_match:
                                                meeting_id = id_match.group(1).replace(" ", "")
                                        break
                                
                                """ # Match meeting links
                                match_link = re.search(MEETING_REGEX, body)
                                if match_link:
                                    link = match_link.group(0)
                                    domain_match = re.search(r'https?://(?:www\.)?([^./]+)', link)
                                    platform = domain_match.group(1) if domain_match else "unknown"

                                    logging.info(f"✅ Meeting found: {link}")
                                    
                                    meeting_id = link.split("/")[-1] """

                                if link:
                                    logging.info(f"✅ Meeting found: {link} \n @ {folder_name}")
                                    
                                    
                                    
                                    
                                    # Special code for team meeting id parsing.
                                    ###########################################
                                    # if "teams.microsoft.com" in link:
                                    #     meet_id_match = re.search(r'/([0-9a-zA-Z_\-@.]+@thread\.v2)', link)
                                    #     if meet_id_match:
                                    #         meeting_id = meet_id_match.group(1)
                                            
                                    # Try to extract Meeting ID from body (if not parsed yet)
                                    # if platform == "teams" and not meeting_id:
                                    #     match = re.search(r"Meeting ID:\s*([\d\s]+)", body)
                                    #     if match:
                                    #         meeting_id = match.group(1).replace(" ", "")
                                            
                                    

                                    # Try to extract meeting date from body
                                    #######################################
                                    # meet_date = None
                                    # date_patterns = [
                                    #     r'(?:When|Time|Date|Ημερομηνία|Στις):?\s*(.+)',
                                    # ]

                                    # for dp in date_patterns:
                                    #     date_match = re.search(dp, body, re.IGNORECASE)
                                    #     if date_match:
                                    #         try:
                                    #             meet_date = dateparser.parse(date_match.group(1), fuzzy=True)
                                    #             break
                                    #         except Exception:
                                    #             continue

                                    # if not meet_date:
                                    #     # fallback to message date if no valid date is parsed
                                    #     meet_date = None
                                    # elif isinstance(meet_date, datetime):
                                    #     meet_date = meet_date.strftime("%a, %d %b %Y %H:%M:%S %z")  # match existing format
                                        
                                    # Try to extract meeting date from body
                                    meet_date = None 
                                    match_date = re.search(r"When:\s*(.*)", body)
                                    if match_date:
                                        when_line = match_date.group(1).strip()
                                        try:
                                            from dateutil import parser as dateparser
                                            parsed_when = dateparser.parse(when_line, fuzzy=True)
                                            meet_date = parsed_when.strftime("%a, %d %b %Y %H:%M:%S %z")
                                        except Exception:
                                            logging.warning(f"⚠️ Could not parse meeting date from line: {when_line}") 
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                        
                                    # # Extract meeting attendees from body (by email pattern)
                                    # email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
                                    # meet_attendees_raw = re.findall(email_regex, body)
                                    # meet_attendees_clean = sorted(set([e.lower() for e in meet_attendees_raw]))  # remove duplicates, normalize

                                    # # Join to comma-separated string
                                    # meet_attendants_str = ", ".join(meet_attendees_clean)
                                    
                                    
                                    # # Find all emails in the body (simple regex)
                                    # email_matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", body)
                                    # cleaned_attendants = [e for e in email_matches if not e.startswith("part") and len(e.split("@")[0]) > 1]
                                    # # Remove duplicates & join
                                    # meet_attendants = ", ".join(sorted(set(cleaned_attendants)))
                                        
                                    
                                    
                                    meetings.append({
                                        "msg_account": acc["email"],
                                        "msg_folder": folder_name,
                                        "msg_id": message_id,
                                        "msg_date": msg_date,
                                        "msg_subject": subject,
                                        "msg_sender": sender,
                                        "msg_attendants": msg_attendants,

                                        "meet_platform": platform,
                                        "meet_id": meeting_id,
                                        "meet_attendants": extract_clean_meet_attendants(body),
                                        "meet_date": meet_date,
                                        "meet_link": link

                                    })

                    except Exception as e:
                        logging.warning(f"⚠️ Error accessing folder '{folder_name}': {e}")

                #mail.logout() # with command handles disconnection 
                    
        except Exception as e:
            logging.warning(f"❌ Connection error with {acc['email']}: {e}")
            
        except IMAPClientError as e:
            print("IMAP error:", e)

        except socket.gaierror as e:
            print("Network error (DNS or host not found):", e)
            

    return meetings

def parse_folder_name(line: bytes) -> str:
    match = re.search(r'"([^"]+)"\s*$', line.decode())
    return match.group(1) if match else None


# def parse_folder_name(line: bytes) -> str:
#     # Extract the encoded folder name from the raw IMAP response
#     match = re.search(r'"([^"]+)"\s*$', line.decode())
#     if match:
#         folder_name_encoded = match.group(1)
#         # Decode from IMAP UTF-7 to Unicode (e.g., "Τραπεζικά")
#         return imap_utf7_decode(folder_name_encoded)
#     return None


def parse_folder_info(line: bytes):
    """
    Extract both encoded and decoded folder names from an IMAP LIST response line.
    """
    try:
        decoded_line = line.decode(errors="replace")
        quoted = re.findall(r'"([^"]+)"', decoded_line)
        if not quoted:
            return None, None

        encoded_path = quoted[-1]  # Last quoted value is the encoded path
        decoded_path = "/".join([
            imap_utf7_decode(p) if '&' in p else p
            for p in encoded_path.split('/')
        ])

        return encoded_path, decoded_path
    except Exception as e:
        print("❌ parse_folder_info error:", e)
        return None, None


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



#Subject Extract - Method 2 (Works)
def clean_subject(subject_raw):
    if subject_raw is None:
        return "(No Subject)"
    subject, encoding = decode_header(subject_raw)[0]
    if isinstance(subject, bytes):
        try:
            return subject.decode(encoding or "utf-8", errors="replace")
        except:
            return subject.decode("utf-8", errors="replace")
    return str(subject)



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





