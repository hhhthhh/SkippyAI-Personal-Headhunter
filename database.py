import sqlite3
import os
import json
import re
from datetime import datetime

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
    "Status Updated",
    "Source"
})

def _resolve_db_path() -> str:
    """Resolves the active database path while maintaining compatibility with callers overriding DB_PATH or DB_FILE."""
    if DB_PATH != "skippy.db":
        return DB_PATH
    return DB_FILE


def secure_file_permissions(filepath: str):
    """Restricts file permissions to user-read/write only (0600)."""
    if os.path.exists(filepath):
        try:
            os.chmod(filepath, 0o600)
        except OSError:
            pass


def _secure_db_file_permissions():
    secure_file_permissions(_resolve_db_path())


def atomic_write_text(filepath: str, content: str) -> None:
    """Safely writes text to file atomically with 0600 permissions, handling Docker bind mounts."""
    tmp_file = f"{filepath}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(content)
        secure_file_permissions(tmp_file)
        try:
            os.replace(tmp_file, filepath)
        except OSError:
            # Fallback for Docker single-file bind mounts (Errno 16: Device or resource busy)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            secure_file_permissions(filepath)
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
    except Exception as e:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        raise e


def atomic_write_json(filepath: str, data: any, indent: int = 2) -> None:
    """Safely dumps JSON to file atomically with 0600 permissions, handling Docker bind mounts."""
    atomic_write_text(filepath, json.dumps(data, indent=indent))


def set_env_var_safe(key: str, value: str, env_file: str = ".env") -> None:
    """Safely updates an environment variable in memory and persists to .env (Docker safe)."""
    from dotenv import set_key
    try:
        set_key(env_file, key, value, quote_mode="always")
    except OSError:
        lines = []
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except OSError:
                lines = []
        escaped_val = value.replace("\\", "\\\\").replace("'", "\\'")
        new_line = f"{key}='{escaped_val}'\n"
        updated = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(f"{key}="):
                lines[i] = new_line
                updated = True
                break
        if not updated:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(new_line)
        try:
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except OSError:
            pass
    os.environ[key] = value
    secure_file_permissions(env_file)


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
                "Status Updated" TEXT DEFAULT "",
                "Source" TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS seen_postings (
                "id" TEXT PRIMARY KEY,
                "url" TEXT DEFAULT "",
                "title" TEXT DEFAULT "",
                "company" TEXT DEFAULT "",
                "location" TEXT DEFAULT "",
                "date" TEXT DEFAULT "",
                "source" TEXT DEFAULT "",
                "seen_at" TEXT DEFAULT ""
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS scraper_results (
                "id" TEXT PRIMARY KEY,
                "url" TEXT DEFAULT "",
                "title" TEXT DEFAULT "",
                "company" TEXT DEFAULT "",
                "location" TEXT DEFAULT "",
                "date" TEXT DEFAULT "",
                "source" TEXT DEFAULT "",
                "status" TEXT DEFAULT "new",
                "payload_json" TEXT DEFAULT "",
                "scraped_at" TEXT DEFAULT ""
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
            ('ALTER TABLE jobs ADD COLUMN "Status Updated" TEXT DEFAULT ""'),
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
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM jobs ORDER BY rowid DESC')
        rows = cur.fetchall()
        int_cols = ("Score", "Technical Score", "Experience Score", "Behavioral Score", "Career Score")
        records = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if v is None:
                    d[k] = ""
            if "Eligible" in d:
                d["Eligible"] = bool(d["Eligible"]) if d["Eligible"] != "" else True
            for col in int_cols:
                if col in d:
                    try:
                        d[col] = int(d[col]) if d[col] != "" else 0
                    except (ValueError, TypeError):
                        d[col] = 0
            records.append(d)
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


def extract_linkedin_job_id(input_str: any) -> str | None:
    """Extracts numeric LinkedIn job ID from any URL, URN, or slug format."""
    if not input_str or not isinstance(input_str, str):
        return None
    trimmed = input_str.strip()
    if not trimmed:
        return None
    urn_match = re.search(r"urn:li:jobPosting:(\d{6,})", trimmed)
    if urn_match:
        return urn_match.group(1)
    if re.match(r"^\d{6,}$", trimmed):
        return trimmed
    path_match = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})/?", trimmed)
    if path_match:
        return path_match.group(1)
    cid_match = re.search(r"[?&]currentJobId=(\d{6,})", trimmed)
    if cid_match:
        return cid_match.group(1)
    slug_match = re.match(r"^[a-z0-9-]*-(\d{6,})$", trimmed, re.I)
    return slug_match.group(1) if slug_match else None


def normalize_job_url(url: any) -> str:
    """Normalizes job URL by stripping query parameters and trailing slashes for robust matching."""
    if not url or not isinstance(url, str):
        return ""
    clean = url.strip()
    if not clean:
        return ""
    clean = clean.split("?")[0].split("#")[0].rstrip("/")
    return clean.lower()


def load_evaluated_job_identifiers() -> tuple[set, set]:
    """Returns (normalized_urls_set, linkedin_job_ids_set) for all evaluated jobs in `jobs`."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT "URL" FROM jobs')
        raw_urls = [row[0] for row in cursor.fetchall() if row[0]]
    except Exception:
        raw_urls = []
    finally:
        conn.close()

    normalized_urls = set()
    linkedin_ids = set()
    for u in raw_urls:
        norm = normalize_job_url(u)
        if norm:
            normalized_urls.add(norm)
        lid = extract_linkedin_job_id(u)
        if lid:
            linkedin_ids.add(lid)
    return normalized_urls, linkedin_ids


def load_seen_job_identifiers() -> tuple[set, set]:
    """Returns (normalized_urls_set, linkedin_job_ids_set) for all seen postings in `seen_postings`."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT "id", "url" FROM seen_postings')
        rows = cursor.fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    normalized_urls = set()
    linkedin_ids = set()
    for pid, u in rows:
        if pid:
            lid = extract_linkedin_job_id(pid)
            if lid:
                linkedin_ids.add(lid)
            else:
                norm_pid = normalize_job_url(pid)
                if norm_pid:
                    normalized_urls.add(norm_pid)
        if u:
            norm = normalize_job_url(u)
            if norm:
                normalized_urls.add(norm)
            lid = extract_linkedin_job_id(u)
            if lid:
                linkedin_ids.add(lid)
    return normalized_urls, linkedin_ids


def record_seen_postings(postings: list[dict]) -> None:
    """Persists a batch of discovered postings to `seen_postings`."""
    if not postings:
        return
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_ts = datetime.now().isoformat()
        records = []
        for p in postings:
            if not isinstance(p, dict):
                continue
            raw_url = p.get("url") or p.get("original_url") or ""
            lid = extract_linkedin_job_id(p.get("id") or raw_url)
            pid = lid or p.get("id") or normalize_job_url(raw_url)
            if not pid:
                continue
            records.append((
                str(pid),
                str(raw_url),
                str(p.get("title") or ""),
                str(p.get("company") or ""),
                str(p.get("location") or ""),
                str(p.get("date") or ""),
                str(p.get("source_board") or p.get("source") or ""),
                now_ts
            ))
        cursor.executemany('''
            INSERT OR REPLACE INTO seen_postings
            ("id", "url", "title", "company", "location", "date", "source", "seen_at")
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', records)
        conn.commit()
    except Exception as e:
        print(f"[Database Error] Failed to record seen postings: {e}")
    finally:
        conn.close()
    _secure_db_file_permissions()


def clear_seen_postings() -> None:
    """Clears all records from `seen_postings`."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM seen_postings")
    finally:
        conn.close()


def classify_posting(
    job_or_url: any,
    eval_urls: set,
    eval_li_ids: set,
    seen_urls: set,
    seen_li_ids: set
) -> str:
    """Classifies a job posting or URL as 'evaluated', 'seen', or 'new'."""
    raw_url = ""
    job_id = None
    if isinstance(job_or_url, dict):
        raw_url = job_or_url.get("url") or job_or_url.get("original_url") or ""
        job_id = job_or_url.get("id")
    elif isinstance(job_or_url, str):
        raw_url = job_or_url

    lid = extract_linkedin_job_id(job_id or raw_url)
    norm_url = normalize_job_url(raw_url)

    # 1. Evaluated check has top priority
    if lid and lid in eval_li_ids:
        return "evaluated"
    if norm_url and norm_url in eval_urls:
        return "evaluated"

    # 2. Seen check
    if lid and lid in seen_li_ids:
        return "seen"
    if norm_url and norm_url in seen_urls:
        return "seen"

    # 3. Otherwise new
    return "new"


def save_scraper_results(postings: list[dict], source_label: str = "") -> None:
    """Atomically replaces the persisted active scraper results with a new batch."""
    conn = get_connection()
    try:
        now_ts = datetime.now().isoformat()
        records = []
        for p in postings:
            if not isinstance(p, dict):
                continue
            raw_url = p.get("url") or p.get("original_url") or ""
            lid = extract_linkedin_job_id(p.get("id") or raw_url)
            pid = lid or p.get("id") or normalize_job_url(raw_url)
            if not pid:
                continue
            payload = json.dumps(p)
            records.append((
                str(pid),
                str(raw_url),
                str(p.get("title") or ""),
                str(p.get("company") or ""),
                str(p.get("location") or ""),
                str(p.get("date") or ""),
                str(source_label or p.get("source_board") or p.get("source") or ""),
                str(p.get("status") or "new"),
                payload,
                now_ts
            ))
        with conn:
            conn.execute("DELETE FROM scraper_results")
            conn.executemany('''
                INSERT OR REPLACE INTO scraper_results
                ("id", "url", "title", "company", "location", "date", "source", "status", "payload_json", "scraped_at")
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
    except Exception as e:
        print(f"[Database Error] Failed to save scraper results: {e}")
    finally:
        conn.close()
    _secure_db_file_permissions()


def load_scraper_results() -> list[dict]:
    """Loads the persisted active scraper results from `scraper_results` with fallback to `seen_postings`."""
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT "id", "url", "title", "company", "location", "date", "source", "status", "payload_json" FROM scraper_results ORDER BY rowid ASC')
        rows = cursor.fetchall()
        results = []
        for r in rows:
            payload_json = r["payload_json"]
            if payload_json:
                try:
                    d = json.loads(payload_json)
                    if r["status"] and "status" not in d:
                        d["status"] = r["status"]
                    results.append(d)
                    continue
                except Exception:
                    pass
            results.append({
                "id": r["id"],
                "url": r["url"],
                "title": r["title"] or "(Untitled Role)",
                "company": r["company"] or "Unknown Company",
                "location": r["location"] or "",
                "date": r["date"] or "",
                "source_board": r["source"] or "LinkedIn",
                "status": r["status"] or "seen"
            })
        if not results:
            # Fallback to seen_postings so results survive initial migration and first login
            cursor.execute('SELECT "id", "url", "title", "company", "location", "date", "source" FROM seen_postings ORDER BY rowid DESC')
            seen_rows = cursor.fetchall()
            for r in seen_rows:
                results.append({
                    "id": r["id"],
                    "url": r["url"],
                    "title": r["title"] or "(Untitled Role)",
                    "company": r["company"] or "Unknown Company",
                    "location": r["location"] or "",
                    "date": r["date"] or "",
                    "source_board": r["source"] or "LinkedIn",
                    "status": "seen"
                })
        return results
    except Exception as e:
        print(f"[Database Error] Failed to load scraper results: {e}")
        return []
    finally:
        conn.close()


def get_seen_postings_count() -> int:
    """Returns the total number of distinct postings recorded in `seen_postings`."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM seen_postings')
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def clear_scraper_results() -> None:
    """Wipes the active scraper results queue from `scraper_results`."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM scraper_results")
    except Exception as e:
        print(f"[Database Error] Failed to clear scraper results: {e}")
    finally:
        conn.close()

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
            if field == "Application Status":
                now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                conn.execute(
                    'UPDATE jobs SET "Application Status" = ?, "Status Updated" = ? WHERE "URL" = ?',
                    (value, now_ts, url)
                )
            else:
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
