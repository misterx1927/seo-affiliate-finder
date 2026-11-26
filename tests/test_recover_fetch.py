import unittest

from recover_fetch import select_retry_targets
from src.database import connect


class RecoverySelectionTests(unittest.TestCase):
    def test_access_denials_and_cached_pages_are_not_retried(self):
        conn = connect(':memory:')
        self.addCleanup(conn.close)
        with conn:
            conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES(1,'now','live','partial')")
            for n, error in enumerate(('Page connection failed', 'Page returned HTTP 403', 'Page exceeds size limit', 'Page connection failed'), 1):
                url = f'https://site{n}.example/'
                conn.execute("INSERT INTO observations(day,keyword,position,url,domain,run_id) VALUES('2026-11-25','q',?,?,?,1)", (n, url, f'site{n}.example'))
                conn.execute("INSERT INTO run_pages(run_id,url,status,error) VALUES(1,?,'needs_review',?)", (url, error))
            conn.execute("INSERT INTO page_cache(url,day,content,charset) VALUES('https://site4.example/','2026-11-25',x'00','utf-8')")
        self.assertEqual([r['url'] for r in select_retry_targets(conn, 1)], ['https://site1.example/', 'https://site3.example/'])


if __name__ == '__main__':
    unittest.main()
