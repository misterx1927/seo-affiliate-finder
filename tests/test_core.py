import sqlite3
import unittest
from src.database import connect, replace_keyword_results
from src.keywords import KEYWORDS
from src.urls import normalize_url

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.results = [{"position": 1, "url": "https://EXAMPLE.com/a?utm_source=x&x=1#section"}]

    def test_keywords(self):
        self.assertEqual(len(set(KEYWORDS)), 10)

    def test_url_normalization(self):
        self.assertEqual(normalize_url(self.results[0]["url"]), "https://example.com/a?x=1")
        with self.assertRaises(ValueError): normalize_url("file:///private")

    def test_rerun_updates_without_duplicates_and_keeps_history(self):
        replace_keyword_results(self.db, "2026-11-24", "q", self.results)
        replace_keyword_results(self.db, "2026-11-24", "q", [{"position": 2, "url": "https://new.example"}])
        replace_keyword_results(self.db, "2026-11-25", "q", self.results)
        rows = self.db.execute("SELECT day, position FROM observations ORDER BY day").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("2026-11-24", 2), ("2026-11-25", 1)])

    def test_invalid_replacement_preserves_existing_results(self):
        replace_keyword_results(self.db, "2026-11-24", "q", self.results)
        with self.assertRaises(ValueError):
            replace_keyword_results(self.db, "2026-11-24", "q", [{"position": 11, "url": "https://bad.example"}])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)

if __name__ == "__main__": unittest.main()
