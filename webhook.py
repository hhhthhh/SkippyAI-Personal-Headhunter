import os
import json
import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Skippy Ingestion API")

# Restrict CORS to browser extensions and local Streamlit instances
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^(chrome-extension://.*|moz-extension://.*|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_methods=["*"],
    allow_headers=["*"],
)

INBOX_FILE = "inbox.json"
MAX_INBOX_SIZE = 100
_inbox_lock = threading.Lock()
_server_lock = threading.Lock()
_server_thread = None

if os.path.exists(INBOX_FILE):
    try:
        os.chmod(INBOX_FILE, 0o600)
    except OSError:
        pass

def load_inbox_jobs() -> list[dict]:
    """Thread-safe loader for inbox.json."""
    with _inbox_lock:
        if not os.path.exists(INBOX_FILE):
            return []
        try:
            with open(INBOX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

def save_inbox_jobs(jobs: list[dict]):
    """Thread-safe, atomic writer for inbox.json with owner-only permissions."""
    with _inbox_lock:
        tmp_file = f"{INBOX_FILE}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=4)
            try:
                os.chmod(tmp_file, 0o600)
            except OSError:
                pass
            try:
                os.replace(tmp_file, INBOX_FILE)
            except OSError:
                # Fallback for Docker single-file bind mounts (Errno 16: Device or resource busy)
                with open(INBOX_FILE, "w", encoding="utf-8") as f:
                    json.dump(jobs, f, indent=4)
                try:
                    os.chmod(INBOX_FILE, 0o600)
                except OSError:
                    pass
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

def clear_inbox():
    """Thread-safe removal of inbox.json."""
    removed = False
    with _inbox_lock:
        if os.path.exists(INBOX_FILE):
            try:
                os.remove(INBOX_FILE)
                removed = True
            except OSError:
                removed = False
        else:
            removed = True
    if not removed:
        save_inbox_jobs([])

class JobPayload(BaseModel):
    source: str = Field(default="linkedin_extension", max_length=100)
    url: str = Field(..., max_length=2048)
    title: str = Field(default="Unknown Title", max_length=500)
    company: str = Field(default="Unknown Company", max_length=500)
    raw_text: str = Field(..., max_length=200_000)

@app.post("/api/ingest")
async def ingest_job(job: JobPayload):
    clean_url = job.url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Invalid URL: Only HTTP and HTTPS schemes are supported.")

    jobs = load_inbox_jobs()
    if len(jobs) >= MAX_INBOX_SIZE:
        raise HTTPException(
            status_code=429,
            detail=f"Inbox queue capacity reached ({MAX_INBOX_SIZE} jobs). Please evaluate or clear pending jobs in Skippy."
        )

    payload_dict = job.model_dump()
    payload_dict["url"] = clean_url
    jobs.append(payload_dict)
    save_inbox_jobs(jobs)
    
    return {"status": "success", "message": "Job added to inbox"}

def _run_server():
    # Bind to 127.0.0.1 by default to prevent external LAN/Internet exposure.
    # When deployed inside Docker, SKIPPY_WEBHOOK_HOST=0.0.0.0 can be passed via environment.
    host = os.environ.get("SKIPPY_WEBHOOK_HOST", "127.0.0.1")
    port = int(os.environ.get("SKIPPY_WEBHOOK_PORT", "8000"))
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except (OSError, SystemExit):
        pass

def start_background_listener():
    """Spawns the FastAPI server in a background daemon thread (singleton)."""
    global _server_thread
    with _server_lock:
        if _server_thread is not None and _server_thread.is_alive():
            return _server_thread
        _server_thread = threading.Thread(target=_run_server, daemon=True)
        _server_thread.start()
        return _server_thread