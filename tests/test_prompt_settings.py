import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import utils
import streamlit as st


class TestPromptSettingsAndPriority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_prompt_tests"))
        os.makedirs(cls.test_dir, exist_ok=True)
        
        cls.orig_db_path = db.DB_PATH
        cls.orig_db_file = db.DB_FILE
        cls.orig_profile_json = getattr(db, "PROFILE_JSON_FILE", "profile_alignment.json")
        cls.orig_settings_json = getattr(db, "SETTINGS_JSON_FILE", "app_settings.json")
        cls.orig_custom_prompt = utils.CUSTOM_PROMPT_FILE
        cls.orig_custom_user_prompt = utils.CUSTOM_USER_PROMPT_FILE

        cls.test_db = os.path.join(cls.test_dir, "test_skippy.db")
        cls.test_profile_json = os.path.join(cls.test_dir, "test_profile_alignment.json")
        cls.test_settings_json = os.path.join(cls.test_dir, "test_app_settings.json")
        cls.test_custom_prompt = os.path.join(cls.test_dir, "test_custom_prompt.txt")
        cls.test_custom_user_prompt = os.path.join(cls.test_dir, "test_custom_user_prompt.txt")

    def setUp(self):
        db.DB_PATH = self.test_db
        db.DB_FILE = self.test_db
        db.PROFILE_JSON_FILE = self.test_profile_json
        db.SETTINGS_JSON_FILE = self.test_settings_json
        utils.CUSTOM_PROMPT_FILE = self.test_custom_prompt
        utils.CUSTOM_USER_PROMPT_FILE = self.test_custom_user_prompt
        db.init_db()

        # Clean session state
        st.session_state.clear()

    def tearDown(self):
        st.session_state.clear()
        for fpath in [
            self.test_db,
            self.test_profile_json,
            self.test_settings_json,
            self.test_custom_prompt,
            self.test_custom_user_prompt,
        ]:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.orig_db_path
        db.DB_FILE = cls.orig_db_file
        db.PROFILE_JSON_FILE = cls.orig_profile_json
        db.SETTINGS_JSON_FILE = cls.orig_settings_json
        utils.CUSTOM_PROMPT_FILE = cls.orig_custom_prompt
        utils.CUSTOM_USER_PROMPT_FILE = cls.orig_custom_user_prompt
        if os.path.exists(cls.test_dir):
            try:
                import shutil
                shutil.rmtree(cls.test_dir, ignore_errors=True)
            except Exception:
                pass

    def test_database_get_and_set_setting(self):
        """Verifies persistent key-value setting storage with JSON fallback."""
        success = db.set_setting("test_key", "test_value_123")
        self.assertTrue(success)
        self.assertEqual(db.get_setting("test_key"), "test_value_123")
        self.assertEqual(db.get_setting("non_existent_key", "default_val"), "default_val")

        # Verify JSON file was written
        self.assertTrue(os.path.exists(self.test_settings_json))
        with open(self.test_settings_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data.get("test_key"), "test_value_123")

    def test_load_and_save_custom_user_prompt(self):
        """Verifies custom user prompt persistence independently of compass prompt."""
        custom_rubric = "CUSTOM SCORING: Strictly score candidates on hands-on lab projects."
        utils.save_custom_user_prompt(custom_rubric)

        loaded = utils.load_custom_user_prompt()
        self.assertEqual(loaded, custom_rubric)
        self.assertTrue(os.path.exists(self.test_custom_user_prompt))

    def test_prompt_mode_resolution_and_default(self):
        """Verifies prompt_mode defaults to compass if archetype exists, otherwise custom."""
        # Case 1: No profile exists -> defaults to custom
        mode = utils.get_prompt_mode()
        self.assertEqual(mode, utils.PROMPT_MODE_CUSTOM)

        st.session_state.clear()

        # Case 2: User profile has an archetype title -> defaults to compass
        db.save_user_profile({
            "archetype_title": "Network Security Engineer",
            "adapted_prompt": "Specialized Network Security Rubric"
        })
        st.session_state["user_profile"] = db.load_user_profile()
        mode = utils.get_prompt_mode()
        self.assertEqual(mode, utils.PROMPT_MODE_COMPASS)

    def test_set_active_prompt_mode_swaps_instructions(self):
        """Verifies switching prompt mode updates session_state and mirrors to custom_prompt.txt."""
        compass_text = "COMPASS PROMPT: Focus on SOC alert handling."
        custom_text = "CUSTOM PROMPT: Focus on algorithm complexity."

        db.save_user_profile({
            "archetype_title": "SOC Analyst",
            "adapted_prompt": compass_text
        })
        st.session_state["user_profile"] = db.load_user_profile()
        utils.save_custom_user_prompt(custom_text)

        # Switch to Compass
        utils.set_active_prompt_mode(utils.PROMPT_MODE_COMPASS)
        self.assertEqual(st.session_state["prompt_mode"], utils.PROMPT_MODE_COMPASS)
        self.assertEqual(st.session_state.system_instructions, compass_text)
        with open(self.test_custom_prompt, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), compass_text)

        details = utils.get_active_prompt_details()
        self.assertTrue(details["is_compass"])
        self.assertIn("SOC Analyst", details["title"])

        # Switch to Custom
        utils.set_active_prompt_mode(utils.PROMPT_MODE_CUSTOM)
        self.assertEqual(st.session_state["prompt_mode"], utils.PROMPT_MODE_CUSTOM)
        self.assertEqual(st.session_state.system_instructions, custom_text)
        with open(self.test_custom_prompt, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), custom_text)

        details = utils.get_active_prompt_details()
        self.assertFalse(details["is_compass"])
        self.assertEqual(details["mode"], utils.PROMPT_MODE_CUSTOM)

    def test_non_destructive_separation(self):
        """Verifies changing compass profile does NOT erase custom prompt and vice-versa."""
        custom_text = "MY SACRED CUSTOM PROMPT"
        utils.save_custom_user_prompt(custom_text)

        # Update Career Compass Profile
        compass_text = "NEW COMPASS PROMPT"
        db.save_user_profile({
            "archetype_title": "Ammonia Technician",
            "adapted_prompt": compass_text
        })
        st.session_state["user_profile"] = db.load_user_profile()

        # Custom user prompt file should still have untouched custom text
        self.assertEqual(utils.load_custom_user_prompt(), custom_text)

        # Saving a new custom prompt should not alter compass profile
        updated_custom = "MY UPDATED CUSTOM PROMPT"
        utils.save_custom_user_prompt(updated_custom)
        profile = db.load_user_profile()
        self.assertEqual(profile["adapted_prompt"], compass_text)

    def test_render_active_prompt_indicator_runs(self):
        """Verifies the UI indicator render function executes cleanly without throwing."""
        with patch.object(st, "caption") as mock_caption:
            utils.set_active_prompt_mode(utils.PROMPT_MODE_CUSTOM)
            utils.render_active_prompt_indicator()
            mock_caption.assert_called()

            utils.set_active_prompt_mode(utils.PROMPT_MODE_COMPASS)
            utils.render_active_prompt_indicator()
            self.assertGreaterEqual(mock_caption.call_count, 2)


if __name__ == "__main__":
    unittest.main()
