import sqlite3
import pandas as pd

DB_FILE = "skippy.db"

def get_connection():
    # check_same_thread=False is required for Streamlit's multithreading
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def load_all_jobs():
    """Loads all jobs from SQLite and formats them for the UI."""
    conn = get_connection()
    try:
        # FIX 1: Use SQLite's hidden 'rowid' to sort by newest, since 'id' doesn't exist
        df = pd.read_sql_query("SELECT * FROM jobs ORDER BY rowid DESC", conn)
        df.fillna("", inplace=True)  
        
        # Ensure booleans are typed correctly for Streamlit's dataframe rendering
        if 'Eligible' in df.columns:
            df['Eligible'] = df['Eligible'].astype(bool)
            
        # FIX 2: We deleted the rename_map. The database already outputs perfect Title Case!
        
        records = df.to_dict(orient="records")
    except Exception as e:
        # Print the error to the terminal so it never fails silently again
        print(f"[Database Error] History load failed: {e}")
        records = []
    conn.close()
    return records

def load_job_urls() -> set:
    """Returns a set of all previously scraped URLs to prevent duplicates."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT url FROM jobs")
        urls = {row[0] for row in cursor.fetchall()}
    except Exception:
        urls = set()
    conn.close()
    return urls

def save_job_result(match_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # We use INSERT OR REPLACE so if you re-scrape a job, it updates the row instead of crashing
    c.execute('''
        INSERT OR REPLACE INTO jobs (
            "Timestamp", "Position", "URL", "Eligible", "Disqualification Reason",
            "Score", "Summary", "Matching Skills", "Missing Skills", "Red Flags",
            "Job Text", "Application Status"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        match_data.get("Application Status")
    ))
    
    conn.commit()
    conn.close()

def update_job_field(url: str, field: str, value: str):
    """Targets a single cell (like Application Status or Tailored Resume) to update instantly."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Wrap the dynamic field name in double quotes so SQLite accepts the spaces
    cursor.execute(f'UPDATE jobs SET "{field}" = ? WHERE "URL" = ?', (value, url))
    
    conn.commit()
    conn.close()

def clear_all_history():
    """Wipes the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()

DB_PATH = "skippy.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            "Interview Prep" TEXT
        )
    ''')
    conn.commit()
    conn.close()

# CRITICAL: Add this at the bottom of the file!
init_db()