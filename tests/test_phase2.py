import unittest
import sys
import os
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import evaluator
import scraper


class TestPhase2Features(unittest.TestCase):
    def setUp(self):
        # Use an in-memory or isolated test database
        self.test_db = "test_phase2_skippy.db"
        db.DB_PATH = self.test_db
        db.DB_FILE = self.test_db
        db.init_db()

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except OSError:
                pass
        db.DB_PATH = "skippy.db"
        db.DB_FILE = "skippy.db"

    def test_database_schema_columns(self):
        """Verifies Phase 2 migration adds Outreach Message, Company Intel, and Applied Date."""
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("PRAGMA table_info(jobs)")
        cols = {r[1] for r in c.fetchall()}
        conn.close()

        self.assertIn("Outreach Message", cols)
        self.assertIn("Company Intel", cols)
        self.assertIn("Applied Date", cols)

    def test_detect_job_reposts_temporal_span(self):
        """Verifies detect_job_reposts detects requisitions reposted across >= 7 days."""
        now = datetime.now()
        date_old = (now - timedelta(days=25)).strftime("%Y-%m-%d %H:%M")
        date_new = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")

        # Insert historical job
        db.save_job_result({
            "Timestamp": date_old,
            "Position": "Clinical Research Coordinator",
            "Company": "BioHealth Labs",
            "URL": "https://example.com/jobs/101",
            "Score": 80,
            "Eligible": True,
        })

        # Insert seen posting from same company with same role 23 days later
        db.record_seen_postings([{
            "id": "bh_202",
            "title": "Clinical Research Coordinator",
            "company": "BioHealth Labs",
            "url": "https://example.com/jobs/202",
            "date": date_new,
            "seen_at": date_new,
        }])

        reposts = db.detect_job_reposts(
            company="BioHealth Labs",
            role="Clinical Research Coordinator",
            current_url="https://example.com/jobs/202",
            window_days=90,
        )
        self.assertGreaterEqual(len(reposts), 2)
        risk = db.check_repost_risk(
            company="BioHealth Labs",
            role="Clinical Research Coordinator",
            current_url="https://example.com/jobs/202",
            window_days=90,
        )
        self.assertIsNotNone(risk)
        self.assertTrue(risk["is_ghost_risk"])
        self.assertIn("Relisted", risk["badge_text"])

    def test_detect_job_reposts_ignores_concurrent_same_day(self):
        """Verifies multiple postings on the same day (< 7 days apart) are not flagged as reposts."""
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        db.save_job_result({
            "Timestamp": now_ts,
            "Position": "Staff Accountant",
            "Company": "Acme Finance",
            "URL": "https://example.com/jobs/301",
            "Score": 75,
            "Eligible": True,
        })
        db.record_seen_postings([{
            "id": "acme_302",
            "title": "Staff Accountant",
            "company": "Acme Finance",
            "url": "https://example.com/jobs/302",
            "date": now_ts,
            "seen_at": now_ts,
        }])

        reposts = db.detect_job_reposts(
            company="Acme Finance",
            role="Staff Accountant",
            current_url="https://example.com/jobs/302",
            window_days=90,
        )
        self.assertEqual(len(reposts), 0)

    def test_enforce_char_limit(self):
        """Verifies LinkedIn message character cap strictly honors <= 300 characters."""
        long_text = "Word " * 80  # 400 chars
        capped = evaluator._enforce_char_limit(long_text, limit=300)
        self.assertLessEqual(len(capped), 300)
        self.assertTrue(capped.endswith("..."))

        short_text = "This is a short connection note."
        self.assertEqual(evaluator._enforce_char_limit(short_text, limit=300), short_text)

    def test_ats_linter(self):
        """Verifies ATS resume linter flags missing contact info and non-ASCII dashes."""
        bad_resume = """
## WORK EXPERIENCE
Some job at Company – 2021 to 2023
- Built an internal tool that did a lot of things without any numbers or metrics
"""
        res = evaluator.lint_ats_resume(bad_resume)
        self.assertLess(res["score"], 80)
        rules = [iss["rule"] for iss in res["issues"]]
        self.assertIn("Contact Info", rules)
        self.assertIn("ASCII Characters", rules)
        # Verify clean_markdown replaces Unicode dash
        self.assertNotIn("–", res["clean_markdown"])
        self.assertIn("-", res["clean_markdown"])

    def test_extract_ats_board_info(self):
        """Verifies URL extraction for Greenhouse, Ashby, and Lever."""
        p1, t1 = scraper.extract_ats_board_info("https://boards.greenhouse.io/anthropic")
        self.assertEqual(p1, "greenhouse")
        self.assertEqual(t1, "anthropic")

        p2, t2 = scraper.extract_ats_board_info("https://jobs.ashbyhq.com/openai")
        self.assertEqual(p2, "ashby")
        self.assertEqual(t2, "openai")

        p3, t3 = scraper.extract_ats_board_info("https://jobs.lever.co/stripe")
        self.assertEqual(p3, "lever")
        self.assertEqual(t3, "stripe")

        p4, t4 = scraper.extract_ats_board_info("cloudflare", default_platform="greenhouse")
        self.assertEqual(p4, "greenhouse")
        self.assertEqual(t4, "cloudflare")

    def test_rejection_latency_and_turnaround_metrics(self):
        """Verifies pipeline turnaround calculation between Applied Date and Status Updated."""
        url = "https://example.com/jobs/latency_test"
        db.save_job_result({
            "Timestamp": "2026-10-01 10:00",
            "Position": "Supply Chain Planner",
            "Company": "LogiCorp",
            "URL": url,
            "Score": 85,
            "Eligible": True,
            "Application Status": "Applied",
        })
        db.update_job_field(url, "Applied Date", "2026-10-01 10:00")
        db.update_job_field(url, "Status Updated", "2026-10-08 14:00")
        db.update_job_field(url, "Application Status", "Interviewing")

        metrics = db.get_pipeline_turnaround_metrics()
        self.assertEqual(metrics["total_interviewed"], 1)
        self.assertGreaterEqual(metrics["avg_interview_days"], 7.0)

    def test_strip_json_fences_with_preamble(self):
        """Verifies _strip_json_fences handles preamble text, markdown tags, and clean json."""
        raw = 'Here is the response:\n```json\n{"position_name": "Dev", "match_score": 90}\n```\nHope this helps!'
        cleaned = evaluator._strip_json_fences(raw)
        self.assertEqual(cleaned, '{"position_name": "Dev", "match_score": 90}')

        raw_clean = '```\n{"test": true}\n```'
        self.assertEqual(evaluator._strip_json_fences(raw_clean), '{"test": true}')

    def test_company_intel_database_field_update(self):
        """Verifies Company Intel field can be updated and retrieved safely in DB."""
        url = "https://example.com/jobs/intel_test"
        db.save_job_result({
            "Timestamp": "2026-10-02 10:00",
            "Position": "Analyst",
            "Company": "Apex Corp",
            "URL": url,
            "Score": 80,
            "Eligible": True,
        })
        dossier_text = "# Strategic Company Dossier\n\n## 1. Core Business Model\nEnterprise SaaS."
        success = db.update_job_field(url, "Company Intel", dossier_text)
        self.assertTrue(success)

        all_jobs = db.load_all_jobs()
        saved = next((j for j in all_jobs if j.get("URL") == url), None)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.get("Company Intel"), dossier_text)


if __name__ == "__main__":
    unittest.main()
