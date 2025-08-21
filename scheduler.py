from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from email_parser import extract_meetings_all_accounts
from app.db.crud import store_meetings_to_db

def _fetch_and_store():
    meetings = extract_meetings_all_accounts()
    store_meetings_to_db(meetings)

# Initializes the background scheduler (using APScheduler) and:
# 1. Immediately fetches and stores meetings when the service starts.
# 2. Sets up a recurring job to re-fetch and update meetings every 5 minutes.
# This ensures the meeting database is always up to date with minimal delay.
def start_scheduler():
    # Create a background scheduler instance (non-blocking, safe for web apps)
    scheduler = BackgroundScheduler()
    #Fetch meetings on service start.
    # store_meetings_to_db(extract_meetings())

    # 1) Τρέξε αμέσως σε BACKGROUND (μη μπλοκάρει το boot)
    scheduler.add_job(_fetch_and_store, 'date', run_date=datetime.now())
    # 2) Επανάληψη ανά 5'
    scheduler.add_job(_fetch_and_store, 'interval', minutes=10, next_run_time=None)

    # meetings_by_id = extract_meetings_all_accounts()
    # store_meetings_to_db(meetings_by_id)
    
     # Schedule a recurring task to fetch and store meetings every 5 minutes
    # scheduler.add_job(
    #     lambda: store_meetings_to_db(extract_meetings()),  # Task to execute
    #     'interval',                                     # Scheduling type: run repeatedly
    #     minutes=5                                       # Run every 5 minutes
    # )
    # Start the scheduler in background mode
    scheduler.start()



