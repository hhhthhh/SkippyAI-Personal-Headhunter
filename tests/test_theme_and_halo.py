import os
import unittest
from unittest.mock import patch, MagicMock
from utils import inject_interactive_hover_halo_effects

class TestThemeAndHaloEffects(unittest.TestCase):
    def test_streamlit_config_dark_theme(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "config.toml")
        self.assertTrue(os.path.exists(config_path), ".streamlit/config.toml should exist")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('base = "dark"', content)
        self.assertIn("primaryColor", content)
        self.assertIn("#2563eb", content)
        self.assertIn('backgroundColor = "#0e1117"', content)

    @patch("streamlit.markdown")
    def test_inject_interactive_hover_halo_effects_blue_and_white(self, mock_markdown):
        inject_interactive_hover_halo_effects()
        mock_markdown.assert_called_once()
        css_content = mock_markdown.call_args[0][0]

        # Verify blue button styling
        self.assertIn("#2563eb", css_content)
        self.assertIn("#1d4ed8", css_content)
        self.assertIn("#1e40af", css_content)
        self.assertIn("#ffffff", css_content)

        # Verify blue and white halo effects (59, 130, 246 / 255, 255, 255)
        self.assertIn("rgba(59, 130, 246", css_content)
        self.assertIn("rgba(255, 255, 255", css_content)

        # Verify red halo effects are eliminated from the injected styles
        self.assertNotIn("rgba(255, 75, 75", css_content)

if __name__ == "__main__":
    unittest.main()
