import hashlib
import json
import unittest
from urllib.parse import urlsplit

from batch_onpage import CANDIDATES, ENDPOINT, eligible_urls, extract, prepare_attempts, run_batch
from src.database import connect
from src.parser import extract_text


def payload(url, *, page_status=200, text=None):
    if text is None:
        text = "# Casino ratings & reviews\n" + "Relevant comparison <text> & information. " * 1200
    return {"status_code": 20000, "cost": 0.00015, "tasks": [{
        "id": "task-id", "status_code": 20000, "data": {"url": url}, "result": [{
            "items": [{"type": "content_parsing_element", "status_code": page_status,
                       "page_as_markdown": text, "fetch_time": "2026-11-26 00:00:00 +00:00"}]}]}]}


class BatchOnpageTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.db.execute("INSERT INTO runs(id,started_at,mode,status) VALUES(7, '2026-11-25', 'live', 'partial')")
        self.db.executemany("INSERT INTO run_pages(run_id,url,status,error) VALUES(7, ?, 'needs_review', 'Page connection failed')",
                            [(url,) for url in CANDIDATES])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_eligible_only_connection_errors_uncached_and_unattempted(self):
        self.db.execute("UPDATE run_pages SET error='Page returned HTTP 403' WHERE url=?", (CANDIDATES[0],))
        self.db.execute("UPDATE run_pages SET error='Page returned HTTP 451' WHERE url=?", (CANDIDATES[1],))
        self.db.execute("INSERT INTO page_cache(url,day,content,charset) VALUES(?, '2026-11-25', x'01', 'utf-8')", (CANDIDATES[2],))
        prepare_attempts(self.db)
        self.db.execute("INSERT INTO onpage_batch_attempts(url,started_at,status) VALUES(?, 'now', 'started')", (CANDIDATES[3],))
        blocked = {urlsplit(CANDIDATES[i]).hostname for i in (0, 1)}
        self.assertEqual(eligible_urls(self.db), [url for url in CANDIDATES[4:] if urlsplit(url).hostname not in blocked])

    def test_one_attempt_per_url_and_atomic_provenance(self):
        calls = []
        def transport(endpoint, tasks, headers, timeout):
            calls.append((endpoint, tasks))
            return payload(tasks[0]["url"])
        first = run_batch(self.db, "fake", "fake", list(CANDIDATES[:2]), transport, progress=lambda x: None)
        second = run_batch(self.db, "fake", "fake", list(CANDIDATES[:2]), transport, progress=lambda x: None)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(x[0] == ENDPOINT for x in calls))
        self.assertEqual([x[1] for x in first], ["text_returned_unverified"] * 2)
        self.assertEqual([x[1] for x in second], ["skipped"] * 2)
        row = self.db.execute("SELECT content, content_sha256, details_json FROM page_cache JOIN page_cache_provenance USING(url) WHERE url=?", (CANDIDATES[0],)).fetchone()
        self.assertEqual(hashlib.sha256(row[0]).hexdigest(), row[1])
        details = json.loads(row[2])
        self.assertTrue(details["text_truncated"])
        self.assertEqual(details["reported_cost_usd"], 0.00015)
        self.assertIn("<text> & information", extract_text(row[0]))
        self.assertNotIn(b"<text>", row[0])

    def test_http_block_and_challenge_are_not_imported(self):
        for response in (payload(CANDIDATES[0], page_status=403),
                         payload(CANDIDATES[0], text="Verify you are human " * 10),
                         payload(CANDIDATES[0], text="Hmm... Are You a Robot? Let's Check. " * 5),
                         payload(CANDIDATES[0], text="LeoVegas ist in deinem Gebiet unter leovegas.de tätig. " * 5)):
            with self.subTest(response=response), self.assertRaises(ValueError):
                extract(response, CANDIDATES[0])

    def test_refuse_unexpected_url_and_more_than_eight(self):
        with self.assertRaises(ValueError):
            run_batch(self.db, "fake", "fake", ["https://example.com"], transport=lambda *a, **k: self.fail())
        with self.assertRaises(ValueError):
            run_batch(self.db, "fake", "fake", list(CANDIDATES) + [CANDIDATES[0]], transport=lambda *a, **k: self.fail())

    def test_ambiguous_failure_is_not_retried_and_stops_batch(self):
        calls = []
        def failure(*args, **kwargs):
            calls.append(1)
            raise TimeoutError()
        self.assertEqual(run_batch(self.db, "fake", "fake", list(CANDIDATES[:2]), failure, progress=lambda x: None), [(CANDIDATES[0], "needs_review")])
        self.assertEqual(run_batch(self.db, "fake", "fake", [CANDIDATES[0]], failure, progress=lambda x: None), [(CANDIDATES[0], "skipped")])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM page_cache").fetchone()[0], 0)

    def test_cache_and_provenance_insert_are_rolled_back_together(self):
        self.db.execute("INSERT INTO page_cache_provenance(url,source,retrieved_at) VALUES(?, 'old', 'old')", (CANDIDATES[0],))
        self.db.commit()
        result = run_batch(self.db, "fake", "fake", [CANDIDATES[0]], lambda *a, **k: payload(CANDIDATES[0]), progress=lambda x: None)
        self.assertEqual(result[0][1], "needs_review")
        self.assertEqual(self.db.execute("SELECT count(*) FROM page_cache").fetchone()[0], 0)

    def test_task_level_provider_error_stops_batch(self):
        calls = []
        def failure(*args, **kwargs):
            calls.append(1)
            return {"status_code": 20000, "cost": 0.00015, "tasks": [{"status_code": 40501}]}
        result = run_batch(self.db, "fake", "fake", list(CANDIDATES[:2]), failure, progress=lambda x: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result[0][1], "needs_review")
        self.assertEqual(self.db.execute("SELECT reported_cost_usd FROM onpage_batch_attempts").fetchone()[0], 0.00015)


if __name__ == "__main__":
    unittest.main()
