import os
import unittest
from pathlib import Path
from unittest.mock import patch
from src.config import load_env

class ConfigTests(unittest.TestCase):
    def test_load_does_not_evaluate_and_environment_wins(self):
        path = Path("data/test-settings.env")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        path.write_text("DATAFORSEO_LOGIN=from_file\nOPENAI_API_KEY=$(not_executed)\n", encoding="utf-8")
        with patch.dict(os.environ, {"DATAFORSEO_LOGIN":"existing"}, clear=True):
            load_env(path)
            self.assertEqual(os.environ["DATAFORSEO_LOGIN"], "existing")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "$(not_executed)")
    def test_rejects_unknown_settings_without_disclosing_values(self):
        path = Path("data/test-settings.env")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        path.write_text("BAD_KEY=secret\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unsupported"): load_env(path)

if __name__ == "__main__": unittest.main()
