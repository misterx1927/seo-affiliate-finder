import unittest
from src.database import connect
from src.cached_pilot import run_cached_pilot, select_cached
from src.analyzer import validate_analysis

class Analyzer:
    model='mock'
    def __init__(self): self.calls = 0
    def analyze(self,text):
        self.calls += 1
        return validate_analysis({'relevance':'yes','brands':['Maple Casino'],'contact':None,'evidence':'Independent reviews'},text), {'prompt_tokens':100,'completion_tokens':20}

class CachedPilotTests(unittest.TestCase):
    def setUp(self):
        self.conn=connect(':memory:')
        self.addCleanup(self.conn.close)
        with self.conn:
            self.conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES(1,'now','live','partial')")
            for i in range(1,4):
                url=f'https://site{i}.example/'
                self.conn.execute('INSERT INTO partial_observations VALUES(?,?,?,?,?,?)',(1,'2026-11-25','q',i,url,f'site{i}.example'))
                html=b'<h1>Independent reviews</h1><p>Maple Casino. '+b'Useful review content. '*10+b'</p>'
                self.conn.execute('INSERT INTO page_cache VALUES(?,?,?,?)',(url,'2026-11-25',html,'utf-8'))
                self.conn.execute("INSERT INTO pages(url,status) VALUES(?,'pending')",(url,))
    def test_pilot_processes_max_two_and_records_usage(self):
        analyzer=Analyzer()
        result=run_cached_pilot(self.conn,1,2,lambda run: analyzer,'data/test-cached.lock')
        self.assertEqual((result['status'],result['completed'],analyzer.calls),('complete',2,2))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM pages WHERE status='complete'").fetchone()[0],2)
        self.assertEqual(self.conn.execute('SELECT sum(input_tokens) FROM api_usage').fetchone()[0],200)
    def test_failed_validation_still_records_available_usage(self):
        class FailedValidation:
            model = 'mock'
            def analyze(self, text):
                error = ValueError('unverified response')
                error.usage = {'prompt_tokens': 111, 'completion_tokens': 22}
                raise error
        result = run_cached_pilot(self.conn,1,1,lambda run: FailedValidation(),'data/test-cached.lock')
        row = self.conn.execute('SELECT input_tokens,output_tokens FROM api_usage WHERE run_id=?', (result['run_id'],)).fetchone()
        self.assertEqual(tuple(row),(111,22))
        self.assertEqual(result['status'],'partial')

    def test_model_error_does_not_erase_other_pages(self):
        class Broken:
            def analyze(self,text): raise ValueError('bad response')
        result=run_cached_pilot(self.conn,1,1,lambda run: Broken(),'data/test-cached.lock')
        self.assertEqual(result['status'],'partial')
        self.assertEqual(self.conn.execute("SELECT count(*) FROM pages WHERE status='needs_review'").fetchone()[0],1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM pages WHERE status='pending'").fetchone()[0],2)

    def test_recovery_can_select_completed_search_rows_without_duplicates(self):
        with self.conn:
            self.conn.execute("INSERT INTO observations(day,keyword,position,url,domain,run_id) VALUES('2026-11-25','q2',1,'https://site1.example/','site1.example',1)")
        rows = select_cached(self.conn, 1, 8, max_allowed=8)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['url'] for r in rows}), 3)
        with self.assertRaises(ValueError): select_cached(self.conn, 1, 9, max_allowed=9)

    def test_recovery_can_use_later_provider_content_with_provenance(self):
        with self.conn:
            self.conn.execute("UPDATE page_cache SET day='2026-11-26' WHERE url='https://site1.example/'")
        self.assertNotIn('https://site1.example/', [r['url'] for r in select_cached(self.conn, 1, 8, max_allowed=8)])
        with self.conn:
            self.conn.execute("INSERT INTO page_cache_provenance(url,source,retrieved_at) VALUES('https://site1.example/','test','2026-11-26')")
        self.assertIn('https://site1.example/', [r['url'] for r in select_cached(self.conn, 1, 8, max_allowed=8)])

    def test_failed_recovery_attempt_is_not_automatically_selected_again(self):
        with self.conn:
            self.conn.execute("INSERT INTO runs(id,started_at,mode,status) VALUES(2,'now','analysis_pilot','partial')")
            self.conn.execute("INSERT INTO run_pages(run_id,url,status) VALUES(2,'https://site1.example/','needs_review')")
        self.assertNotIn('https://site1.example/', [r['url'] for r in select_cached(self.conn, 1, 8, max_allowed=8)])

if __name__ == '__main__': unittest.main()
