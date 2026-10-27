"""
Unit tests for the Skippy onboarding flow, single-launch guarantee,
sample datasets, and AI connection diagnostics.
"""

import os
import unittest
import tempfile
import io
from unittest.mock import patch, MagicMock

import database as db
from sample_data import SAMPLE_RESUMES, SAMPLE_JOBS, test_ai_connection
from utils import parse_resume_file


class TestOnboardingFlow(unittest.TestCase):

    def setUp(self):
        self.original_onboarding_flag = db.get_setting("onboarding_completed", "")

    def tearDown(self):
        if self.original_onboarding_flag:
            db.set_setting("onboarding_completed", self.original_onboarding_flag)
        else:
            db.set_setting("onboarding_completed", "")

    def test_single_launch_persistence_and_bypass(self):
        """Verify that marking onboarding completed is persistent across app launches."""
        # 1. Mark completed
        db.mark_onboarding_completed()
        self.assertTrue(db.is_onboarding_completed())
        self.assertEqual(db.get_setting("onboarding_completed"), "true")

        # 2. Reset and verify
        db.reset_onboarding_status()
        self.assertEqual(db.get_setting("onboarding_completed"), "false")

        # 3. Mark completed again
        db.mark_onboarding_completed()
        self.assertTrue(db.is_onboarding_completed())

    def test_sample_resumes_structure(self):
        """Ensure all 4 built-in sample resumes are present, rich, and well-structured."""
        expected_keys = [
            "Software & Cloud Engineer",
            "Clinical Healthcare Specialist",
            "Operations & Supply Chain Lead",
            "Skilled Trades & Automation Technician",
        ]
        for key in expected_keys:
            self.assertIn(key, SAMPLE_RESUMES)
            resume_content = SAMPLE_RESUMES[key]
            self.assertIsInstance(resume_content, str)
            self.assertGreater(len(resume_content), 300)
            self.assertIn("# ", resume_content)
            self.assertTrue("Experience" in resume_content or "Work History" in resume_content)

    def test_sample_jobs_structure(self):
        """Ensure built-in demo jobs provide realistic descriptions for 1-click test drives."""
        self.assertIsInstance(SAMPLE_JOBS, list)
        self.assertGreaterEqual(len(SAMPLE_JOBS), 3)
        for job in SAMPLE_JOBS:
            self.assertIn("title", job)
            self.assertIn("company", job)
            self.assertIn("text", job)
            self.assertGreater(len(job["text"]), 100)

    def test_ai_connection_tester_empty_key(self):
        """Verify connection tester catches empty API keys before making network requests."""
        ok, msg = test_ai_connection("Google Gemini", "")
        self.assertFalse(ok)
        self.assertIn("Please provide an API key", msg)

        ok2, msg2 = test_ai_connection("OpenAI ChatGPT", "   ")
        self.assertFalse(ok2)
        self.assertIn("Please provide an API key", msg2)

    @patch("evaluator._get_completion")
    def test_ai_connection_tester_success(self, mock_get_completion):
        """Verify connection tester reports success when provider responds with choices."""
        mock_completion = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "OK"
        mock_response.choices = [mock_choice]
        mock_completion.return_value = mock_response
        mock_get_completion.return_value = mock_completion

        ok, msg = test_ai_connection("Google Gemini", "fake_key_12345")
        self.assertTrue(ok)
        self.assertIn("verified successfully", msg.lower())

    @patch("evaluator._get_completion")
    def test_ai_connection_tester_error_translation(self, mock_get_completion):
        """Verify connection tester translates provider exceptions into user-friendly messages."""
        mock_completion = MagicMock()
        mock_completion.side_effect = Exception("API_KEY_INVALID: 401 Unauthorized")
        mock_get_completion.return_value = mock_completion

        ok, msg = test_ai_connection("Google Gemini", "bad_key")
        self.assertFalse(ok)
        self.assertIn("Invalid API key", msg)

    def test_parse_resume_file_text_and_md(self):
        """Verify resume file parsing for uploaded text and markdown documents."""
        # Mock markdown file
        md_file = io.BytesIO(b"# Candidate Name\n\nExperience:\n- Dev at Acme")
        md_file.name = "my_resume.md"
        parsed_md = parse_resume_file(md_file)
        self.assertIn("Candidate Name", parsed_md)
        self.assertIn("Acme", parsed_md)

        # Mock plain text file
        txt_file = io.BytesIO(b"Jane Doe\nOperations Specialist\n5 years experience")
        txt_file.name = "resume.txt"
        parsed_txt = parse_resume_file(txt_file)
        self.assertIn("Jane Doe", parsed_txt)


if __name__ == "__main__":
    unittest.main()
