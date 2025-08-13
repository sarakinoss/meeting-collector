


import sqlite3

DB_PATH = "meetings.db"


def init_db():
    print("📦 Initializing meeting database...")
    conn = sqlite3.connect(DB_PATH)
    
    c = conn.cursor()
    c.execute('''
        DROP TABLE IF EXISTS meetings
    ''')
    conn.commit()
    
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_account TEXT,
            msg_folder TEXT,
            msg_id TEXT UNIQUE,
            msg_date TEXT,
            msg_subject TEXT,
            msg_sender TEXT,
            msg_attendants TEXT,
            
            meet_platform TEXT,
            meet_id TEXT UNIQUE,
            meet_attendants TEXT,
            meet_date TEXT,
            meet_link TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database ready!")


# def storeMeetingsToDB(data):
#     conn = sqlite3.connect(DB_PATH)
#     c = conn.cursor()
#     try:
#         c.execute('''
#             INSERT OR IGNORE INTO meetings
#             (account, folder, platform, subject, date_received, meeting_link, meeting_id, message_id)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         ''', (
#             data["account"],
#             data["folder"],
#             data["platform"],
#             data["subject"],
#             data["date"],
#             data["link"],
#             data["meeting_id"],
#             data["message_id"]
#         ))
#         conn.commit()
#     except Exception as e:
#         print("❌ DB insert error:", e)
#     finally:
#         conn.close()
        
# ------------------------------------------
# 💾 Insert Meetings to DB
# ------------------------------------------
def store_meetings_to_db(meeting_list):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # enable access by column name
    cur = conn.cursor()
    for m in meeting_list:
        cur.execute("""
            INSERT OR IGNORE INTO meetings (
                msg_account, msg_folder, msg_id, msg_date, msg_subject,
                msg_sender, msg_attendants,
                meet_platform, meet_id, meet_attendants, meet_date, meet_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m["msg_account"], m["msg_folder"], m["msg_id"], m["msg_date"], m["msg_subject"],
            m["msg_sender"], m["msg_attendants"],
            m["meet_platform"], m["meet_id"], m["meet_attendants"], m["meet_date"], m["meet_link"]
        ))
    conn.commit()
    conn.close()

    
# ------------------------------------------
# Fetch All Meetings from DB
# ------------------------------------------    
def get_all_meetings_as_dict():
    db_conn = sqlite3.connect(DB_PATH)
    db_conn.row_factory = sqlite3.Row
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM meetings ORDER BY msg_date DESC")
    rows = cursor.fetchall()
    db_conn.close()
    return [dict(row) for row in rows]  # 👈 μετατροπή σε dicts


