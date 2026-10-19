import os
import sys
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.sync_api import sync_playwright

import database as db
from scraper import scrape_job_text
from evaluator import evaluate_job
from webhook import load_inbox_jobs, save_inbox_jobs


class PipelineManager:
    """Thread-safe singleton managing asynchronous background evaluations.
    Decouples the evaluation pipeline from Streamlit's page lifecycle so users
    can switch pages without killing the running jobs.
    """
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(PipelineManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # State attributes
        self.is_running: bool = False
        self.total_jobs: int = 0
        self.completed_jobs: int = 0
        self.failed_jobs: int = 0
        self.current_job_name: str = ""
        self.source: str = ""  # "Scraper" or "LinkedIn"
        self.evaluated_jobs: list[dict] = []
        self.start_timestamp: Optional[float] = None
        self.finish_timestamp: Optional[float] = None
        self.has_unnotified_completion: bool = False
        self.last_error: Optional[str] = None

    def get_status(self) -> dict:
        """Returns a thread-safe snapshot of the current pipeline execution state."""
        with self._lock:
            return {
                "is_running": self.is_running,
                "total": self.total_jobs,
                "completed": self.completed_jobs,
                "failed": self.failed_jobs,
                "current_job": self.current_job_name,
                "source": self.source,
                "has_unnotified_completion": self.has_unnotified_completion,
                "last_error": self.last_error,
                "evaluated_count": len(self.evaluated_jobs),
            }

    def cancel(self):
        """Signals the background worker to halt gracefully after the current step."""
        self._stop_event.set()

    def consume_completed_batch(self) -> Optional[dict]:
        """Consumes the completed batch for UI notification and resets the notification flag.
        Returns a dict suitable for st.session_state['completion_batch'].
        """
        with self._lock:
            if not self.has_unnotified_completion:
                return None
            self.has_unnotified_completion = False
            return {
                "source": self.source,
                "jobs": list(self.evaluated_jobs),
                "failed": self.failed_jobs,
                "last_error": self.last_error,
                "timestamp": self.finish_timestamp or time.time()
            }

    def dismiss_latest_run(self):
        """Clears completed batch memory once acknowledged by the user."""
        with self._lock:
            self.evaluated_jobs = []
            self.has_unnotified_completion = False

    def start_url_pipeline(
        self,
        urls: list[str],
        resume_text: str,
        system_instructions: str,
        model_choice: str,
        api_key: str,
        local_base_url: str = "",
        local_model_name: str = "",
        model_override: str = "",
        source: str = "Scraper"
    ) -> bool:
        """Launches a background thread to scrape and evaluate a list of URLs."""
        with self._lock:
            if self.is_running:
                return False

            self.is_running = True
            self.total_jobs = len(urls)
            self.completed_jobs = 0
            self.failed_jobs = 0
            self.current_job_name = "Launching browser context..."
            self.source = source
            self.evaluated_jobs = []
            self.start_timestamp = time.time()
            self.finish_timestamp = None
            self.has_unnotified_completion = False
            self.last_error = None
            self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_url_worker,
            args=(
                urls, resume_text, system_instructions, model_choice,
                api_key, local_base_url, local_model_name, model_override, source
            ),
            daemon=True
        )
        self._thread.start()
        return True

    def start_inbox_pipeline(
        self,
        pending_jobs: list[dict],
        resume_text: str,
        system_instructions: str,
        model_choice: str,
        api_key: str,
        local_base_url: str = "",
        local_model_name: str = "",
        model_override: str = "",
        source: str = "LinkedIn"
    ) -> bool:
        """Launches a background thread to evaluate jobs from the LinkedIn extension inbox."""
        with self._lock:
            if self.is_running:
                return False

            self.is_running = True
            self.total_jobs = len(pending_jobs)
            self.completed_jobs = 0
            self.failed_jobs = 0
            self.current_job_name = "Initializing inbox evaluation..."
            self.source = source
            self.evaluated_jobs = []
            self.start_timestamp = time.time()
            self.finish_timestamp = None
            self.has_unnotified_completion = False
            self.last_error = None
            self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run_inbox_worker,
            args=(
                pending_jobs, resume_text, system_instructions, model_choice,
                api_key, local_base_url, local_model_name, model_override, source
            ),
            daemon=True
        )
        self._thread.start()
        return True

    def _run_url_worker(
        self, urls, resume_text, system_instructions, model_choice,
        api_key, local_base_url, local_model_name, model_override, source
    ):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                shared_page = browser.new_page()

                for i, url in enumerate(urls):
                    if self._stop_event.is_set():
                        break

                    with self._lock:
                        self.current_job_name = url

                    job_text = scrape_job_text(url, page=shared_page)

                    if not job_text.startswith("Error"):
                        try:
                            result = evaluate_job(
                                resume_text=resume_text,
                                job_text=job_text,
                                system_instructions=system_instructions,
                                model_choice=model_choice,
                                api_key=api_key,
                                local_base_url=local_base_url,
                                local_model_name=local_model_name,
                                model_override=model_override
                            )
                            match_data = {
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "Position": result.position_name,
                                "URL": url,
                                "Eligible": result.is_eligible,
                                "Disqualification Reason": result.disqualification_reason,
                                "Score": result.match_score,
                                "Summary": result.summary,
                                "Matching Skills": ", ".join(result.matching_skills),
                                "Missing Skills": ", ".join(result.missing_skills),
                                "Red Flags": " | ".join(result.red_flags_or_caveats),
                                "Job Text": job_text,
                                "Application Status": "Not Applied",
                                "Source": source
                            }
                            db.save_job_result(match_data)
                            with self._lock:
                                self.evaluated_jobs.append(match_data)
                                self.completed_jobs += 1
                        except Exception as e:
                            print(f"[Pipeline Error] {url}: {e}")
                            with self._lock:
                                self.failed_jobs += 1
                                self.last_error = str(e)
                    else:
                        print(f"[Pipeline Warning] Skipped {url}: {job_text}")
                        with self._lock:
                            self.failed_jobs += 1

                    if i < len(urls) - 1 and not self._stop_event.is_set():
                        time.sleep(3)

                browser.close()
        except Exception as e:
            print(f"[Pipeline Fatal Error]: {e}")
            with self._lock:
                self.last_error = str(e)
        finally:
            with self._lock:
                self.is_running = False
                self.finish_timestamp = time.time()
                self.has_unnotified_completion = True

    def _run_inbox_worker(
        self, pending_jobs, resume_text, system_instructions, model_choice,
        api_key, local_base_url, local_model_name, model_override, source
    ):
        try:
            for i, job_data in enumerate(pending_jobs):
                if self._stop_event.is_set():
                    break

                title = job_data.get("title", "Unknown Role")
                with self._lock:
                    self.current_job_name = title

                try:
                    result = evaluate_job(
                        resume_text=resume_text,
                        job_text=job_data.get("raw_text", ""),
                        system_instructions=system_instructions,
                        model_choice=model_choice,
                        api_key=api_key,
                        local_base_url=local_base_url,
                        local_model_name=local_model_name,
                        model_override=model_override
                    )
                    match_data = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Position": title,
                        "URL": job_data.get("url", ""),
                        "Eligible": result.is_eligible,
                        "Disqualification Reason": result.disqualification_reason,
                        "Score": result.match_score,
                        "Summary": result.summary,
                        "Matching Skills": ", ".join(result.matching_skills),
                        "Missing Skills": ", ".join(result.missing_skills),
                        "Red Flags": " | ".join(result.red_flags_or_caveats),
                        "Job Text": job_data.get("raw_text", ""),
                        "Application Status": "Not Applied",
                        "Source": source
                    }
                    db.save_job_result(match_data)
                    with self._lock:
                        self.evaluated_jobs.append(match_data)
                        self.completed_jobs += 1

                    # Remove evaluated job from inbox.json atomically
                    current_inbox = load_inbox_jobs()
                    updated_inbox = [j for j in current_inbox if j.get("url") != job_data.get("url")]
                    save_inbox_jobs(updated_inbox)

                except Exception as e:
                    print(f"[Pipeline Error] {title}: {e}")
                    with self._lock:
                        self.failed_jobs += 1
                        self.last_error = str(e)

        except Exception as e:
            print(f"[Pipeline Fatal Error]: {e}")
            with self._lock:
                self.last_error = str(e)
        finally:
            with self._lock:
                self.is_running = False
                self.finish_timestamp = time.time()
                self.has_unnotified_completion = True


# Global singleton instance
pipeline_manager = PipelineManager()
