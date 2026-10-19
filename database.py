import sqlite3
import os
import pandas as pd

DB_FILE = "skippy.db"
DB_PATH = "skippy.db"

# Strict whitelist of allowable columns to completely eliminate SQL injection
ALLOWED_UPDATE_FIELDS = frozenset({
    "Timestamp",
    "Position",
    "Eligible",
    "Disqualification Reason",
    "Score",
    "Summary",
    "Matching Skills",
    "Missing Skills",
    "Red Flags",
    "Job Text",
    "Application Status",
    "Tailored Resume",
    "Cover Letter",
    "Interview Prep",
    "Source"
})

def _secure_db_file_permissions():
    """Ensure database file permissions are restricted to the owner only (0600)."""
    if os.path.exists(DB_PATH):
        try:
            os.chmod(DB_PATH, 0o600)
        except OSError:
            pass

def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    _secure_db_file_permissions()
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                "URL" TEXT PRIMARY KEY,
                "Timestamp" TEXT,
                "Position" TEXT,
                "Eligible" BOOLEAN,
                "Disqualification Reason" TEXT,
                "Score" INTEGER,
                "Summary" TEXT,
                "Matching Skills" TEXT,
                "Missing Skills" TEXT,
                "Red Flags" TEXT,
                "Job Text" TEXT,
                "Application Status" TEXT,
                "Tailored Resume" TEXT,
                "Cover Letter" TEXT,
                "Interview Prep" TEXT,
                "Source" TEXT
            )
        ''')
        
        # Gracefully upgrade existing databases to include the Source column
        try:
            c.execute('ALTER TABLE jobs ADD COLUMN "Source" TEXT DEFAULT "Manual"')
        except sqlite3.OperationalError:
            pass # Column already exists
            
        conn.commit()
    finally:
        conn.close()
    _secure_db_file_permissions()

def load_all_jobs():
    conn = get_connection()
    try:
        df = pd.read_sql_query('SELECT * FROM jobs ORDER BY rowid DESC', conn)
        df.fillna("", inplace=True)  
        if 'Eligible' in df.columns:
            df['Eligible'] = df['Eligible'].astype(bool)
        records = df.to_dict(orient="records")
    except Exception as e:
        print(f"[Database Error] History load failed: {e}")
        records = []
    finally:
        conn.close()
    return records

def load_job_urls() -> set:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT "URL" FROM jobs')
        urls = {row[0] for row in cursor.fetchall()}
    except Exception:
        urls = set()
    finally:
        conn.close()
    return urls

def save_job_result(match_data):
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO jobs (
                "Timestamp", "Position", "URL", "Eligible", "Disqualification Reason",
                "Score", "Summary", "Matching Skills", "Missing Skills", "Red Flags",
                "Job Text", "Application Status", "Source"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            match_data.get("Timestamp"),
            match_data.get("Position"),
            match_data.get("URL"),
            match_data.get("Eligible"),
            match_data.get("Disqualification Reason"),
            match_data.get("Score"),
            match_data.get("Summary"),
            match_data.get("Matching Skills"),
            match_data.get("Missing Skills"),
            match_data.get("Red Flags"),
            match_data.get("Job Text"),
            match_data.get("Application Status"),
            match_data.get("Source", "Manual") # Default to Manual if not provided
        ))
        conn.commit()
    finally:
        conn.close()
    _secure_db_file_permissions()

def update_job_field(url: str, field: str, value: str):
    if field not in ALLOWED_UPDATE_FIELDS:
        raise ValueError(f"Unauthorized field update attempt: '{field}'")
    conn = get_connection()
    try:
        with conn:
            conn.execute(f'UPDATE jobs SET "{field}" = ? WHERE "URL" = ?', (value, url))
    finally:
        conn.close()

def clear_all_history():
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM jobs")
    finally:
        conn.close()

init_db()