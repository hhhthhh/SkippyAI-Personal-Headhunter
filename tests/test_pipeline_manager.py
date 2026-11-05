import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
from pipeline import PipelineManager
import database as db


class TestPipelineManager(unittest.TestCase):
    def setUp(self):
        self.pm = PipelineManager()
        self.pm.cancel()
        self.pm.dismiss_latest_run()

    def test_pipeline_status_structure(self):
        status = self.pm.get_status()
        self.assertIn("is_running", status)
        self.assertIn("is_stopping", status)
        self.assertIn("was_cancelled", status)
        self.assertIn("total", status)
        self.assertIn("completed", status)
        self.assertIn("failed", status)
        self.assertIn("current_job", status)

    def test_pipeline_cancel_and_dismiss(self):
        self.pm.cancel()
        self.assertTrue(self.pm._stop_event.is_set())
        self.pm.dismiss_latest_run()
        self.assertFalse(self.pm.has_unnotified_completion)
        self.assertEqual(len(self.pm.evaluated_jobs), 0)

    def test_pipeline_cancel_sets_is_stopping_when_running(self):
        # Simulate active running state
        with self.pm._lock:
            self.pm.is_running = True
            self.pm.is_stopping = False
        self.pm.cancel()
        status = self.pm.get_status()
        self.assertTrue(status["is_stopping"])
        self.assertEqual(status["current_job"], "Stopping review...")
        with self.pm._lock:
            self.pm.is_running = False
            self.pm.is_stopping = False

    def test_pipeline_consume_cancelled_batch(self):
        with self.pm._lock:
            self.pm.has_unnotified_completion = True
            self.pm.was_cancelled = True
            self.pm.source = "Scraper"
            self.pm.evaluated_jobs = [{"Position": "Test Role", "Company": "Acme", "Score": 85}]
        batch = self.pm.consume_completed_batch()
        self.assertIsNotNone(batch)
        self.assertTrue(batch["was_cancelled"])
        self.assertEqual(len(batch["jobs"]), 1)

    def test_pipeline_worker_fast_abort_on_cancel(self):
        mock_job_match = MagicMock()
        mock_job_match.is_eligible = True
        mock_job_match.match_score = 80
        mock_job_match.technical_score = 80
        mock_job_match.experience_score = 80
        mock_job_match.behavioral_score = 80
        mock_job_match.career_alignment_score = 80
        mock_job_match.location_gate = "PASS"
        mock_job_match.eligibility_gate = "PASS"
        mock_job_match.company_name = "Test Co"
        mock_job_match.position_name = "Test Engineer"
        mock_job_match.application_deadline = ""
        mock_job_match.disqualification_reason = ""
        mock_job_match.summary = "Test summary"
        mock_job_match.matching_skills = ["Python"]
        mock_job_match.missing_skills = []
        mock_job_match.red_flags_or_caveats = []

        def slow_eval(*args, **kwargs):
            time.sleep(0.08)
            return mock_job_match

        items = [{"url": f"https://example.com/job/{i}", "raw_text": "Software engineer role requirements...", "title": f"Job {i}", "company": "Co"} for i in range(10)]
        with patch("pipeline.evaluate_job", side_effect=slow_eval), patch("database.save_job_result"):
            started = self.pm.start_url_pipeline(
                urls=items,
                resume_text="Resume",
                system_instructions="Prompt",
                model_choice="Google Gemini",
                api_key="fake-key",
            )
            self.assertTrue(started)
            time.sleep(0.02)
            self.pm.cancel()
            self.assertTrue(self.pm.get_status()["is_stopping"])
            if self.pm._thread:
                self.pm._thread.join(timeout=3.0)

            status = self.pm.get_status()
            self.assertFalse(status["is_running"])
            self.assertTrue(status["was_cancelled"])
            self.assertLess(status["completed"], 10)

    def test_database_summary_loading(self):
        records = db.load_all_jobs(summary_only=True)
        self.assertIsInstance(records, list)
        if records:
            # Verify heavy text blob columns are not present in summary load
            first = records[0]
            self.assertNotIn("Job Text", first)
            self.assertNotIn("Tailored Resume", first)
            self.assertIn("Position", first)
            self.assertIn("Score", first)

    def test_check_repost_risk_caching(self):
        # Verify check_repost_risk returns identical cached output and clears safely
        res1 = db.check_repost_risk("NonExistentCorp123", "Software Engineer")
        res2 = db.check_repost_risk("NonExistentCorp123", "Software Engineer")
        self.assertEqual(res1, res2)
        db.clear_repost_cache()


if __name__ == "__main__":
    unittest.main()
