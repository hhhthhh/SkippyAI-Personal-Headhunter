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
        df = pd.read_sql_query("SELECT * FROM jobs ORDER BY id DESC", conn)
        df.fillna("", inplace=True)  
        
        if 'eligible' in df.columns:
            df['eligible'] = df['eligible'].astype(bool)
            
        # Map DB column names back to what the UI UI expects
        rename_map = {
            'url': 'URL', 'timestamp': 'Timestamp', 'position': 'Position',
            'eligible': 'Eligible', 'disqualification_reason': 'Disqualification Reason',
            'score': 'Score', 'summary': 'Summary', 'matching_skills': 'Matching Skills',
            'missing_skills': 'Missing Skills', 'red_flags': 'Red Flags', 'job_text': 'Job Text',
            'tailored_resume': 'Tailored Resume', 'cover_letter': 'Cover Letter',
            'interview_prep': 'Interview Prep', 'application_status': 'Application Status'
        }
        df.rename(columns=rename_map, inplace=True)
        records = df.to_dict(orient="records")
    except Exception as e:
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

def save_job_result(match_data: dict):
    """Inserts a new job evaluation or completely overwrites an existing one."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO jobs (
            url, timestamp, position, eligible, disqualification_reason, score, 
            summary, matching_skills, missing_skills, red_flags, job_text, application_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match_data["URL"], match_data["Timestamp"], match_data["Position"],
        1 if match_data["Eligible"] else 0, match_data.get("Disqualification Reason", ""),
        match_data["Score"], match_data["Summary"], match_data.get("Matching Skills", ""),
        match_data.get("Missing Skills", ""), match_data.get("Red Flags", ""),
        match_data.get("Job Text", ""), match_data.get("Application Status", "Not Applied")
    ))
    conn.commit()
    conn.close()

def update_job_field(url: str, field: str, value: str):
    """Targets a single cell (like Application Status or Tailored Resume) to update instantly."""
    column_map = {
        "Tailored Resume": "tailored_resume",
        "Cover Letter": "cover_letter",
        "Interview Prep": "interview_prep",
        "Application Status": "application_status"
    }
    db_col = column_map.get(field)
    if not db_col: return
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE jobs SET {db_col} = ? WHERE url = ?", (value, url))
    conn.commit()
    conn.close()

def clear_all_history():
    """Wipes the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()