import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

import diagnose_onpage
from diagnose_onpage import ENDPOINT, TARGET, eligible, parse_response, reported_cost, run_one, task


def payload():
    return {"status_code": 20000, "cost": 0.00015, "tasks": [{
        "id": "example", "status_code": 20000, "data": {"url": TARGET}, "result": [{"items": [{
            "type": "content_parsing_element", "status_code": 200,
            "page_as_markdown": "A casino review page with published comparisons. " * 4,
            "fetch_time": "2026-11-26 10:00:00 +00:00"}]}]}]}


class OnpageDiagnosticTests(unittest.TestCase):
    def test_dry_run_needs_no_credentials(self):
        env = dict(os.environ)
        env.pop("DATAFORSEO_LOGIN", None)
        env.pop("DATAFORSEO_PASSWORD", None)
        result = subprocess.run([sys.executable, "diagnose_onpage.py"], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn(TARGET, result.stdout)

    def test_one_fixed_request_and_parse(self):
        calls = []
        def transport(url, data, headers, timeout):
            calls.append((url, data, timeout))
            return payload()
        response = run_one("fake", "fake", transport=transport)
        summary, text = parse_response(response)
        self.assertEqual(calls, [(ENDPOINT, [task()], 180)])
        self.assertGreater(len(text), 80)
        self.assertEqual(summary["page_http_status"], 200)
        self.assertEqual(reported_cost(response), 0.00015)
        self.assertNotIn("enable_javascript", calls[0][1][0])

    def test_rejects_other_url_http_block_and_challenge(self):
        for mutation in ("url", "status", "challenge"):
            obj = payload()
            item = obj["tasks"][0]["result"][0]["items"][0]
            if mutation == "url": obj["tasks"][0]["data"]["url"] = "https://other.example/"
            if mutation == "status": item["status_code"] = 403
            if mutation == "challenge": item["page_as_markdown"] = "Verify you are human. " * 10
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                parse_response(obj)

    def test_only_selected_connection_failure_is_eligible(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("create table run_pages(run_id integer, url text, error text)")
        conn.execute("insert into run_pages values(7, ?, 'Page returned HTTP 403')", (TARGET,))
        self.assertFalse(eligible(conn))
        conn.execute("update run_pages set error='Page connection failed'")
        self.assertTrue(eligible(conn))
        conn.close()

    def test_missing_credentials_do_not_use_transport(self):
        with self.assertRaises(ValueError):
            run_one("", "", transport=lambda *a, **kw: self.fail("network"))

    def test_cost_rejects_nonfinite_and_untrusted_values(self):
        for bad in (None, -1, True, "0.1", float("nan"), float("inf")):
            self.assertIsNone(reported_cost({"cost": bad}))

    def test_persistent_marker_prevents_second_request(self):
        real_connect = sqlite3.connect
        writer = mock_open()
        writer.side_effect = [writer.return_value, FileExistsError()]
        with patch.object(diagnose_onpage, "REPORT_DIR", Path("unused")), \
             patch("sys.argv", ["diagnose_onpage.py", "--allow-paid"]), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("pathlib.Path.mkdir"), patch("pathlib.Path.open", writer), \
             patch("pathlib.Path.write_text"), \
             patch("diagnose_onpage.sqlite3.connect", side_effect=lambda *a, **kw: real_connect(":memory:")), \
             patch("diagnose_onpage.eligible", return_value=True), \
             patch("diagnose_onpage.load_env"), \
             patch.dict(os.environ, {"DATAFORSEO_LOGIN": "fake", "DATAFORSEO_PASSWORD": "fake"}), \
             patch("diagnose_onpage.run_one", return_value=payload()) as request:
            diagnose_onpage.main()
            with self.assertRaises(SystemExit):
                diagnose_onpage.main()
            self.assertEqual(request.call_count, 1)
            self.assertEqual(writer.call_count, 2)


if __name__ == "__main__":
    unittest.main()
