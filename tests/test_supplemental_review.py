"""Sanity checks for the independently reviewed, source-linked snapshot."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


class SupplementalReviewTests(unittest.TestCase):
    def test_review_entries_have_valid_urls_and_metadata(self):
        path = Path(__file__).resolve().parents[1] / 'results' / 'independent-review-2026-11-26.json'

        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                self.assertNotIn(key, result, f'duplicate JSON key: {key}')
                result[key] = value
            return result

        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_pairs)
        self.assertGreaterEqual(len(data), 18)
        for url, entry in data.items():
            with self.subTest(url=url):
                source = urlsplit(url)
                self.assertEqual(source.scheme, 'https')
                self.assertTrue(source.hostname)
                self.assertIn(entry['relevance'], {'yes', 'no', 'needs_review'})
                self.assertIsInstance(entry['brands'], list)
                self.assertTrue(all(isinstance(name, str) and name.strip() for name in entry['brands']))
                self.assertIn('26.11.2026', entry['note'])
                if contact := entry.get('contact_page'):
                    contact_url = urlsplit(contact)
                    self.assertEqual(contact_url.scheme, 'https')
                    self.assertEqual(source.hostname, contact_url.hostname)


if __name__ == '__main__':
    unittest.main()
