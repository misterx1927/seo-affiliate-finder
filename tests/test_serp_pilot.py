import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from src.providers import DataForSEO, RequestAllowance
from src.serp import SerpError, build_task, parse_response

class SerpPilotTests(unittest.TestCase):
    def test_depth_20_configuration_and_first_ten(self):
        self.assertEqual(build_task("online casino canada", 20)["depth"], 20)
        self.assertTrue(build_task("online casino canada", 20)["resolve_goto_urls"])
        with self.assertRaises(ValueError): build_task("test", 100)
        payload = json.loads(Path("tests/fixtures/dataforseo.json").read_text(encoding="utf-8-sig"))
        items = payload["tasks"][0]["result"][0]["items"]
        for i in range(4, 13): items.append({"type":"organic", "rank_group":i, "url":f"https://result{i}.example"})
        self.assertEqual([r.position for r in parse_response(payload)], list(range(1, 11)))
        calls = []
        def transport(url, data, headers): calls.append(data); return payload
        provider = DataForSEO("test", "test", RequestAllowance(1, 0, approved=True), transport, depth=20)
        self.assertEqual(len(provider.search("online casino canada")), 10)
        self.assertEqual(calls[0][0]["depth"], 20)
    def test_default_is_offline_without_credentials(self):
        env = dict(os.environ)
        for key in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"): env.pop(key, None)
        result = subprocess.run([sys.executable, "serp_only.py"], capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("DRY RUN", result.stdout)

if __name__ == "__main__": unittest.main()
