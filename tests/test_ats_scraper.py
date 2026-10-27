import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scraper
import database as db


class TestATSScraper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig_db_path = db.DB_PATH
        cls.orig_db_file = db.DB_FILE
        cls.test_db = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_ats_temp.db"))

    def setUp(self):
        db.DB_PATH = self.test_db
        db.DB_FILE = self.test_db
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.orig_db_path
        db.DB_FILE = self.orig_db_file
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

    def test_extract_ats_board_info_urls(self):
        """Verifies accurate detection of platform and slug from career URLs."""
        # Greenhouse
        plat, token = scraper.extract_ats_board_info("https://boards.greenhouse.io/anthropic")
        self.assertEqual(plat, "greenhouse")
        self.assertEqual(token, "anthropic")

        # Ashby
        plat, token = scraper.extract_ats_board_info("https://jobs.ashbyhq.com/openai")
        self.assertEqual(plat, "ashby")
        self.assertEqual(token, "openai")

        # Lever
        plat, token = scraper.extract_ats_board_info("https://jobs.lever.co/palantir")
        self.assertEqual(plat, "lever")
        self.assertEqual(token, "palantir")

    def test_extract_ats_board_info_slugs(self):
        """Verifies clean slug extraction when no URL prefix is passed."""
        plat, token = scraper.extract_ats_board_info("anthropic", default_platform="greenhouse")
        self.assertEqual(plat, "greenhouse")
        self.assertEqual(token, "anthropic")

        plat, token = scraper.extract_ats_board_info("OpenAI_Labs", default_platform="ashby")
        self.assertEqual(plat, "ashby")
        self.assertEqual(token, "openai_labs")

    @patch("scraper._get_http_session")
    def test_fetch_greenhouse_board_mock(self, mock_session_getter):
        """Verifies parsing of Greenhouse API payload and HTML stripping without NameError."""
        mock_session = MagicMock()
        mock_session_getter.return_value = mock_session

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "jobs": [
                {
                    "id": 12345,
                    "title": "Security Analyst",
                    "absolute_url": "https://boards.greenhouse.io/corp/jobs/12345?gh_jid=12345",
                    "location": {"name": "Remote, US"},
                    "departments": [{"name": "Cyber Defense"}],
                    "updated_at": "2026-10-20T10:00:00Z",
                    "content": "<p>Handle <b>incident response</b> protocols.</p>",
                }
            ]
        }
        mock_session.get.return_value = fake_resp

        results = scraper.fetch_greenhouse_board(
            "corp",
            limit=10,
            evaluated_urls={"https://boards.greenhouse.io/corp/jobs/12345"},
            seen_urls=set()
        )

        self.assertEqual(len(results), 1)
        job = results[0]
        self.assertEqual(job["id"], "gh_12345")
        self.assertEqual(job["title"], "Security Analyst")
        self.assertEqual(job["location"], "Remote, US")
        self.assertEqual(job["department"], "Cyber Defense")
        self.assertIn("Handle", job["description"])
        self.assertIn("incident response", job["description"])
        self.assertIn("protocols.", job["description"])
        self.assertTrue(job["is_evaluated"])
        self.assertTrue(job["is_seen"])

    @patch("scraper._get_http_session")
    def test_fetch_ashby_board_mock(self, mock_session_getter):
        """Verifies Ashby posting API JSON parsing and remote location tagging."""
        mock_session = MagicMock()
        mock_session_getter.return_value = mock_session

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "jobs": [
                {
                    "id": "abc-789",
                    "title": "AI Research Scientist",
                    "jobUrl": "https://jobs.ashbyhq.com/lab/abc-789",
                    "isRemote": True,
                    "location": "",
                    "department": "Foundational Models",
                    "publishedAt": "2026-10-22T08:30:00.000Z",
                    "descriptionPlain": "Develop alignment research and evaluation harnesses.",
                }
            ]
        }
        mock_session.get.return_value = fake_resp

        results = scraper.fetch_ashby_board("lab", limit=5)
        self.assertEqual(len(results), 1)
        job = results[0]
        self.assertEqual(job["id"], "ashby_abc-789")
        self.assertEqual(job["title"], "AI Research Scientist")
        self.assertEqual(job["location"], "Remote")
        self.assertEqual(job["department"], "Foundational Models")
        self.assertEqual(job["description"], "Develop alignment research and evaluation harnesses.")
        self.assertFalse(job["is_evaluated"])

    @patch("scraper._get_http_session")
    def test_fetch_lever_board_mock(self, mock_session_getter):
        """Verifies Lever API JSON list parsing and date conversion from epoch milliseconds."""
        mock_session = MagicMock()
        mock_session_getter.return_value = mock_session

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = [
            {
                "id": "lever-456",
                "text": "Threat Detection Engineer",
                "hostedUrl": "https://jobs.lever.co/enterprise/lever-456",
                "categories": {
                    "location": "San Francisco, CA",
                    "team": "Security Operations"
                },
                "createdAt": 1761000000000,
                "descriptionPlain": "Build SIEM detection pipelines in Snowflake.",
            }
        ]
        mock_session.get.return_value = fake_resp

        results = scraper.fetch_lever_board("enterprise", limit=5)
        self.assertEqual(len(results), 1)
        job = results[0]
        self.assertEqual(job["id"], "lever_lever-456")
        self.assertEqual(job["title"], "Threat Detection Engineer")
        self.assertEqual(job["location"], "San Francisco, CA")
        self.assertEqual(job["department"], "Security Operations")
        self.assertEqual(job["description"], "Build SIEM detection pipelines in Snowflake.")

    @patch("scraper.fetch_greenhouse_board")
    @patch("scraper.fetch_ashby_board")
    @patch("scraper.fetch_lever_board")
    def test_fetch_ats_board_jobs_auto_detect_probing(self, mock_lever, mock_ashby, mock_gh):
        """Verifies that Auto-Detect probes Greenhouse, Ashby, and Lever until jobs are returned."""
        # Greenhouse 404/empty, Ashby returns jobs
        mock_gh.return_value = []
        mock_ashby.return_value = [{"id": "ashby_1", "title": "Job at Ashby"}]
        mock_lever.return_value = []

        results = scraper.fetch_ats_board_jobs("auto-detect", "target_company", limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Job at Ashby")
        mock_gh.assert_called_once()
        mock_ashby.assert_called_once()
        mock_lever.assert_not_called()

    def test_multi_source_scraper_results_accumulation(self):
        """Verifies that scraping multiple sources appends to scraper_results without deleting previous results."""
        # 1. Ingest Greenhouse jobs
        gh_jobs = [
            {"id": "gh_1", "title": "Security Analyst", "url": "https://boards.greenhouse.io/anthropic/jobs/1", "source": "Greenhouse (anthropic)"},
            {"id": "gh_2", "title": "Research Engineer", "url": "https://boards.greenhouse.io/anthropic/jobs/2", "source": "Greenhouse (anthropic)"},
        ]
        db.save_scraper_results(gh_jobs, "Greenhouse (anthropic)")
        loaded1 = db.load_scraper_results()
        self.assertEqual(len(loaded1), 2)

        # 2. Ingest Ashby jobs - should accumulate, NOT wipe Greenhouse!
        ashby_jobs = [
            {"id": "ashby_1", "title": "Model Alignment Lead", "url": "https://jobs.ashbyhq.com/openai/1", "source": "Ashby (openai)"},
        ]
        db.save_scraper_results(ashby_jobs, "Ashby (openai)")
        loaded2 = db.load_scraper_results()
        self.assertEqual(len(loaded2), 3)

        # 3. Ingest LinkedIn jobs - should accumulate, NOT wipe ATS!
        li_jobs = [
            {"id": "li_100", "title": "SOC Incident Lead", "url": "https://www.linkedin.com/jobs/view/100", "source": "LinkedIn Guest Search"},
        ]
        db.save_scraper_results(li_jobs, "LinkedIn Guest Search")
        loaded3 = db.load_scraper_results()
        self.assertEqual(len(loaded3), 4)

        sources = {j.get("source") for j in loaded3}
        self.assertIn("Greenhouse (anthropic)", sources)
        self.assertIn("Ashby (openai)", sources)
        self.assertIn("LinkedIn Guest Search", sources)

        # 4. Clear by source
        db.clear_scraper_results(source="LinkedIn Guest Search")
        loaded_after_src_clear = db.load_scraper_results()
        self.assertEqual(len(loaded_after_src_clear), 3)
        sources_remaining = {j.get("source") for j in loaded_after_src_clear}
        self.assertNotIn("LinkedIn Guest Search", sources_remaining)
        self.assertIn("Greenhouse (anthropic)", sources_remaining)
        self.assertIn("Ashby (openai)", sources_remaining)


if __name__ == "__main__":
    unittest.main()
