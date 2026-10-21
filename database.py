import sqlite3
import os
import pandas as pd

DB_FILE = "skippy.db"
DB_PATH = "skippy.db"

# Strict whitelist of allowable columns to completely eliminate SQL injection
ALLOWED_UPDATE_FIELDS = frozenset({
    "Timestamp",
    "Position",
    "Company",
    "Deadline",
    "Eligible",
    "Disqualification Reason",
    "Score",
    "Technical Score",
    "Experience Score",
    "Behavioral Score",
    "Career Score",
    "Location Gate",
    "Eligibility Gate",
    "Summary",
    "Matching Skills",
    "Missing Skills",
    "Red Flags",
    "Job Text",
    "Application Status",
    "Tailored Resume",
    "Cover Letter",
    "Interview Prep",
    "Application QA",
    "Followup Note",
    "Reviewer Audit",
    "Matched Resumes",
    "Source"
})

def _resolve_db_path() -> str:
    """Resolves the active database path while maintaining compatibility with callers overriding DB_PATH or DB_FILE."""
    if DB_PATH != "skippy.db":
        return DB_PATH
    return DB_FILE


def _secure_db_file_permissions():
    """Ensure database file permissions are restricted to the owner only (0600)."""
    target = _resolve_db_path()
    if os.path.exists(target):
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_resolve_db_path(), timeout=30.0, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass
    return conn


def init_db():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                "URL" TEXT PRIMARY KEY,
                "Timestamp" TEXT,
                "Position" TEXT,
                "Company" TEXT DEFAULT "",
                "Deadline" TEXT DEFAULT "",
                "Eligible" BOOLEAN,
                "Disqualification Reason" TEXT,
                "Score" INTEGER,
                "Technical Score" INTEGER DEFAULT 0,
                "Experience Score" INTEGER DEFAULT 0,
                "Behavioral Score" INTEGER DEFAULT 0,
                "Career Score" INTEGER DEFAULT 0,
                "Location Gate" TEXT DEFAULT "PASS",
                "Eligibility Gate" TEXT DEFAULT "PASS",
                "Summary" TEXT,
                "Matching Skills" TEXT,
                "Missing Skills" TEXT,
                "Red Flags" TEXT,
                "Job Text" TEXT,
                "Application Status" TEXT,
                "Tailored Resume" TEXT,
                "Cover Letter" TEXT,
                "Interview Prep" TEXT,
                "Application QA" TEXT DEFAULT "",
                "Followup Note" TEXT DEFAULT "",
                "Reviewer Audit" TEXT DEFAULT "",
                "Matched Resumes" TEXT DEFAULT "",
                "Source" TEXT
            )
        ''')
        
        # Gracefully upgrade existing databases to include new columns
        migrations = [
            ('ALTER TABLE jobs ADD COLUMN "Source" TEXT DEFAULT "Manual"'),
            ('ALTER TABLE jobs ADD COLUMN "Company" TEXT DEFAULT ""'),
            ('ALTER TABLE jobs ADD COLUMN "Deadline" TEXT DEFAULT ""'),
            ('ALTER TABLE jobs ADD COLUMN "Technical Score" INTEGER DEFAULT 0'),
            ('ALTER TABLE jobs ADD COLUMN "Experience Score" INTEGER DEFAULT 0'),
            ('ALTER TABLE jobs ADD COLUMN "Behavioral Score" INTEGER DEFAULT 0'),
            ('ALTER TABLE jobs ADD COLUMN "Career Score" INTEGER DEFAULT 0'),
            ('ALTER TABLE jobs ADD COLUMN "Location Gate" TEXT DEFAULT "PASS"'),
            ('ALTER TABLE jobs ADD COLUMN "Eligibility Gate" TEXT DEFAULT "PASS"'),
            ('ALTER TABLE jobs ADD COLUMN "Application QA" TEXT DEFAULT ""'),
            ('ALTER TABLE jobs ADD COLUMN "Followup Note" TEXT DEFAULT ""'),
            ('ALTER TABLE jobs ADD COLUMN "Reviewer Audit" TEXT DEFAULT ""'),
            ('ALTER TABLE jobs ADD COLUMN "Matched Resumes" TEXT DEFAULT ""'),
        ]
        for stmt in migrations:
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
            
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
        for num_col in ("Score", "Technical Score", "Experience Score", "Behavioral Score", "Career Score"):
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0).astype(int)
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
    """
    Persists or updates an evaluated job posting using a non-destructive UPSERT.
    If the URL already exists in the database, updates the evaluation scores and metadata
    while preserving any existing generated documents ('Tailored Resume', 'Cover Letter',
    'Interview Prep', 'Application QA', 'Followup Note', 'Reviewer Audit') and existing
    non-default 'Application Status'.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''
            INSERT INTO jobs (
                "Timestamp", "Position", "Company", "Deadline", "URL",
                "Eligible", "Disqualification Reason", "Score",
                "Technical Score", "Experience Score", "Behavioral Score", "Career Score",
                "Location Gate", "Eligibility Gate",
                "Summary", "Matching Skills", "Missing Skills", "Red Flags",
                "Job Text", "Application Status", "Matched Resumes", "Source"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT("URL") DO UPDATE SET
                "Timestamp" = excluded."Timestamp",
                "Position" = excluded."Position",
                "Company" = CASE WHEN excluded."Company" != '' THEN excluded."Company" ELSE jobs."Company" END,
                "Deadline" = CASE WHEN excluded."Deadline" != '' THEN excluded."Deadline" ELSE jobs."Deadline" END,
                "Eligible" = excluded."Eligible",
                "Disqualification Reason" = excluded."Disqualification Reason",
                "Score" = excluded."Score",
                "Technical Score" = excluded."Technical Score",
                "Experience Score" = excluded."Experience Score",
                "Behavioral Score" = excluded."Behavioral Score",
                "Career Score" = excluded."Career Score",
                "Location Gate" = excluded."Location Gate",
                "Eligibility Gate" = excluded."Eligibility Gate",
                "Summary" = excluded."Summary",
                "Matching Skills" = excluded."Matching Skills",
                "Missing Skills" = excluded."Missing Skills",
                "Red Flags" = excluded."Red Flags",
                "Job Text" = excluded."Job Text",
                "Application Status" = CASE
                    WHEN jobs."Application Status" IS NOT NULL
                         AND jobs."Application Status" != ''
                         AND jobs."Application Status" != 'Not Applied'
                    THEN jobs."Application Status"
                    ELSE excluded."Application Status"
                END,
                "Matched Resumes" = CASE
                    WHEN excluded."Matched Resumes" != '' THEN excluded."Matched Resumes"
                    ELSE jobs."Matched Resumes"
                END,
                "Source" = excluded."Source"
        ''', (
            match_data.get("Timestamp"),
            match_data.get("Position"),
            match_data.get("Company", ""),
            match_data.get("Deadline", ""),
            match_data.get("URL"),
            match_data.get("Eligible"),
            match_data.get("Disqualification Reason"),
            int(match_data.get("Score") or 0),
            int(match_data.get("Technical Score") or 0),
            int(match_data.get("Experience Score") or 0),
            int(match_data.get("Behavioral Score") or 0),
            int(match_data.get("Career Score") or 0),
            match_data.get("Location Gate", "PASS"),
            match_data.get("Eligibility Gate", "PASS"),
            match_data.get("Summary"),
            match_data.get("Matching Skills"),
            match_data.get("Missing Skills"),
            match_data.get("Red Flags"),
            match_data.get("Job Text"),
            match_data.get("Application Status", "Not Applied"),
            match_data.get("Matched Resumes", ""),
            match_data.get("Source", "Manual")
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
