
# scheduler.py
# └── start_scheduler()
#     ├── ⏱️ immediate: extract_meetings() (from email_parser.py)
#     │   └── connect to each account
#     │       └── scan folders/emails
#     │           └── parse subject, body, platform, meeting link, etc.
#     └── ⏳ schedule: every 5 minutes -> repeat above

#     └── insert_meetings() → app/db.py → into `meetings.db`

from apscheduler.schedulers.background import BackgroundScheduler
from email_parser import extract_meetings
from app.db.crud import store_meetings_to_db

# Initializes the background scheduler (using APScheduler) and:
# 1. Immediately fetches and stores meetings when the service starts.
# 2. Sets up a recurring job to re-fetch and update meetings every 5 minutes.
# This ensures the meeting database is always up to date with minimal delay.
def start_scheduler():
    # Create a background scheduler instance (non-blocking, safe for web apps)
    scheduler = BackgroundScheduler()
    #Fetch meetings on service start.
    store_meetings_to_db(extract_meetings())
    
     # Schedule a recurring task to fetch and store meetings every 5 minutes
    # scheduler.add_job(
    #     lambda: store_meetings_to_db(extract_meetings()),  # Task to execute
    #     'interval',                                     # Scheduling type: run repeatedly
    #     minutes=5                                       # Run every 5 minutes
    # )
    # Start the scheduler in background mode
    scheduler.start()



