import copy
import json
import unittest
from pathlib import Path
from src.serp import SerpError, build_task, parse_response

class SerpTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(Path("tests/fixtures/dataforseo.json").read_text(encoding="utf-8-sig"))

    def test_search_settings(self):
        task = build_task("online casino canada")
        self.assertEqual((task["location_name"], task["language_code"], task["device"], task["se_domain"]),
                         ("Canada", "en", "mobile", "google.ca"))
        self.assertEqual(build_task("online casino canada", 40)["depth"], 40)
        with self.assertRaises(ValueError): build_task("online casino canada", 200)

    def test_filters_ads_orders_organic_and_normalizes(self):
        results = parse_response(self.payload)
        self.assertEqual([r.position for r in results], [1, 2, 3])
        self.assertEqual(results[0].url, "https://reviews.example/canada")

    def test_rejects_api_and_task_errors(self):
        for level in ("root", "task"):
            payload = copy.deepcopy(self.payload)
            (payload if level == "root" else payload["tasks"][0])["status_code"] = 40000
            with self.subTest(level=level), self.assertRaises(SerpError): parse_response(payload)

    def test_rejects_missing_or_invalid_data(self):
        for payload in ({}, {"status_code": 20000, "tasks": []},
                        {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [{"items": []}]}]}):
            with self.subTest(payload=payload), self.assertRaises(SerpError): parse_response(payload)

    def test_rejects_duplicate_ranks(self):
        items = self.payload["tasks"][0]["result"][0]["items"]
        items.append(copy.deepcopy(items[1]))
        with self.assertRaises(SerpError): parse_response(self.payload)

if __name__ == "__main__": unittest.main()
