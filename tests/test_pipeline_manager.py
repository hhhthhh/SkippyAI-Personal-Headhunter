import unittest
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
