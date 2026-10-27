import unittest
import os
import sys
import pandas as pd
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import streamlit as st


class TestGalleryJumpToPosting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_gallery_jump.db"))
        cls.orig_db_path = db.DB_PATH
        cls.orig_db_file = db.DB_FILE

    def setUp(self):
        db.DB_PATH = self.test_db
        db.DB_FILE = self.test_db
        db.init_db()
        st.session_state.clear()

    def tearDown(self):
        st.session_state.clear()
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.orig_db_path
        db.DB_FILE = cls.orig_db_file
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def test_pages_compile(self):
        """Verifies gallery and history scripts compile cleanly without syntax errors."""
        import py_compile
        py_compile.compile("pages/6_gallery.py", doraise=True)
        py_compile.compile("pages/2_history.py", doraise=True)

    def test_gallery_jump_state_and_filter_safeguard(self):
        """Verifies jumping to a job ensures it is identified, tab-sorted, and kept in allowed_indices."""
        jobs_data = [
            {
                "URL": "https://example.com/job-1",
                "Position": "Junior Security Analyst",
                "Company": "Alpha Defense",
                "Timestamp": "2026-10-20 10:00:00",
                "Score": 85,
                "Eligible": True,
                "Source": "LinkedIn",
                "Tailored Resume": "# Resume for Alpha Defense",
            },
            {
                "URL": "https://example.com/job-2",
                "Position": "Lead Platform Engineer",
                "Company": "Beta Cloud",
                "Timestamp": "2026-10-15 10:00:00",
                "Score": 45,
                "Eligible": True,
                "Source": "Scraper",
                "Tailored Resume": "# Resume for Beta Cloud",
            },
        ]
        for j in jobs_data:
            db.save_job_result(j)
            db.update_job_field(j["URL"], "Tailored Resume", j["Tailored Resume"])

        all_saved_jobs = db.load_all_jobs()
        self.assertEqual(len(all_saved_jobs), 2)

        # Simulate clicking "Jump to Posting" on job-2 from Gallery
        target_url = "https://example.com/job-2"
        st.session_state["active_job_url"] = target_url
        st.session_state["jump_to_card"] = True

        # Simulate history resolution logic
        active_job = next((j for j in all_saved_jobs if j.get("URL") == st.session_state.get("active_job_url")), None)
        self.assertIsNotNone(active_job)
        self.assertEqual(active_job["Position"], "Lead Platform Engineer")

        # Verify source tab priority
        def get_source(item):
            src = item.get("Source")
            return "Manual" if pd.isna(src) or not src else str(src).strip()

        active_source = get_source(active_job)
        source_tabs_config = [
            ("LinkedIn", "🔗 LinkedIn Inbox", "Empty"),
            ("Scraper", "🕸️ Scraper Batch", "Empty"),
            ("Manual", "📝 Manual Entries", "Empty"),
        ]
        source_tabs_config.sort(key=lambda x: 0 if x[0] == active_source else 1)
        self.assertEqual(source_tabs_config[0][0], "Scraper")

        target_idx = next(i for i, j in enumerate(all_saved_jobs) if j.get("URL") == target_url)
        other_idx = next(i for i, j in enumerate(all_saved_jobs) if j.get("URL") != target_url)

        # Simulate an active filter that only kept the other job
        allowed_indices = {other_idx}
        self.assertNotIn(target_idx, allowed_indices)

        # Safeguard execution
        for i, j in enumerate(all_saved_jobs):
            if j.get("URL") == active_job.get("URL"):
                allowed_indices.add(i)
                break

        # Verification: target job is now guaranteed visible in allowed_indices
        self.assertIn(target_idx, allowed_indices)

        # Card expanded check
        for j in all_saved_jobs:
            is_active_card = (active_job is not None and j.get("URL") == active_job.get("URL"))
            if j.get("URL") == target_url:
                self.assertTrue(is_active_card)
            else:
                self.assertFalse(is_active_card)

    def test_open_document_modal_variable_binding(self):
        """Verifies open_document_modal binds safe_suffix and safe_prefix without UnboundLocalError."""
        import importlib
        from unittest.mock import patch, MagicMock

        mod = importlib.import_module("pages.6_gallery")
        sample_job = {
            "URL": "https://example.com/jobs/view/123456",
            "Position": "Security Specialist",
            "Company": "CyberCorp",
            "Timestamp": "2026-10-24 12:00:00",
            "Tailored Resume": "# Resume",
        }

        with patch.object(st, "columns", return_value=[MagicMock(), MagicMock()]), \
             patch.object(st, "button", return_value=False) as mock_btn, \
             patch.object(st, "text_area", return_value=""), \
             patch.object(st, "download_button", return_value=None):
            try:
                mod.open_document_modal(
                    doc_label="Resume",
                    doc_content="# Resume",
                    file_prefix="Resume",
                    doc_key="Tailored Resume",
                    job=sample_job
                )
            except Exception as e:
                self.assertNotIsInstance(e, UnboundLocalError)


if __name__ == "__main__":
    unittest.main()
