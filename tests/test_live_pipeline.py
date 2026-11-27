import unittest
from pathlib import Path
from src.analyzer import validate_analysis
from src.database import connect
from src.live_pipeline import run_live
from src.serp import OrganicResult
from src.run_lock import RunLock, RunLocked

class FakeSerp:
    def search(self, keyword):
        if keyword == "bad": raise ValueError("simulated unavailable API")
        return [OrganicResult(i, f"https://example{i}.com/") for i in range(1,11)]
class FakeAI:
    def __init__(self): self.calls = 0
    def analyze(self, text):
        self.calls += 1
        return validate_analysis({"relevance":"yes", "brands":["Maple Casino"], "contact":None, "evidence":"Independent reviews"}, text), {}
def fake_fetch(url):
    return (b"<h1>Independent reviews</h1><p>Maple Casino is reviewed by our editors. " + b"Detailed content for our readers. " * 4 + b"</p>", "utf-8")

class LivePipelineTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.path = Path("data/test-live.lock")
    def test_partial_failure_and_cached_page(self):
        ai = FakeAI()
        result = run_live(self.db, "2026-11-24", ["ok", "bad"], FakeSerp(), ai, fake_fetch, self.path, 1)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["keywords_complete"], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM observations").fetchone()[0], 10)
        self.assertEqual(ai.calls, 1)
        run_live(self.db, "2026-11-24", ["ok"], FakeSerp(), ai, fake_fetch, self.path, 1)
        self.assertEqual(ai.calls, 1)

    def test_changed_analysis_version_invalidates_cache(self):
        ai = FakeAI()
        ai.cache_version = 'model-prompt-v1'
        run_live(self.db, '2026-11-24', ['ok'], FakeSerp(), ai, fake_fetch, self.path, 1)
        run_live(self.db, '2026-11-24', ['ok'], FakeSerp(), ai, fake_fetch, self.path, 1)
        self.assertEqual(ai.calls, 1)
        ai.cache_version = 'model-prompt-v2'
        run_live(self.db, '2026-11-24', ['ok'], FakeSerp(), ai, fake_fetch, self.path, 1)
        self.assertEqual(ai.calls, 2)

    def test_each_run_preserves_its_analysis_even_if_a_later_fetch_fails(self):
        ai = FakeAI()
        first = run_live(self.db, '2026-11-24', ['ok'], FakeSerp(), ai, fake_fetch, self.path, 1)
        cached = run_live(self.db, '2026-11-24', ['ok'], FakeSerp(), ai, fake_fetch, self.path, 1)
        def failed_fetch(url):
            raise OSError('site unavailable')
        later = run_live(self.db, '2026-11-25', ['ok'], FakeSerp(), ai, failed_fetch, self.path, 1)
        records = self.db.execute('SELECT run_id,status,relevance,error FROM run_page_analysis WHERE url=? ORDER BY run_id', ('https://example1.com/',)).fetchall()
        self.assertEqual([tuple(row[:3]) for row in records], [
            (first['run_id'], 'complete', 'yes'),
            (cached['run_id'], 'complete', 'yes'),
            (later['run_id'], 'needs_review', None),
        ])
        self.assertIn('site unavailable', records[-1]['error'])
        self.assertEqual(ai.calls, 1)

    def test_search_diagnostics_are_saved_with_keyword(self):
        class DiagnosticSerp(FakeSerp):
            last_diagnostics = {"items_by_type": {"organic": 10, "people_also_ask": 1}, "organic_ranks": list(range(1, 11)), "from_web_ranks": [1, 3]}
        result = run_live(self.db, "2026-11-24", ["ok"], DiagnosticSerp(), FakeAI(), fake_fetch, self.path, 0)
        row = self.db.execute("SELECT items_by_type,organic_ranks,from_web_ranks FROM serp_diagnostics WHERE run_id=? AND keyword='ok'", (result["run_id"],)).fetchone()
        self.assertIn('"people_also_ask": 1', row[0])
        self.assertIn('10', row[1])
        self.assertEqual(row[2], '[1, 3]')
    def test_incomplete_results_do_not_replace_prior(self):
        class Short(FakeSerp):
            def search(self, keyword): return super().search(keyword)[:3]
        run_live(self.db, "2026-11-24", ["ok"], FakeSerp(), FakeAI(), fake_fetch, self.path, 0)
        result = run_live(self.db, "2026-11-24", ["ok"], Short(), FakeAI(), fake_fetch, self.path, 0)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(self.db.execute("SELECT count(*) FROM observations").fetchone()[0], 10)
        self.assertEqual(self.db.execute("SELECT count(*) FROM partial_observations").fetchone()[0], 3)

    def test_daily_history_and_same_day_replacement(self):
        class ChangedSerp(FakeSerp):
            def search(self, keyword):
                return [OrganicResult(i, f"https://new{i}.example/") for i in range(1, 11)]

        run_live(self.db, "2026-11-24", ["ok"], FakeSerp(), FakeAI(), fake_fetch, self.path, 0)
        earlier = run_live(self.db, "2026-11-25", ["ok"], FakeSerp(), FakeAI(), fake_fetch, self.path, 0)
        later = run_live(self.db, "2026-11-25", ["ok"], ChangedSerp(), FakeAI(), fake_fetch, self.path, 0)
        rows = self.db.execute("SELECT day, position, url FROM observations ORDER BY day, position").fetchall()
        self.assertEqual(len(rows), 20)
        self.assertEqual([r[1] for r in rows[:10]], list(range(1, 11)))
        self.assertEqual([r[1] for r in rows[10:]], list(range(1, 11)))
        self.assertEqual(rows[0][2], "https://example1.com/")
        self.assertEqual(rows[10][2], "https://new1.example/")
        self.assertEqual(self.db.execute('SELECT url FROM run_observations WHERE run_id=? AND position=1', (earlier['run_id'],)).fetchone()[0], 'https://example1.com/')
        self.assertEqual(self.db.execute('SELECT url FROM run_observations WHERE run_id=? AND position=1', (later['run_id'],)).fetchone()[0], 'https://new1.example/')
    def test_partial_search_is_saved_and_resumed_without_repeating_request(self):
        class Short(FakeSerp):
            def __init__(self): self.calls = 0; self.last_cost = 0.002
            def search(self, keyword): self.calls += 1; return super().search(keyword)[:8]
        serp, ai = Short(), FakeAI()
        first = run_live(self.db, "2026-11-24", ["ok"], serp, ai, fake_fetch, self.path, 1)
        self.assertEqual(first["status"], "partial")
        self.assertEqual(self.db.execute("SELECT count(*) FROM partial_observations").fetchone()[0], 8)
        self.assertEqual(self.db.execute("SELECT sum(cost_usd) FROM api_usage WHERE service='serp'").fetchone()[0], 0.002)
        self.assertEqual(ai.calls, 1)
        again = run_live(self.db, "2026-11-24", ["ok"], serp, ai, fake_fetch, self.path, 1, resume_id=first["run_id"])
        self.assertEqual((serp.calls, ai.calls, again["status"]), (1, 1, "partial"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM partial_observations").fetchone()[0], 8)

    def test_resume_does_not_repeat_paid_search_or_failed_analysis(self):
        class CountingSerp(FakeSerp):
            def __init__(self): self.calls = 0
            def search(self, keyword): self.calls += 1; return super().search(keyword)
        class FailedAI:
            def __init__(self): self.calls = 0
            def analyze(self, text): self.calls += 1; raise ValueError("response lost")
        serp, ai = CountingSerp(), FailedAI()
        result = run_live(self.db, "2026-11-24", ["ok"], serp, ai, fake_fetch, self.path, 1)
        resumed = run_live(self.db, "2026-11-24", ["ok"], serp, ai, fake_fetch, self.path, 1, resume_id=result["run_id"])
        self.assertEqual(resumed["status"], "partial")
        self.assertEqual((serp.calls, ai.calls), (1, 1))

    def test_resume_uses_own_search_snapshot_after_later_run(self):
        class CountingSerp(FakeSerp):
            def __init__(self): self.calls = []
            def search(self, keyword):
                self.calls.append(keyword)
                return super().search(keyword)
        class ChangedSerp(FakeSerp):
            def search(self, keyword):
                return [OrganicResult(i, f"https://new{i}.example/") for i in range(1, 11)]

        serp = CountingSerp()
        first = run_live(self.db, '2026-11-24', ['ok', 'bad'], serp, FakeAI(), fake_fetch, self.path, 0)
        run_live(self.db, '2026-11-24', ['ok'], ChangedSerp(), FakeAI(), fake_fetch, self.path, 0)
        resumed = run_live(self.db, '2026-11-24', ['ok', 'bad'], serp, FakeAI(), fake_fetch,
                           self.path, 1, resume_id=first['run_id'])
        self.assertEqual(serp.calls, ['ok', 'bad'])
        self.assertEqual(resumed['keywords_complete'], 1)
        self.assertEqual(self.db.execute('SELECT url FROM run_pages WHERE run_id=?', (first['run_id'],)).fetchone()[0],
                         'https://example1.com/')
        self.assertFalse(any('checkpoint data no longer available' in e for e in resumed['errors']))

    def test_resume_old_run_uses_remaining_legacy_observations(self):
        first = run_live(self.db, '2026-11-24', ['ok', 'bad'], FakeSerp(), FakeAI(), fake_fetch, self.path, 0)
        self.db.execute('DELETE FROM run_observations WHERE run_id=?', (first['run_id'],))
        self.db.commit()
        resumed = run_live(self.db, '2026-11-24', ['ok', 'bad'], FakeSerp(), FakeAI(), fake_fetch,
                           self.path, 0, resume_id=first['run_id'])
        self.assertEqual(resumed['keywords_complete'], 1)
        self.assertFalse(any('checkpoint data no longer available' in e for e in resumed['errors']))

    def test_failed_analysis_records_usage_without_retry(self):
        class FailedAI:
            model = "test-model"
            def analyze(self, text):
                error = ValueError("response could not be verified")
                error.usage = {"prompt_tokens": 111, "completion_tokens": 22}
                raise error
        result = run_live(self.db, "2026-11-24", ["ok"], FakeSerp(), FailedAI(), fake_fetch, self.path, 1)
        usage = self.db.execute("SELECT input_tokens, output_tokens FROM api_usage WHERE run_id=? AND service='llm'", (result["run_id"],)).fetchone()
        self.assertEqual(tuple(usage), (111, 22))
        self.assertEqual(result["status"], "partial")

    def test_unusable_serp_response_still_records_reported_charge(self):
        class InvalidResponse:
            def search(self, keyword):
                error = ValueError('invalid provider result')
                error.serp_response_cost = 0.004
                raise error
        result = run_live(self.db, '2026-11-24', ['ok'], InvalidResponse(), FakeAI(), fake_fetch, self.path, 0)
        row = self.db.execute("SELECT cost_usd FROM api_usage WHERE run_id=? AND service='serp'", (result['run_id'],)).fetchone()
        self.assertEqual(row[0], 0.004)
        self.assertEqual(result['status'], 'partial')

    def test_interrupted_search_is_not_repeated_on_resume(self):
        class InterruptingSerp(FakeSerp):
            def search(self, keyword):
                if keyword == "interrupt": raise KeyboardInterrupt()
                return super().search(keyword)
        with self.assertRaises(KeyboardInterrupt):
            run_live(self.db, "2026-11-24", ["first", "interrupt", "third"], InterruptingSerp(), FakeAI(), fake_fetch, self.path, 0)
        run_id = self.db.execute("SELECT id FROM runs").fetchone()[0]
        self.assertEqual(self.db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()[0], "failed")
        class CountingSerp(FakeSerp):
            def __init__(self): self.calls = []
            def search(self, keyword): self.calls.append(keyword); return super().search(keyword)
        serp = CountingSerp()
        result = run_live(self.db, "2026-11-24", ["first", "interrupt", "third"], serp, FakeAI(), fake_fetch, self.path, 0, resume_id=run_id)
        self.assertEqual(serp.calls, ["third"])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(any("manual review" in error for error in result["errors"]))

    def test_google_goto_links_are_not_classified_as_sites(self):
        class RedirectSerp:
            def search(self, keyword):
                return [OrganicResult(i, f"https://google.ca/goto?url={i}") for i in range(1, 11)]
        ai = FakeAI()
        def forbidden_fetch(url): raise AssertionError("Unresolved Google links must not be fetched")
        result = run_live(self.db, "2026-11-24", ["ok"], RedirectSerp(), ai, forbidden_fetch, self.path, 10)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(self.db.execute("SELECT count(*) FROM observations").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM partial_observations").fetchone()[0], 10)
        self.assertEqual(self.db.execute("SELECT count(*) FROM pages WHERE status='needs_review'").fetchone()[0], 10)
        self.assertEqual(ai.calls, 0)

    def test_parallel_lock(self):
        with RunLock(self.path):
            with self.assertRaises(RunLocked):
                with RunLock(self.path): pass

if __name__ == "__main__": unittest.main()
