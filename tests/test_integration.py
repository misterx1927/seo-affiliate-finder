import json
import unittest
from src.database import connect
from src.keywords import KEYWORDS
from src.live_pipeline import run_live
from src.providers import DataForSEO, OpenAIAnalyzer
from src.budget import PersistentAllowance

class FullMockIntegrationTests(unittest.TestCase):
    def test_full_run_with_budget_and_mocked_services(self):
        conn = connect(":memory:")
        self.addCleanup(conn.close)
        calls = {"serp": 0, "llm": 0}
        def mock_transport(url, payload, headers):
            if "dataforseo" in url:
                calls["serp"] += 1
                keyword_index = KEYWORDS.index(payload[0]["keyword"])
                items = [{"type":"organic", "rank_group":i, "url":f"https://site{keyword_index}-{i}.example/"} for i in range(1, 11)]
                return {"status_code":20000, "tasks":[{"status_code":20000,"result":[{"items":items}]}]}
            calls["llm"] += 1
            return {"choices":[{"message":{"content":json.dumps({"relevance":"yes", "brands":["Maple Casino"], "contact":None, "evidence":"Independent reviews"})}}], "usage":{"prompt_tokens":100,"completion_tokens":20}}
        def fake_fetch(url):
            return (b"<h1>Independent reviews</h1><p>Our team reviews Maple Casino and its games for Canadian players. " + b"Full details and more information. " * 4 + b"</p>", "utf-8")
        def factory(run_id):
            allowance = PersistentAllowance(conn, run_id, approved=True, max_serp=10, max_llm=100,
                budget_usd="1.00", serp_reservation_usd="0.002", llm_reservation_usd="0.005")
            return DataForSEO("fake", "fake", allowance, mock_transport), OpenAIAnalyzer("fake", "fake-model", allowance, mock_transport)
        result = run_live(conn, "2026-11-24", KEYWORDS, None, None, fake_fetch, "data/test-integration.lock", 100, provider_factory=factory)
        self.assertEqual(result["status"], "complete", result["errors"])
        self.assertEqual(calls, {"serp":10, "llm":100})
        self.assertEqual(conn.execute("SELECT count(*) FROM observations").fetchone()[0], 100)
        self.assertEqual(conn.execute("SELECT count(*) FROM pages WHERE status='complete'").fetchone()[0], 100)
        self.assertEqual(conn.execute("SELECT sum(estimated_microusd) FROM request_reservations").fetchone()[0], 520000)

if __name__ == "__main__": unittest.main()
