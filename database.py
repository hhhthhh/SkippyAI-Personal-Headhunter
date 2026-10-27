import sqlite3
import os
import json
import re
import time
from datetime import datetime
from functools import lru_cache

DB_FILE = "skippy.db"
DB_PATH = "skippy.db"
PROFILE_JSON_FILE = "profile_alignment.json"
SETTINGS_JSON_FILE = "app_settings.json"

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
    "Outreach Message",
    "Company Intel",
    "Applied Date",
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
                "Outreach Message" TEXT DEFAULT "",
                "Company Intel" TEXT DEFAULT "",
                "Applied Date" TEXT DEFAULT "",
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

        c.execute('''
            CREATE TABLE IF NOT EXISTS user_profile (
                "id" TEXT PRIMARY KEY,
                "primary_domain" TEXT DEFAULT "trades_construction",
                "secondary_domain" TEXT DEFAULT "",
                "primary_title" TEXT DEFAULT "",
                "secondary_title" TEXT DEFAULT "",
                "archetype_title" TEXT DEFAULT "",
                "archetype_description" TEXT DEFAULT "",
                "scores_json" TEXT DEFAULT "{}",
                "keywords_json" TEXT DEFAULT "[]",
                "custom_skills_json" TEXT DEFAULT "[]",
                "search_queries_json" TEXT DEFAULT "[]",
                "compliance_gates_json" TEXT DEFAULT "[]",
                "adapted_prompt" TEXT DEFAULT "",
                "updated_at" TEXT DEFAULT "",
                "ai_synthesized" INTEGER DEFAULT 0,
                "rubric_focus" TEXT DEFAULT ""
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS app_settings (
                "key" TEXT PRIMARY KEY,
                "value" TEXT DEFAULT "",
                "updated_at" TEXT DEFAULT ""
            )
        ''')
        
        # Gracefully upgrade existing databases to include new columns (checking schema first to avoid repeated exception overhead)
        c.execute('PRAGMA table_info(jobs)')
        existing_job_cols = {row[1] for row in c.fetchall()}
        c.execute('PRAGMA table_info(user_profile)')
        existing_prof_cols = {row[1] for row in c.fetchall()}

        migrations = [
            ("jobs", "Source", 'ALTER TABLE jobs ADD COLUMN "Source" TEXT DEFAULT "Manual"'),
            ("jobs", "Company", 'ALTER TABLE jobs ADD COLUMN "Company" TEXT DEFAULT ""'),
            ("jobs", "Deadline", 'ALTER TABLE jobs ADD COLUMN "Deadline" TEXT DEFAULT ""'),
            ("jobs", "Technical Score", 'ALTER TABLE jobs ADD COLUMN "Technical Score" INTEGER DEFAULT 0'),
            ("jobs", "Experience Score", 'ALTER TABLE jobs ADD COLUMN "Experience Score" INTEGER DEFAULT 0'),
            ("jobs", "Behavioral Score", 'ALTER TABLE jobs ADD COLUMN "Behavioral Score" INTEGER DEFAULT 0'),
            ("jobs", "Career Score", 'ALTER TABLE jobs ADD COLUMN "Career Score" INTEGER DEFAULT 0'),
            ("jobs", "Location Gate", 'ALTER TABLE jobs ADD COLUMN "Location Gate" TEXT DEFAULT "PASS"'),
            ("jobs", "Eligibility Gate", 'ALTER TABLE jobs ADD COLUMN "Eligibility Gate" TEXT DEFAULT "PASS"'),
            ("jobs", "Application QA", 'ALTER TABLE jobs ADD COLUMN "Application QA" TEXT DEFAULT ""'),
            ("jobs", "Followup Note", 'ALTER TABLE jobs ADD COLUMN "Followup Note" TEXT DEFAULT ""'),
            ("jobs", "Reviewer Audit", 'ALTER TABLE jobs ADD COLUMN "Reviewer Audit" TEXT DEFAULT ""'),
            ("jobs", "Matched Resumes", 'ALTER TABLE jobs ADD COLUMN "Matched Resumes" TEXT DEFAULT ""'),
            ("jobs", "Status Updated", 'ALTER TABLE jobs ADD COLUMN "Status Updated" TEXT DEFAULT ""'),
            ("jobs", "Outreach Message", 'ALTER TABLE jobs ADD COLUMN "Outreach Message" TEXT DEFAULT ""'),
            ("jobs", "Company Intel", 'ALTER TABLE jobs ADD COLUMN "Company Intel" TEXT DEFAULT ""'),
            ("jobs", "Applied Date", 'ALTER TABLE jobs ADD COLUMN "Applied Date" TEXT DEFAULT ""'),
            ("user_profile", "ai_synthesized", 'ALTER TABLE user_profile ADD COLUMN "ai_synthesized" INTEGER DEFAULT 0'),
            ("user_profile", "rubric_focus", 'ALTER TABLE user_profile ADD COLUMN "rubric_focus" TEXT DEFAULT ""'),
            ("user_profile", "custom_skills_json", 'ALTER TABLE user_profile ADD COLUMN "custom_skills_json" TEXT DEFAULT "[]"'),
        ]
        for tbl, col, stmt in migrations:
            cols = existing_prof_cols if tbl == "user_profile" else existing_job_cols
            if col not in cols:
                try:
                    c.execute(stmt)
                except sqlite3.OperationalError:
                    pass

        # Secondary indexes for fast filtering, history sorting, and repost lookups
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_jobs_company_lower ON jobs(LOWER("Company"));',
            'CREATE INDEX IF NOT EXISTS idx_jobs_timestamp ON jobs("Timestamp" DESC);',
            'CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs("Application Status");',
            'CREATE INDEX IF NOT EXISTS idx_seen_company_lower ON seen_postings(LOWER("company"));',
            'CREATE INDEX IF NOT EXISTS idx_scraper_company_lower ON scraper_results(LOWER("company"));',
            'CREATE INDEX IF NOT EXISTS idx_seen_url ON seen_postings("url");',
        ]
        for idx_stmt in indexes:
            try:
                c.execute(idx_stmt)
            except sqlite3.OperationalError:
                pass
            
        conn.commit()
        clear_repost_cache()
    finally:
        conn.close()
    _secure_db_file_permissions()

SUMMARY_COLUMNS = (
    '"URL", "Timestamp", "Position", "Company", "Deadline", "Eligible", '
    '"Disqualification Reason", "Score", "Technical Score", "Experience Score", '
    '"Behavioral Score", "Career Score", "Location Gate", "Eligibility Gate", '
    '"Summary", "Matching Skills", "Missing Skills", "Red Flags", '
    '"Application Status", "Matched Resumes", "Status Updated", "Applied Date", "Source"'
)

def load_all_jobs(summary_only: bool = False):
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        query = f'SELECT {SUMMARY_COLUMNS} FROM jobs ORDER BY rowid DESC' if summary_only else 'SELECT * FROM jobs ORDER BY rowid DESC'
        cur.execute(query)
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

def load_jobs_summary():
    """Loads lightweight job metadata without heavy text columns (resumes, cover letters, raw text)."""
    return load_all_jobs(summary_only=True)


def save_user_profile(profile_data: dict) -> bool:
    """Persists the user's career compass profile to SQLite and local JSON backup."""
    if not profile_data or not isinstance(profile_data, dict):
        return False

    # Write JSON fallback
    try:
        atomic_write_json(PROFILE_JSON_FILE, profile_data)
    except Exception:
        pass

    conn = get_connection()
    try:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        arch_title = profile_data.get("industry_title") or profile_data.get("archetype_title", "")
        arch_desc = profile_data.get("industry_description") or profile_data.get("archetype_description", "")
        with conn:
            conn.execute('''
                INSERT INTO user_profile (
                    "id", "primary_domain", "secondary_domain", "primary_title", "secondary_title",
                    "archetype_title", "archetype_description", "scores_json", "keywords_json",
                    "custom_skills_json", "search_queries_json", "compliance_gates_json",
                    "adapted_prompt", "updated_at", "ai_synthesized", "rubric_focus"
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT("id") DO UPDATE SET
                    "primary_domain" = excluded."primary_domain",
                    "secondary_domain" = excluded."secondary_domain",
                    "primary_title" = excluded."primary_title",
                    "secondary_title" = excluded."secondary_title",
                    "archetype_title" = excluded."archetype_title",
                    "archetype_description" = excluded."archetype_description",
                    "scores_json" = excluded."scores_json",
                    "keywords_json" = excluded."keywords_json",
                    "custom_skills_json" = excluded."custom_skills_json",
                    "search_queries_json" = excluded."search_queries_json",
                    "compliance_gates_json" = excluded."compliance_gates_json",
                    "adapted_prompt" = excluded."adapted_prompt",
                    "updated_at" = excluded."updated_at",
                    "ai_synthesized" = excluded."ai_synthesized",
                    "rubric_focus" = excluded."rubric_focus"
            ''', (
                "default_user",
                profile_data.get("primary_domain", ""),
                profile_data.get("secondary_domain", "") or "",
                profile_data.get("primary_title", ""),
                profile_data.get("secondary_title", ""),
                arch_title,
                arch_desc,
                json.dumps(profile_data.get("scores", {})),
                json.dumps(profile_data.get("keywords", [])),
                json.dumps(profile_data.get("custom_skills", [])),
                json.dumps(profile_data.get("search_queries", [])),
                json.dumps(profile_data.get("compliance_gates", [])),
                profile_data.get("adapted_prompt", ""),
                now_ts,
                1 if profile_data.get("ai_synthesized") else 0,
                profile_data.get("rubric_focus", "")
            ))
        return True
    except Exception as e:
        print(f"[Database Error] User profile save failed: {e}")
        return False
    finally:
        conn.close()


def load_user_profile() -> dict | None:
    """Loads the user's career compass profile from SQLite, falling back to local JSON if present."""
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM user_profile WHERE "id" = ?', ("default_user",))
        row = cur.fetchone()
        if row:
            d = dict(row)
            arch_title = d.get("archetype_title", "")
            arch_desc = d.get("archetype_description", "")
            return {
                "primary_domain": d.get("primary_domain", ""),
                "secondary_domain": d.get("secondary_domain", "") or None,
                "primary_title": d.get("primary_title", ""),
                "secondary_title": d.get("secondary_title", ""),
                "industry_title": arch_title,
                "archetype_title": arch_title,
                "industry_description": arch_desc,
                "archetype_description": arch_desc,
                "scores": json.loads(d.get("scores_json") or "{}"),
                "keywords": json.loads(d.get("keywords_json") or "[]"),
                "custom_skills": json.loads(d.get("custom_skills_json") or "[]"),
                "search_queries": json.loads(d.get("search_queries_json") or "[]"),
                "compliance_gates": json.loads(d.get("compliance_gates_json") or "[]"),
                "adapted_prompt": d.get("adapted_prompt", ""),
                "updated_at": d.get("updated_at", ""),
                "ai_synthesized": bool(d.get("ai_synthesized", 0)),
                "rubric_focus": d.get("rubric_focus", ""),
            }
    except Exception as e:
        print(f"[Database Warning] Profile load from DB failed, trying JSON fallback: {e}")
    finally:
        conn.close()

    if os.path.exists(PROFILE_JSON_FILE):
        try:
            with open(PROFILE_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("custom_skills", [])
                    # Self-heal SQLite database if row was missing or cleared
                    try:
                        save_user_profile(data)
                    except Exception:
                        pass
                    return data
        except Exception:
            pass
    return None


def get_setting(key: str, default: str = "") -> str:
    """Retrieves an application setting from SQLite, falling back to app_settings.json if present."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT "value" FROM app_settings WHERE "key" = ?', (key,))
        row = cur.fetchone()
        if row is not None and row[0] is not None:
            return str(row[0])
    except Exception as e:
        print(f"[Database Warning] Error loading setting '{key}' from DB: {e}")
    finally:
        conn.close()

    # JSON fallback
    if os.path.exists(SETTINGS_JSON_FILE):
        try:
            with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and key in data:
                    return str(data[key])
        except Exception:
            pass

    return default


def set_setting(key: str, value: str) -> bool:
    """Persists an application setting to SQLite and app_settings.json atomically."""
    clean_val = str(value)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Update JSON fallback
    settings_data = {}
    if os.path.exists(SETTINGS_JSON_FILE):
        try:
            with open(SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    settings_data = loaded
        except Exception:
            settings_data = {}
    settings_data[key] = clean_val
    try:
        atomic_write_json(SETTINGS_JSON_FILE, settings_data)
    except Exception:
        pass

    conn = get_connection()
    try:
        with conn:
            conn.execute('''
                INSERT INTO app_settings ("key", "value", "updated_at")
                VALUES (?, ?, ?)
                ON CONFLICT("key") DO UPDATE SET
                    "value" = excluded."value",
                    "updated_at" = excluded."updated_at"
            ''', (key, clean_val, now_ts))
        return True
    except Exception as e:
        print(f"[Database Error] Error saving setting '{key}': {e}")
        return False
    finally:
        conn.close()


def is_onboarding_completed() -> bool:
    """
    Returns True if onboarding was previously marked completed,
    or if user has existing resumes, profile, or job records.
    Automatically marks onboarding completed if existing data is detected.
    """
    flag = get_setting("onboarding_completed", "")
    if flag.lower() in ("true", "1", "yes"):
        return True

    # Retroactive detection: if user already has resumes, profile, or jobs, auto-mark completed
    try:
        if os.path.exists("resumes.json"):
            with open("resumes.json", "r", encoding="utf-8") as f:
                rdata = json.load(f)
                if isinstance(rdata, dict) and any(str(v).strip() for v in rdata.values()):
                    mark_onboarding_completed()
                    return True
        if os.path.exists("resume.md") and os.path.getsize("resume.md") > 20:
            mark_onboarding_completed()
            return True
        if os.path.exists("profile_alignment.json") and os.path.getsize("profile_alignment.json") > 20:
            mark_onboarding_completed()
            return True
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM jobs")
            row = cur.fetchone()
            if row and row[0] > 0:
                mark_onboarding_completed()
                return True
        finally:
            conn.close()
    except Exception:
        pass

    return False


def mark_onboarding_completed() -> bool:
    """Persists onboarding_completed flag to SQLite and app_settings.json."""
    return set_setting("onboarding_completed", "true")


def reset_onboarding_status() -> bool:
    """Allows a user to explicitly reset their onboarding status if they want to re-run setup."""
    return set_setting("onboarding_completed", "false")


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
        clear_repost_cache()
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
        clear_repost_cache()
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


def save_scraper_results(postings: list[dict], source_label: str = "", clear_existing: bool = False) -> None:
    """Persists or appends active scraper results to `scraper_results`."""
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
            if clear_existing:
                conn.execute("DELETE FROM scraper_results")
            conn.executemany('''
                INSERT INTO scraper_results
                ("id", "url", "title", "company", "location", "date", "source", "status", "payload_json", "scraped_at")
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT("id") DO UPDATE SET
                    "url" = excluded."url",
                    "title" = excluded."title",
                    "company" = excluded."company",
                    "location" = excluded."location",
                    "date" = excluded."date",
                    "source" = excluded."source",
                    "payload_json" = excluded."payload_json",
                    "scraped_at" = excluded."scraped_at",
                    "status" = CASE
                        WHEN scraper_results."status" IN ('evaluated', 'seen') THEN scraper_results."status"
                        ELSE excluded."status"
                    END
            ''', records)
        clear_repost_cache()
    except Exception as e:
        print(f"[Database Error] Failed to save scraper results: {e}")
    finally:
        conn.close()
    _secure_db_file_permissions()


def load_scraper_results() -> list[dict]:
    """Loads the persisted active scraper results from `scraper_results`."""
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
                    if r["source"] and "source" not in d:
                        d["source"] = r["source"]
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
                "source": r["source"] or "LinkedIn",
                "source_board": r["source"] or "LinkedIn",
                "status": r["status"] or "new"
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


def clear_scraper_results(source: str | None = None) -> None:
    """Wipes the active scraper results queue from `scraper_results`, optionally filtered by source."""
    conn = get_connection()
    try:
        with conn:
            if source:
                conn.execute('DELETE FROM scraper_results WHERE "source" = ?', (source,))
            else:
                conn.execute("DELETE FROM scraper_results")
        clear_repost_cache()
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
        clear_repost_cache()
    finally:
        conn.close()
    _secure_db_file_permissions()

def update_job_field(url: str, field: str, value: str, max_retries: int = 3) -> bool:
    if field not in ALLOWED_UPDATE_FIELDS:
        raise ValueError(f"Unauthorized field update attempt: '{field}'")
    clean_url = (url or "").strip()
    last_err = None
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            try:
                with conn:
                    if field == "Application Status":
                        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                        if value == "Applied":
                            cur = conn.execute(
                                'UPDATE jobs SET "Application Status" = ?, "Status Updated" = ?, '
                                '"Applied Date" = CASE WHEN "Applied Date" IS NULL OR "Applied Date" = \'\' THEN ? ELSE "Applied Date" END '
                                'WHERE "URL" = ?',
                                (value, now_ts, now_ts, clean_url)
                            )
                        else:
                            cur = conn.execute(
                                'UPDATE jobs SET "Application Status" = ?, "Status Updated" = ? WHERE "URL" = ?',
                                (value, now_ts, clean_url)
                            )
                    else:
                        cur = conn.execute(f'UPDATE jobs SET "{field}" = ? WHERE "URL" = ?', (value, clean_url))

                    if cur.rowcount == 0 and clean_url:
                        # Fallback for minor URL variations (e.g. trailing slash)
                        alt_url = clean_url.rstrip("/") if clean_url.endswith("/") else clean_url + "/"
                        if field == "Application Status":
                            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                            cur2 = conn.execute(
                                'UPDATE jobs SET "Application Status" = ?, "Status Updated" = ? WHERE "URL" = ?',
                                (value, now_ts, alt_url)
                            )
                            if cur2.rowcount > 0:
                                return True
                        else:
                            cur2 = conn.execute(f'UPDATE jobs SET "{field}" = ? WHERE "URL" = ?', (value, alt_url))
                            if cur2.rowcount > 0:
                                return True
                    return cur.rowcount > 0
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.05 * (2 ** attempt))
                continue
            raise
    if last_err:
        raise last_err
    return False


def _parse_timestamp_to_dt(ts_str: str) -> datetime | None:
    """Robustly parses timestamps across diverse ISO and human-readable formats."""
    if not ts_str or not isinstance(ts_str, str):
        return None
    s = ts_str.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if iso_match:
        try:
            return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
        except ValueError:
            pass
    return None


_TITLE_STOPWORDS = frozenset({
    "senior", "sr", "junior", "jr", "lead", "staff", "principal", "associate",
    "ii", "iii", "iv", "level", "1", "2", "3", "remote", "hybrid", "onsite",
    "full-time", "part-time", "contract", "intern", "internship", "the", "and", "or",
    "of", "in", "at", "for", "to", "with"
})


def _extract_title_tokens(title: str) -> set[str]:
    """Extracts distinctive role title tokens for repost matching."""
    clean = re.sub(r"[^\w\s-]", " ", (title or "").lower())
    words = set(re.findall(r"\b[a-z]{3,}\b", clean))
    return words - _TITLE_STOPWORDS


def detect_job_reposts(
    company: str,
    role: str,
    current_url: str = "",
    window_days: int = 90
) -> list[dict]:
    """
    Scans evaluated jobs, scraper queue, and seen postings to identify historical
    repostings or stale relistings of the same requisition from the same employer.
    Distinguishes concurrent multiple-openings from temporal relistings (requiring span >= 7 days).
    """
    company_clean = (company or "").strip()
    if not company_clean or company_clean.lower() in ("unknown", "unknown company", "confidential"):
        return []

    role_tokens = _extract_title_tokens(role)
    if not role_tokens:
        return []

    now = datetime.now()
    normalized_curr_url = normalize_job_url(current_url)
    curr_li_id = extract_linkedin_job_id(current_url)

    candidates = []
    conn = get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Search in jobs (evaluated postings)
        cur.execute(
            'SELECT "URL", "Position", "Company", "Timestamp", "Deadline", "Application Status" '
            'FROM jobs WHERE LOWER("Company") = LOWER(?)',
            (company_clean,)
        )
        for r in cur.fetchall():
            row = dict(r)
            candidates.append({
                "source_table": "jobs",
                "url": row.get("URL", ""),
                "title": row.get("Position", ""),
                "company": row.get("Company", ""),
                "date_str": row.get("Timestamp", "") or row.get("Deadline", ""),
                "status": row.get("Application Status", ""),
            })

        # 2. Search in scraper_results
        cur.execute(
            'SELECT "url", "title", "company", "date", "scraped_at" '
            'FROM scraper_results WHERE LOWER("company") = LOWER(?)',
            (company_clean,)
        )
        for r in cur.fetchall():
            row = dict(r)
            candidates.append({
                "source_table": "scraper_results",
                "url": row.get("url", ""),
                "title": row.get("title", ""),
                "company": row.get("company", ""),
                "date_str": row.get("scraped_at", "") or row.get("date", ""),
                "status": "Scraped",
            })

        # 3. Search in seen_postings
        cur.execute(
            'SELECT "url", "title", "company", "date", "seen_at" '
            'FROM seen_postings WHERE LOWER("company") = LOWER(?)',
            (company_clean,)
        )
        for r in cur.fetchall():
            row = dict(r)
            candidates.append({
                "source_table": "seen_postings",
                "url": row.get("url", ""),
                "title": row.get("title", ""),
                "company": row.get("company", ""),
                "date_str": row.get("seen_at", "") or row.get("date", ""),
                "status": "Discovered",
            })
    except Exception as e:
        print(f"[Database Error] detect_job_reposts query failed: {e}")
        return []
    finally:
        conn.close()

    matched_events = []
    seen_urls_in_batch = set()

    for cand in candidates:
        cand_url = cand.get("url", "")
        norm_url = normalize_job_url(cand_url)
        cand_li_id = extract_linkedin_job_id(cand_url)

        is_same_item = (norm_url and norm_url == normalized_curr_url) or (curr_li_id and cand_li_id and curr_li_id == cand_li_id)
        cand_tokens = _extract_title_tokens(cand.get("title", ""))
        overlap = role_tokens.intersection(cand_tokens)

        # Title similarity threshold: at least 50% overlap or >= 2 core tokens
        if len(overlap) >= max(1, len(role_tokens) // 2) or len(overlap) >= 2:
            dt = _parse_timestamp_to_dt(cand.get("date_str", ""))
            if dt:
                days_ago = (now - dt).days
                if 0 <= days_ago <= window_days:
                    dedup_key = (norm_url or cand_url, dt.strftime("%Y-%m-%d"))
                    if dedup_key not in seen_urls_in_batch:
                        seen_urls_in_batch.add(dedup_key)
                        matched_events.append({
                            "url": cand_url,
                            "title": cand.get("title", ""),
                            "company": cand.get("company", ""),
                            "date": dt.strftime("%Y-%m-%d %H:%M"),
                            "dt": dt,
                            "days_ago": days_ago,
                            "status": cand.get("status", ""),
                            "is_current": is_same_item,
                        })

    if len(matched_events) < 2:
        return []

    matched_events.sort(key=lambda x: x["dt"])
    earliest = matched_events[0]["dt"]
    latest = matched_events[-1]["dt"]
    days_span = (latest - earliest).days

    # Temporal relisting verification requires spanning at least 7 days
    if days_span < 7:
        return []

    reposts = []
    for ev in matched_events:
        reposts.append({
            "url": ev["url"],
            "title": ev["title"],
            "company": ev["company"],
            "date": ev["date"],
            "days_ago": ev["days_ago"],
            "status": ev["status"],
            "days_span": days_span,
            "is_ghost_risk": days_span >= 14,
        })
    return reposts


def clear_repost_cache():
    try:
        check_repost_risk.cache_clear()
    except Exception:
        pass


@lru_cache(maxsize=512)
def check_repost_risk(company: str, role: str, current_url: str = "", window_days: int = 90) -> dict | None:
    """
    Returns a high-level summary dict if a role is identified as a repost / ghost risk,
    or None if no repost patterns were detected.
    """
    reposts = detect_job_reposts(company, role, current_url, window_days)
    if not reposts:
        return None
    days_span = reposts[0]["days_span"]
    count = len(reposts)
    is_ghost = days_span >= 14 or count >= 3
    return {
        "count": count,
        "days_span": days_span,
        "first_seen": reposts[0]["date"],
        "last_seen": reposts[-1]["date"],
        "is_ghost_risk": is_ghost,
        "badge_text": f"👻 Relisted {count}x over {days_span}d" if is_ghost else f"🔄 Relisted {count}x ({days_span}d span)",
        "reposts": reposts,
    }


def get_pipeline_turnaround_metrics() -> dict:
    """
    Computes turnaround latencies and employer responsiveness metrics across evaluated jobs:
    - Average days to interview invite
    - Average days to rejection
    - Fast responders (< 7 days)
    - Stale / Ghosted applications (> 14 days with no response)
    """
    all_jobs = load_all_jobs(summary_only=True)
    interview_latencies = []
    rejection_latencies = []
    ghosted_count = 0
    now = datetime.now()

    for j in all_jobs:
        status = j.get("Application Status", "")
        applied_str = j.get("Applied Date", "")
        status_up_str = j.get("Status Updated", "") or j.get("Timestamp", "")

        app_dt = _parse_timestamp_to_dt(applied_str)
        if not app_dt and status in ("Applied", "Interviewing", "Offer", "Rejected"):
            app_dt = _parse_timestamp_to_dt(j.get("Timestamp", ""))

        if app_dt:
            up_dt = _parse_timestamp_to_dt(status_up_str) or now
            delta_days = max(0, (up_dt - app_dt).days)

            if status == "Interviewing":
                interview_latencies.append(delta_days)
            elif status == "Rejected":
                rejection_latencies.append(delta_days)
            elif status == "Applied":
                wait_days = (now - app_dt).days
                if wait_days >= 14:
                    ghosted_count += 1

    avg_interview = sum(interview_latencies) / len(interview_latencies) if interview_latencies else 0.0
    avg_rejection = sum(rejection_latencies) / len(rejection_latencies) if rejection_latencies else 0.0

    return {
        "avg_interview_days": round(avg_interview, 1),
        "avg_rejection_days": round(avg_rejection, 1),
        "total_interviewed": len(interview_latencies),
        "total_rejected": len(rejection_latencies),
        "ghosted_14d_count": ghosted_count,
    }

def clear_all_history():
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM jobs")
        clear_repost_cache()
    finally:
        conn.close()

init_db()
