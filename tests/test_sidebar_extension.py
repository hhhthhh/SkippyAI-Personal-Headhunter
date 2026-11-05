import unittest
import os
import sys
import py_compile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import utils
import streamlit as st


class TestSidebarExtensionButton(unittest.TestCase):
    def test_scripts_compile(self):
        """Ensures app, utils, and linkedin page compile cleanly."""
        py_compile.compile("app.py", doraise=True)
        py_compile.compile("utils.py", doraise=True)
        py_compile.compile("pages/5_linkedin.py", doraise=True)

    @patch("webhook.load_inbox_jobs")
    def test_extension_inbox_title_empty_inbox(self, mock_load):
        import app
        mock_load.return_value = []
        title = app.get_extension_inbox_title()
        self.assertEqual(title, "Extension Inbox")

    @patch("webhook.load_inbox_jobs")
    def test_extension_inbox_title_with_pending_jobs(self, mock_load):
        import app
        mock_load.return_value = [
            {"title": "Role 1", "company": "Co 1", "url": "https://example.com/1"},
            {"title": "Role 2", "company": "Co 2", "url": "https://example.com/2"},
            {"title": "Role 3", "company": "Co 3", "url": "https://example.com/3"},
        ]
        title = app.get_extension_inbox_title()
        self.assertEqual(title, "Extension Inbox (3)")

    def test_extension_page_is_sub_item_under_job_search(self):
        # Verify app source code places 5_linkedin immediately after 1_scraper
        with open("app.py", "r", encoding="utf-8") as f:
            content = f.read()
        scraper_idx = content.find('"pages/1_scraper.py"')
        linkedin_idx = content.find('"pages/5_linkedin.py"')
        results_idx = content.find('"pages/7_scraper_results.py"')
        self.assertNotEqual(scraper_idx, -1)
        self.assertNotEqual(linkedin_idx, -1)
        self.assertNotEqual(results_idx, -1)
        self.assertLess(scraper_idx, linkedin_idx, "Job Search must appear before Extension Inbox")
        self.assertLess(linkedin_idx, results_idx, "Extension Inbox must appear before Search Results")


if __name__ == "__main__":
    unittest.main()
