import json
import unittest
from pathlib import Path
from src.providers import DataForSEO, OpenAIAnalyzer, ProviderError, RequestAllowance

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.payload = json.loads(Path("tests/fixtures/dataforseo.json").read_text(encoding="utf-8-sig"))
    def transport(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.payload
    def test_requires_approval_before_any_call(self):
        client = DataForSEO("login", "secret", RequestAllowance(1, 1), self.transport)
        with self.assertRaises(ProviderError): client.search("keyword")
        self.assertEqual(self.calls, [])
    def test_poisoned_results_verification_is_opt_in_and_tracks_restored_ranks(self):
        self.payload['tasks'][0]['result'][0]['items'][1]['checks'] = ['from_web']
        client = DataForSEO('login', 'secret', RequestAllowance(1, 0, approved=True), self.transport, verify_serp=True)
        client.search('keyword')
        self.assertTrue(self.calls[0][1][0]['resolve_poisoned_results'])
        self.assertEqual(len(client.last_diagnostics['from_web_ranks']), 1)
    def test_limit_and_search_settings(self):
        allowance = RequestAllowance(1, 1, approved=True)
        client = DataForSEO("login", "secret", allowance, self.transport)
        self.assertEqual(len(client.search("keyword")), 3)
        self.assertEqual(client.last_diagnostics["items_by_type"]["organic"], 3)
        self.assertEqual(client.last_diagnostics["organic_ranks"], [2, 1, 3])
        self.assertEqual(self.calls[0][1][0]["device"], "mobile")
        with self.assertRaises(ProviderError): client.search("keyword")
        self.assertEqual(len(self.calls), 1)
    def test_model_response_checked_and_limited(self):
        response = {"choices": [{"message": {"content": json.dumps({"relevance":"yes", "brands": ["Maple Casino"], "contact": None, "evidence":"Independent reviews"})}}], "usage":{"prompt_tokens":100}}
        def fake(*args): self.calls.append(args); return response
        client = OpenAIAnalyzer("key", "model", RequestAllowance(0, 1, approved=True), fake)
        result, usage = client.analyze("Independent reviews of Maple Casino.")
        self.assertEqual(result.brands, ("Maple Casino",))
        self.assertEqual(usage["prompt_tokens"], 100)
        with self.assertRaises(ProviderError): client.analyze("Independent reviews of Maple Casino.")
        self.assertEqual(len(self.calls), 1)
    def test_luna_prompt_is_byte_limited_and_reasoning_disabled(self):
        response = {"choices": [{"message": {"content": json.dumps({"relevance":"needs_review", "brands": [], "contact": None, "evidence":"A"})}}]}
        def fake(*args): self.calls.append(args); return response
        client = OpenAIAnalyzer("key", "gpt-6-luna", RequestAllowance(0, 1, approved=True), fake)
        client.analyze("A" + "é" * 30000 + " footer@example.com")
        body = self.calls[0][1]
        text = body["messages"][1]["content"].split("\n", 1)[1]
        self.assertLessEqual(len(text.encode("utf-8")), 40000)
        self.assertIn("footer@example.com", text)
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertNotIn("temperature", body)

    def test_page_text_below_new_limit_is_not_truncated(self):
        response = {"choices": [{"message": {"content": json.dumps({"relevance":"needs_review", "brands": [], "contact": None, "evidence":"A"})}}]}
        def fake(*args): self.calls.append(args); return response
        client = OpenAIAnalyzer('key', 'gpt-6-luna', RequestAllowance(0, 1, approved=True), fake)
        client.analyze('A' * 17_000 + ' Wettson Casino ' + 'A' * 10_000)
        text = self.calls[0][1]['messages'][1]['content']
        self.assertIn('Wettson Casino', text)
        self.assertNotIn('[...]', text)

    def test_prompt_distinguishes_casino_brand_from_regulator_and_payment_provider(self):
        response = {"choices": [{"message": {"content": json.dumps({"relevance": "yes", "brands": ["PlayNow"], "contact": None, "evidence": "PlayNow (BCLC)"})}}]}
        def fake(*args): self.calls.append(args); return response
        client = OpenAIAnalyzer('key', 'model', RequestAllowance(0, 1, approved=True), fake)
        result, _ = client.analyze('PlayNow (BCLC) is a provincial online casino; AGCO is a regulator, PayDirect a payment provider.')
        instruction = self.calls[0][1]['messages'][0]['content']
        self.assertIn('payment providers', instruction)
        self.assertIn('regulators', instruction)
        self.assertIn('context', instruction)
        self.assertIn('PlayNow', result.brands)
        self.assertTrue(client.cache_version.startswith('openai-page-analysis-v9:'))

    def test_prompt_prevents_confusing_reviewed_casino_support_with_publisher_contact(self):
        response = {"choices": [{"message": {"content": json.dumps({"relevance": "yes", "brands": [], "contact": None, "evidence": "Independent reviews"})}}]}
        def fake(*args): self.calls.append(args); return response
        client = OpenAIAnalyzer('key', 'model', RequestAllowance(0, 1, approved=True), fake)
        client.analyze('Independent reviews. Mirax provides customer support at support@miraxcasino.com.')
        instruction = self.calls[0][1]['messages'][0]['content']
        self.assertIn('publisher', instruction)
        self.assertIn('third-party casino', instruction)
        self.assertIn('partnership contact', instruction)

    def test_invalid_response_preserves_usage_without_exposing_content(self):
        def fake(*args):
            return {"choices":[{"message":{"content":"not json"}}],"usage":{"prompt_tokens":11,"completion_tokens":3}}
        client = OpenAIAnalyzer("key", "model", RequestAllowance(0,1,approved=True),fake)
        with self.assertRaises(ProviderError) as caught:
            client.analyze("A page with some text.")
        self.assertEqual(caught.exception.usage["prompt_tokens"],11)
        self.assertNotIn("not json", str(caught.exception))

    def test_failed_call_is_not_retried(self):
        def fail(*args): self.calls.append(args); raise ProviderError("failed")
        client = DataForSEO("login", "secret", RequestAllowance(2, 0, approved=True), fail)
        with self.assertRaises(ProviderError): client.search("keyword")
        self.assertEqual(len(self.calls), 1)

    def test_invalid_serp_preserves_only_reported_cost(self):
        self.payload['cost'] = 0.004
        self.payload['tasks'][0]['result'][0]['items'] = None
        client = DataForSEO('login', 'secret', RequestAllowance(1, 0, approved=True), self.transport)
        with self.assertRaises(ValueError) as caught:
            client.search('keyword')
        self.assertEqual(caught.exception.serp_response_cost, 0.004)
        self.assertNotIn('secret', str(caught.exception))

if __name__ == "__main__": unittest.main()
