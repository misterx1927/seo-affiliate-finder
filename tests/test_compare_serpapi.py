import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from compare_serpapi import compare, main, serpapi_request


class SerpApiComparisonTests(unittest.TestCase):
    def test_requests_canadian_mobile_results_without_cache(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()

        class Opener:
            def open(self, request, timeout):
                query = parse_qs(urlsplit(request.full_url).query)
                self_case.assertEqual(query['location'], ['Canada'])
                self_case.assertEqual(query['gl'], ['ca'])
                self_case.assertEqual(query['hl'], ['en'])
                self_case.assertEqual(query['device'], ['mobile'])
                self_case.assertEqual(query['no_cache'], ['true'])
                return Response(json.dumps({'search_metadata': {'status': 'Success'},
                    'organic_results': [{'position': i, 'link': f'https://example.com/{i}'}
                                        for i in range(1, 11)]}).encode())

        self_case = self
        with patch('compare_serpapi.urllib.request.build_opener', return_value=Opener()):
            self.assertEqual(len(serpapi_request('interac casino', 'test-key')), 10)

    def test_compares_exact_urls_and_ranks(self):
        first = [{'rank': 1, 'url': 'https://a.example/'}, {'rank': 2, 'url': 'https://b.example/'}]
        second = [{'rank': 1, 'url': 'https://a.example/'}, {'rank': 3, 'url': 'https://b.example/'}]
        self.assertEqual(compare(first, second), {'exact_url_overlap': 2, 'exact_rank_matches': 1})

    def test_invalid_provider_response_does_not_report_success(self):
        class Opener:
            def open(self, request, timeout):
                class Response(io.BytesIO):
                    def __enter__(self): return self
                    def __exit__(self, *args): self.close()
                return Response(b'[]')
        with patch('compare_serpapi.urllib.request.build_opener', return_value=Opener()):
            with self.assertRaisesRegex(RuntimeError, 'no DataForSEO request'):
                serpapi_request('interac casino', 'test-key')

    def test_incomplete_response_is_saved_without_querying_dataforseo(self):
        rows = [{'rank': 1, 'url': 'https://example.com/'}]
        with patch.dict(os.environ, {'SERPAPI_API_KEY': 'secret', 'DATAFORSEO_LOGIN': 'x',
                                    'DATAFORSEO_PASSWORD': 'y'}), \
             patch('sys.argv', ['compare_serpapi.py', '--keyword', 'interac casino', '--allow-paid']), \
             patch('compare_serpapi.load_env'), \
             patch('compare_serpapi.serpapi_request', return_value=rows), \
             patch('compare_serpapi.save_report', return_value=Path('report.json')) as save, \
             patch('compare_serpapi.run_one') as dataforseo:
            with self.assertRaisesRegex(RuntimeError, 'no DataForSEO request'):
                main()
            dataforseo.assert_not_called()
            report = save.call_args.args[0]
            self.assertEqual(report['serpapi'], rows)
            self.assertIsNone(report['dataforseo'])
            self.assertNotIn('secret', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
