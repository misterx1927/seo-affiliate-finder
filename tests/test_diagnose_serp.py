import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from diagnose_serp import diagnostic_task, run_one, summarize


class DiagnosticTests(unittest.TestCase):
    def test_default_dry_run_does_not_require_credentials(self):
        env = dict(os.environ)
        for key in ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"):
            env.pop(key, None)
        result = subprocess.run([sys.executable, "diagnose_serp.py"], capture_output=True,
                                text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("DRY RUN", result.stdout)

    def test_one_paid_request_and_summary(self):
        payload = json.loads(Path("tests/fixtures/dataforseo.json").read_text(encoding="utf-8-sig"))
        payload["cost"] = 0.004
        results = payload["tasks"][0]["result"][0]
        results["pages_count"] = 1
        organic = next(item for item in results["items"] if item.get("type") == "organic")
        organic["checks"] = ["from_web"]
        organic["related_result"] = [{"url": "https://example.org/subpage"}]
        calls = []
        def transport(url, data, headers, timeout):
            calls.append((url, data, timeout))
            return payload
        report = run_one("fake", "fake", transport=transport)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][1][0]["resolve_poisoned_results"])
        self.assertNotIn("group_organic_results", calls[0][1][0])
        self.assertEqual(report["pages_count"], 1)
        self.assertEqual(report["counts"]["organic"], 3)
        self.assertEqual(report["organic"][0]["checks"], ["from_web"])
        self.assertEqual(report["organic"][0]["related_count"], 1)
        self.assertEqual(report["cost"], 0.004)

    def test_ungroup_is_explicit(self):
        self.assertFalse(diagnostic_task(ungroup=True)["group_organic_results"])
        self.assertNotIn("group_organic_results", diagnostic_task())
        self.assertEqual(diagnostic_task(keyword="interac casino")["keyword"], "interac casino")

    def test_malformed_response_is_not_retried(self):
        calls = []
        def transport(*args, **kwargs):
            calls.append(1)
            return {"status_code": 20000, "tasks": []}
        with self.assertRaises(ValueError):
            run_one("fake", "fake", transport=transport)
        self.assertEqual(len(calls), 1)

    def test_missing_credentials_do_not_request(self):
        def transport(*args, **kwargs):
            self.fail("Network must not be used")
        with self.assertRaises(ValueError):
            run_one("", "", transport=transport)

    def test_provider_failure_keeps_cost_and_task_id_without_results(self):
        report = summarize({"status_code": 20000, "cost": 0.002, "tasks": [{
            "status_code": 40501, "id": "task-id", "result": None}]})
        self.assertEqual(report["task_id"], "task-id")
        self.assertEqual(report["task_status_code"], 40501)
        self.assertEqual(report["cost"], 0.002)
        self.assertEqual(report["organic"], [])


if __name__ == "__main__":
    unittest.main()
