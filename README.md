# 📅 Meeting Collector

A self-hosted Python-based system for scanning multiple email accounts, extracting meeting links (e.g., Microsoft Teams, Zoom, Google Meet), storing them in a local database, and displaying them via a web dashboard.

This solution is ideal for environments with:
- Limited internet connectivity
- On-premise infrastructure (e.g., Nextcloud, Synology)
- The need for a unified calendar view of all upcoming meetings

        +---------------------------------------------------------------+
        |   uvicorn main:app --reload --host 0.0.0.0 --port 8080        |   
        +---------------------------------------------------------------+
                                   |
                                   v
                          +-----------------+   <-- Entry point (optional CLI/test)
                          |   main.py       |   <-- FastAPI Server
                          +-----------------+
                                   |
        +--------------------------+-----------------------------+
        |                          |                             |
        v                          v                             v
+----------------+        +-------------------+         +---------------------+
|   init_db()    |        |  start_scheduler()|         | FastAPI Endpoints   |
| (app/db.py)    |        | (scheduler.py)    |         | - /                 |
+----------------+        +-------------------+         | - /meetings         |
                                                         +---------------------+
                                                                  |
                                                                  v
                                                    +------------------------------+
                                                    |   get_all_meetings()         |
                                                    |       or SQLite direct       |
                                                    |       query to DB            |
                                                    +------------------------------+



---

## 🚀 Features

- ✅ Connects to Gmail, Synology Mail Server, and other IMAP-compatible servers
- ✅ Extracts meeting links from both plain-text and HTML emails
- ✅ Detects Microsoft Teams, Zoom, and Google Meet platforms
- ✅ Stores meetings in a local SQLite database
- ✅ Ensures unique meeting detection across folders and accounts
- ✅ Supports future extensions like calendar syncing and web dashboards

---

## 🛠 Installation

### 1. Clone the repository

```bash
git clone https://your.repo.url/meeting-collector.git
cd meeting-collector
```

### 2. Create a virtual environment 
```bash
python3 -m venv venv
source venv/bin/activate
```
### 3. Install dependencies
```bash
pip install -r requirements.txt
```

## Usage
🔹 Initialize the database
```bash
python3 run.py
```


🧱 Project Structure
```bash
meeting-collector/
├── app/
│   ├── __init__.py         # Python package marker
│   ├── db.py               # Database logic
│   └── email_reader.py     # [Coming Soon] Email scan and parsing logic
│
├── run.py                  # Entry point for DB or task execution
├── requirements.txt        # Python dependencies
├── venv/                   # Python virtual environment
└── README.md               # You are here
```

### Run
uvicorn main:app --reload --host 0.0.0.0 --port 8080
Λύση 1: Διαγραφή και επαναδημιουργία του venv
Αν δεν έχεις σημαντικά πακέτα εγκατεστημένα:
Διέγραψε τον φάκελο venv:
Δημιούργησε νέο virtual environment:
python3 -m venv venv
Ενεργοποίησε το venv:
source venv/bin/activate
Εγκατέστησε ξανά τα dependencies:
Αν έχεις requirements.txt:
pip install -r requirements.txt
Αν όχι:
pip install fastapi uvicorn
Τρέξε ξανά:
uvicorn main:app --reload --host 0.0.0.0 --port 8080
