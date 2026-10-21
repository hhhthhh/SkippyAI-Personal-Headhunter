import os
import sys
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.sync_api import sync_playwright

import database as db
from scraper import scrape_job_text, scrape_job_with_guard, normalize_linkedin_job_id
from evaluator import evaluate_job
from webhook import load_inbox_jobs, save_inbox_jobs, remove_inbox_job_by_url


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
        source: str = "Scraper",
        matched_resumes: str = "",
    ) -> bool:
        """Launches a background thread to scrape and evaluate a list of URLs."""
        with self._lock:
            if self.is_running:
                return False

            self.is_running = True
            self.total_jobs = len(urls)
            self.completed_jobs = 0
            self.failed_jobs = 0
            self.current_job_name = "Initializing job evaluation pipeline..."
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
                api_key, local_base_url, local_model_name, model_override, source, matched_resumes
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
        source: str = "LinkedIn",
        matched_resumes: str = "",
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
                api_key, local_base_url, local_model_name, model_override, source, matched_resumes
            ),
            daemon=True
        )
        self._thread.start()
        return True

    def _evaluate_and_persist_posting(
        self,
        *,
        url: str,
        job_text: str,
        resume_text: str,
        system_instructions: str,
        model_choice: str,
        api_key: str,
        local_base_url: str,
        local_model_name: str,
        model_override: str,
        source: str,
        preset_title: str = "",
        preset_company: str = "",
        pre_security_flags: Optional[list[str]] = None,
        matched_resumes: str = "",
    ) -> dict:
        """Shared evaluation & database persistence helper used by both URL and Inbox workers."""
        result = evaluate_job(
            resume_text=resume_text,
            job_text=job_text,
            system_instructions=system_instructions,
            model_choice=model_choice,
            api_key=api_key,
            local_base_url=local_base_url,
            local_model_name=local_model_name,
            model_override=model_override,
            pre_security_flags=pre_security_flags or [],
        )
        resolved_company = preset_company or result.company_name or ""
        if resolved_company == "Unknown Company":
            resolved_company = ""

        resolved_position = result.position_name or preset_title or "Unknown Role"
        if preset_title and resolved_position in ("Unknown Role", "Unknown Position", "(Untitled Role)"):
            resolved_position = preset_title

        match_data = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Position": resolved_position,
            "Company": resolved_company,
            "Deadline": result.application_deadline or "",
            "URL": url,
            "Eligible": result.is_eligible,
            "Disqualification Reason": result.disqualification_reason,
            "Score": result.match_score,
            "Technical Score": result.technical_score,
            "Experience Score": result.experience_score,
            "Behavioral Score": result.behavioral_score,
            "Career Score": result.career_alignment_score,
            "Location Gate": result.location_gate,
            "Eligibility Gate": result.eligibility_gate,
            "Summary": result.summary,
            "Matching Skills": ", ".join(result.matching_skills),
            "Missing Skills": ", ".join(result.missing_skills),
            "Red Flags": " | ".join(result.red_flags_or_caveats),
            "Job Text": job_text,
            "Application Status": "Not Applied",
            "Matched Resumes": matched_resumes,
            "Source": source,
        }
        db.save_job_result(match_data)
        with self._lock:
            self.evaluated_jobs.append(match_data)
            self.completed_jobs += 1
        return match_data

    def _run_url_worker(
        self, urls, resume_text, system_instructions, model_choice,
        api_key, local_base_url, local_model_name, model_override, source, matched_resumes=""
    ):
        playwright_ctx = None
        browser = None
        shared_page = None
        try:
            for i, item in enumerate(urls):
                if self._stop_event.is_set():
                    break

                if isinstance(item, dict):
                    url = item.get("url", "")
                    preset_title = item.get("title", "")
                    preset_company = item.get("company", "")
                    raw_text = item.get("raw_text", "")
                    pre_flags = list(item.get("security_flags") or [])
                    display_label = f"{preset_title} ({preset_company})" if preset_title and preset_company else (preset_title or url)
                else:
                    url = str(item)
                    preset_title = ""
                    preset_company = ""
                    raw_text = ""
                    pre_flags = []
                    display_label = url

                with self._lock:
                    self.current_job_name = display_label

                if raw_text and len(raw_text.strip()) > 50:
                    job_text = raw_text
                    sec_flags = pre_flags
                elif normalize_linkedin_job_id(url):
                    # LinkedIn URLs resolve via fast unauthenticated Guest API first
                    job_text, sec_flags = scrape_job_with_guard(url, page=None)
                else:
                    # Try fast static fetch first; lazily launch shared Playwright browser only if needed
                    job_text, sec_flags = scrape_job_with_guard(url, page=shared_page)
                    if job_text.startswith("Error") and shared_page is None:
                        try:
                            playwright_ctx = sync_playwright().start()
                            browser = playwright_ctx.chromium.launch(headless=True)
                            shared_page = browser.new_page()
                            job_text, sec_flags = scrape_job_with_guard(url, page=shared_page)
                        except Exception as pw_err:
                            job_text = f"Error launching browser fallback: {pw_err}"

                all_sec_flags = []
                for fl in pre_flags + (sec_flags or []):
                    if fl and fl not in all_sec_flags:
                        all_sec_flags.append(fl)

                if not job_text.startswith("Error"):
                    try:
                        self._evaluate_and_persist_posting(
                            url=url,
                            job_text=job_text,
                            resume_text=resume_text,
                            system_instructions=system_instructions,
                            model_choice=model_choice,
                            api_key=api_key,
                            local_base_url=local_base_url,
                            local_model_name=local_model_name,
                            model_override=model_override,
                            source=source,
                            preset_title=preset_title,
                            preset_company=preset_company,
                            pre_security_flags=all_sec_flags,
                            matched_resumes=matched_resumes,
                        )
                    except Exception as e:
                        print(f"[Pipeline Error] {url}: {e}")
                        with self._lock:
                            self.failed_jobs += 1
                            self.last_error = str(e)
                else:
                    print(f"[Pipeline Warning] Skipped {url}: {job_text}")
                    with self._lock:
                        self.failed_jobs += 1
                        self.last_error = job_text

                if i < len(urls) - 1 and not self._stop_event.is_set():
                    time.sleep(1.5 if raw_text else 2.5)
        except Exception as e:
            print(f"[Pipeline Fatal Error]: {e}")
            with self._lock:
                self.last_error = str(e)
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright_ctx is not None:
                try:
                    playwright_ctx.stop()
                except Exception:
                    pass
            with self._lock:
                self.is_running = False
                self.finish_timestamp = time.time()
                self.has_unnotified_completion = True

    def _run_inbox_worker(
        self, pending_jobs, resume_text, system_instructions, model_choice,
        api_key, local_base_url, local_model_name, model_override, source, matched_resumes=""
    ):
        try:
            for i, job_data in enumerate(pending_jobs):
                if self._stop_event.is_set():
                    break

                title = job_data.get("title", "Unknown Role")
                with self._lock:
                    self.current_job_name = title

                try:
                    self._evaluate_and_persist_posting(
                        url=job_data.get("url", ""),
                        job_text=job_data.get("raw_text", ""),
                        resume_text=resume_text,
                        system_instructions=system_instructions,
                        model_choice=model_choice,
                        api_key=api_key,
                        local_base_url=local_base_url,
                        local_model_name=local_model_name,
                        model_override=model_override,
                        source=source,
                        preset_title=title,
                        preset_company=job_data.get("company") or "",
                        pre_security_flags=list(job_data.get("security_flags") or []),
                        matched_resumes=matched_resumes,
                    )
                    # Atomically remove evaluated job from inbox.json while holding _inbox_lock
                    remove_inbox_job_by_url(job_data.get("url", ""))
                except Exception as e:
                    print(f"[Pipeline Error] {title}: {e}")
                    with self._lock:
                        self.failed_jobs += 1
                        self.last_error = str(e)

                if i < len(pending_jobs) - 1 and not self._stop_event.is_set():
                    time.sleep(1.5)
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
