import csv
from pathlib import Path
from uuid import uuid4
import unittest

from src.keywords import KEYWORDS
from verify_results import inspect


class VerifyResultsTests(unittest.TestCase):
    def write_snapshot(self, duplicate=False):
        path = Path('data') / f'test-snapshot-{uuid4().hex}.csv'
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['date', 'keyword', 'position', 'url', 'analysis_status', 'relevance', 'serp_provenance'])
            for keyword in KEYWORDS:
                for position in range(1, 11):
                    rank = 1 if duplicate and keyword == KEYWORDS[0] and position == 10 else position
                    writer.writerow(['2026-11-25', keyword, rank, f'https://example.com/{position}', 'complete', 'yes', 'unknown'])
        return path

    def test_complete_snapshot(self):
        summary, errors = inspect(self.write_snapshot())
        self.assertEqual(errors, [])
        self.assertEqual(summary['rows'], 100)
        self.assertEqual(summary['keywords'], 10)
        self.assertEqual(summary['unique_urls'], 10)

    def test_duplicate_position_is_rejected(self):
        _, errors = inspect(self.write_snapshot(duplicate=True))
        self.assertTrue(any('positions 1–10' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
