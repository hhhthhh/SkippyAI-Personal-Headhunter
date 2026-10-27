import unittest
from datetime import datetime, timedelta
import importlib
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import modules with numerical prefix via importlib
metrics_mod = importlib.import_module("pages.3_metrics")
funnel_mod = importlib.import_module("pages.8_pipeline_funnel")
parse_date_safely = funnel_mod.parse_date_safely
compute_sankey_data = funnel_mod.compute_sankey_data
build_sankey_figure = funnel_mod.build_sankey_figure
import database as db


class TestSankeyPipeline(unittest.TestCase):
    def test_backwards_compatible_reexports(self):
        """Verifies that pages.3_metrics continues to export Sankey utilities."""
        self.assertTrue(callable(metrics_mod.parse_date_safely))
        self.assertTrue(callable(metrics_mod.compute_sankey_data))
        self.assertTrue(callable(metrics_mod.build_sankey_figure))
        self.assertTrue(callable(metrics_mod.render_sankey_section))
        self.assertTrue(callable(metrics_mod.generate_safe_job_key))
    def test_parse_date_safely(self):
        # Standard formats
        dt1 = parse_date_safely("2026-10-20 14:30")
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.year, 2026)
        self.assertEqual(dt1.month, 10)
        self.assertEqual(dt1.day, 20)

        dt2 = parse_date_safely("2026-05-12")
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.month, 5)

        dt3 = parse_date_safely("2026/08/15")
        self.assertIsNotNone(dt3)
        self.assertEqual(dt3.month, 8)

        # Edge cases
        self.assertIsNone(parse_date_safely(None))
        self.assertIsNone(parse_date_safely(""))
        self.assertIsNone(parse_date_safely("Not a date"))

    def test_compute_sankey_data_empty(self):
        res = compute_sankey_data([])
        self.assertEqual(res, {})

    def test_compute_sankey_data_full_pipeline(self):
        now = datetime.now()
        recent_date = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        old_date = (now - timedelta(days=25)).strftime("%Y-%m-%d %H:%M")

        jobs = [
            # Ineligible job
            {"URL": "url_inelig", "Eligible": False, "Score": 20},
            # Eligible but Not Applied
            {"URL": "url_saved", "Eligible": True, "Application Status": "Not Applied", "Score": 85},
            # Applied recently (< 14 days) -> Awaiting Response
            {"URL": "url_applied_recent", "Eligible": True, "Application Status": "Applied", "Timestamp": recent_date},
            # Applied long ago (>= 14 days) -> Stale / Ghosted
            {"URL": "url_applied_stale", "Eligible": True, "Application Status": "Applied", "Timestamp": old_date},
            # Explicitly rejected at application stage
            {"URL": "url_rej_app", "Eligible": True, "Application Status": "Rejected (Application)"},
            # Active interview
            {"URL": "url_interview", "Eligible": True, "Application Status": "Interviewing"},
            # Waitlisted
            {"URL": "url_waitlist", "Eligible": True, "Application Status": "Waitlisted"},
            # Rejected post interview
            {"URL": "url_rej_int", "Eligible": True, "Application Status": "Rejected (Interview)"},
            # Offer received!
            {"URL": "url_offer", "Eligible": True, "Application Status": "Offer"},
        ]

        data = compute_sankey_data(jobs, stale_days=14)
        self.assertEqual(data["total"], 9)
        self.assertEqual(len(data["ineligible"]), 1)
        self.assertEqual(len(data["eligible"]), 8)
        self.assertEqual(len(data["not_applied"]), 1)
        self.assertEqual(len(data["applied_all"]), 7)

        # Applied breakdown
        self.assertEqual(len(data["awaiting_response"]), 1)
        self.assertEqual(len(data["stale_ghosted"]), 1)
        self.assertEqual(len(data["rejected_app"]), 1)
        self.assertEqual(len(data["interviewing_all"]), 4)

        # Interview breakdown
        self.assertEqual(len(data["active_interviews"]), 1)
        self.assertEqual(len(data["waitlisted"]), 1)
        self.assertEqual(len(data["rejected_interview"]), 1)
        self.assertEqual(len(data["offers"]), 1)

        # Conversion rates
        # Apply rate: 7 applied / 8 eligible = 87.5%
        self.assertAlmostEqual(data["apply_rate"], 87.5, places=1)
        # Screen rate: 4 interviewing / 7 applied = 57.1%
        self.assertAlmostEqual(data["screen_rate"], 57.1, places=1)
        # Offer rate: 1 offer / 7 applied = 14.3%
        self.assertAlmostEqual(data["offer_rate"], 14.3, places=1)

    def test_stale_to_moving_forward_transition(self):
        """Tests that when an application is stale, updating status to Interviewing moves it forward."""
        now = datetime.now()
        old_date = (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M")

        # Initial stale job
        stale_job = {
            "URL": "https://example.com/job_stale",
            "Eligible": True,
            "Application Status": "Applied",
            "Timestamp": old_date,
            "Status Updated": ""
        }

        data_before = compute_sankey_data([stale_job], stale_days=14)
        self.assertEqual(len(data_before["stale_ghosted"]), 1)
        self.assertEqual(len(data_before["interviewing_all"]), 0)

        # User hears back! Status moves to Interviewing
        stale_job["Application Status"] = "Interviewing"
        stale_job["Status Updated"] = now.strftime("%Y-%m-%d %H:%M")

        data_after = compute_sankey_data([stale_job], stale_days=14)
        self.assertEqual(len(data_after["stale_ghosted"]), 0)
        self.assertEqual(len(data_after["interviewing_all"]), 1)
        self.assertEqual(len(data_after["active_interviews"]), 1)

    def test_build_sankey_figure(self):
        jobs = [
            {"URL": "url_1", "Eligible": True, "Application Status": "Applied"},
            {"URL": "url_2", "Eligible": True, "Application Status": "Interviewing"},
            {"URL": "url_3", "Eligible": False},
        ]
        data = compute_sankey_data(jobs)
        fig = build_sankey_figure(data)
        self.assertIsNotNone(fig)
        self.assertTrue(hasattr(fig, "data"))
        self.assertGreater(len(fig.data[0].link.source), 0)
        # Verify no 0 values exist in links
        for val in fig.data[0].link.value:
            self.assertGreater(val, 0)
        # Verify specified horizontal stage lengths are present
        self.assertTrue(hasattr(fig.data[0].node, "x"))
        self.assertIn(0.001, fig.data[0].node.x)
        self.assertIn(0.25, fig.data[0].node.x)
        self.assertIn(0.50, fig.data[0].node.x)
        self.assertIn(0.75, fig.data[0].node.x)
        self.assertIn(0.999, fig.data[0].node.x)

    def test_database_status_update_with_timestamp(self):
        """Verifies that updating Application Status stamps Status Updated in database."""
        test_url = "https://example.com/test_sankey_job_url"
        # Insert a job
        db.save_job_result({
            "URL": test_url,
            "Position": "Test SOC Lead",
            "Eligible": True,
            "Score": 88,
            "Company": "Test Cyber Corp",
            "Job Text": "Job Text",
        })

        try:
            # Change status to Applied
            db.update_job_field(test_url, "Application Status", "Applied")
            jobs = db.load_all_jobs()
            match = next((j for j in jobs if j.get("URL") == test_url), None)
            self.assertIsNotNone(match)
            self.assertEqual(match["Application Status"], "Applied")
            self.assertTrue(len(match.get("Status Updated", "")) > 0)

            # Advance to Interviewing
            db.update_job_field(test_url, "Application Status", "Interviewing")
            jobs_after = db.load_all_jobs()
            match_after = next((j for j in jobs_after if j.get("URL") == test_url), None)
            self.assertEqual(match_after["Application Status"], "Interviewing")
        finally:
            # Cleanup test job
            conn = db.get_connection()
            with conn:
                conn.execute('DELETE FROM jobs WHERE "URL" = ?', (test_url,))
            conn.close()

    def test_generate_safe_job_key(self):
        """Tests that generate_safe_job_key produces deterministic, collision-free widget keys."""
        job1 = {"URL": "https://example.com/job/1", "Position": "DevOps", "Company": "Acme"}
        job1_dup = {"URL": "https://example.com/job/1", "Position": "DevOps", "Company": "Acme"}
        job2 = {"URL": "https://example.com/job/2", "Position": "SRE", "Company": "Beta"}
        job_no_url = {"Position": "Lead", "Company": "Gamma", "Timestamp": "2026-10-22 12:00"}

        key1 = funnel_mod.generate_safe_job_key(job1, prefix="sankey_status")
        key1_dup = funnel_mod.generate_safe_job_key(job1_dup, prefix="sankey_status")
        key2 = funnel_mod.generate_safe_job_key(job2, prefix="sankey_status")
        key_no_url = funnel_mod.generate_safe_job_key(job_no_url, prefix="quick_adv")

        # Deterministic
        self.assertEqual(key1, key1_dup)
        # Distinct
        self.assertNotEqual(key1, key2)
        # Prefixed
        self.assertTrue(key1.startswith("sankey_status_"))
        self.assertTrue(key_no_url.startswith("quick_adv_"))
        # Clean hex format without whitespace or special characters
        hex_part = key1.split("sankey_status_")[1]
        self.assertEqual(len(hex_part), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_database_update_trailing_slash_resilience(self):
        """Verifies that update_job_field handles trailing slash discrepancies without failing."""
        test_url = "https://example.com/job/trailing_test/"
        db.save_job_result({
            "URL": test_url,
            "Position": "Test Role",
            "Eligible": True,
            "Score": 80,
            "Job Text": "Job Text",
        })

        try:
            # Update using URL without trailing slash
            updated = db.update_job_field("https://example.com/job/trailing_test", "Application Status", "Interviewing")
            self.assertTrue(updated)
            jobs = db.load_all_jobs()
            match = next((j for j in jobs if "trailing_test" in j.get("URL", "")), None)
            self.assertIsNotNone(match)
            self.assertEqual(match["Application Status"], "Interviewing")
        finally:
            conn = db.get_connection()
            with conn:
                conn.execute('DELETE FROM jobs WHERE "URL" LIKE ?', ("%trailing_test%",))
            conn.close()

    def test_sankey_stage_keys_alignment(self):
        """Verifies that stage dropdown identifiers align with compute_sankey_data keys."""
        dummy_data = compute_sankey_data([{"URL": "u", "Eligible": True, "Application Status": "Applied"}])
        expected_stages = [
            "applied_all",
            "awaiting_response",
            "stale_ghosted",
            "interviewing_all",
            "offers",
            "waitlisted",
            "rejected_app",
            "rejected_interview",
            "not_applied",
            "ineligible",
        ]
        for stage in expected_stages:
            self.assertIn(stage, dummy_data, f"Stage key '{stage}' missing from compute_sankey_data output")

    def test_metrics_and_sankey_page_isolation(self):
        """Verifies that visiting Metrics page never accidentally executes or renders the Sankey funnel."""
        from streamlit.testing.v1 import AppTest

        metrics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pages", "3_metrics.py"))
        at_metrics = AppTest.from_file(metrics_path)
        at_metrics.run()
        self.assertFalse(at_metrics.exception)
        subheaders = [s.value for s in at_metrics.subheader]
        self.assertNotIn("🌊 Application Conversion Funnel", subheaders)

        funnel_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pages", "8_pipeline_funnel.py"))
        at_funnel = AppTest.from_file(funnel_path)
        at_funnel.run()
        self.assertFalse(at_funnel.exception)
        funnel_subheaders = [s.value for s in at_funnel.subheader]
        self.assertTrue(any("Application" in s for s in funnel_subheaders))


if __name__ == "__main__":
    unittest.main()
