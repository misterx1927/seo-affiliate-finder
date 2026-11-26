import unittest
from pathlib import Path
from src.snapshot import load_snapshot


class SnapshotTests(unittest.TestCase):
    def test_bundled_snapshot_loads_without_database(self):
        rows = load_snapshot(Path(__file__).resolve().parents[1] / 'results' / 'run-7-reviewed.csv')
        self.assertEqual(len(rows), 100)
        self.assertEqual(len({row['Keyword'] for row in rows}), 10)
        self.assertEqual(len({row['URL'] for row in rows}), 69)
        self.assertEqual(sum(row['SnapshotSerpSource'] == 'restored_from_google_web' for row in rows), 87)
        self.assertEqual(sum(row['Status'] == 'complete' for row in {r['URL']: r for r in rows}.values()), 35)

