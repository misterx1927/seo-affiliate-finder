import os
import subprocess
import sys
import unittest

class CliSafetyTests(unittest.TestCase):
    def test_default_and_full_dry_runs_do_not_need_credentials(self):
        env = dict(os.environ)
        for name in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "OPENAI_API_KEY", "OPENAI_MODEL"):
            env.pop(name, None)
        for extra in ([], ["--mode", "full"]):
            result = subprocess.run([sys.executable, "pilot.py", *extra], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("DRY RUN", result.stdout)
    def test_full_requires_explicit_second_confirmation(self):
        result = subprocess.run([sys.executable, "pilot.py", "--mode", "full", "--allow-paid"], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --confirm-full", result.stderr)

if __name__ == "__main__": unittest.main()
