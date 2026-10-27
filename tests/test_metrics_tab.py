import os
import unittest
from unittest.mock import patch, MagicMock
from streamlit.testing.v1 import AppTest


class TestMetricsUpskillTab(unittest.TestCase):
    """Verifies that generating and managing the upskill roadmap gracefully stays on the roadmap tab."""

    def test_metrics_page_upskill_tab_retention(self):
        metrics_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pages", "3_metrics.py"))
        at = AppTest.from_file(metrics_path)

        mock_jobs = [
            {
                "id": "job1",
                "Position": "Security Analyst",
                "Company": "CyberCorp",
                "Score": 75,
                "Eligible": True,
                "Missing Skills": "SIEM Alert Triage, Wireshark",
                "Technical Score": 25,
                "Experience Score": 20,
                "Behavioral Score": 15,
                "Career Score": 15,
                "Status": "new",
            },
            {
                "id": "job2",
                "Position": "SOC Lead",
                "Company": "DefenderNet",
                "Score": 60,
                "Eligible": True,
                "Missing Skills": "CompTIA Security+, Python Automation",
                "Technical Score": 20,
                "Experience Score": 15,
                "Behavioral Score": 10,
                "Career Score": 15,
                "Status": "new",
            }
        ]

        with patch("database.load_all_jobs", return_value=mock_jobs), \
             patch("evaluator.generate_upskill_roadmap", return_value="### Strategic Upskill Plan\n- Learn Wireshark\n- Master SIEM"):
            at.run()
            self.assertFalse(at.exception)

            # Find the generate roadmap button
            gen_buttons = [b for b in at.button if "Generate Personalized Upskill" in b.label]
            self.assertEqual(len(gen_buttons), 1)

            # Click generate roadmap
            gen_buttons[0].click()
            at.run()
            self.assertFalse(at.exception)

            # Verify roadmap markdown was rendered directly without error
            self.assertTrue(any("Strategic Upskill Plan" in m.value for m in at.markdown))
            self.assertEqual(at.session_state["upskill_roadmap_md"], "### Strategic Upskill Plan\n- Learn Wireshark\n- Master SIEM")

            # Verify Clear button is now visible
            clear_buttons = [b for b in at.button if "Clear Roadmap" in b.label]
            self.assertEqual(len(clear_buttons), 1)

            # Click Clear button
            clear_buttons[0].click()
            at.run()
            self.assertFalse(at.exception)
            self.assertEqual(at.session_state["upskill_roadmap_md"], "")


if __name__ == "__main__":
    unittest.main()
