import os
import json
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.database import connect, replace_keyword_results


class UIHistoryTests(unittest.TestCase):
    def test_tracked_run_never_uses_a_later_page_analysis(self):
        root = Path(__file__).resolve().parents[1]
        (root / 'data').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / 'data') as temporary:
            folder = Path(temporary)
            (folder / 'results').mkdir()
            (folder / 'results' / 'public-domain-contacts.json').write_text(json.dumps({
                'second.example': {'email': 'public@second.example', 'source': 'https://second.example/contact', 'contact_page': 'https://second.example/contact'}
            }), encoding='utf-8')
            db = connect(folder / 'data' / 'live.db')
            with db:
                db.execute("INSERT INTO runs(id,started_at,mode,status) VALUES (1,'now','live','complete')")
                db.execute('INSERT INTO run_analysis_tracking(run_id) VALUES (1)')
                replace_keyword_results(db, '2026-11-27', 'example query', [
                    {'position': 1, 'url': 'https://first.example/'},
                    {'position': 2, 'url': 'https://second.example/'},
                ], 1)
                db.execute("INSERT INTO pages(url,status,relevance,contact) VALUES ('https://first.example/','complete','no','current@first.example')")
                db.execute("INSERT INTO pages(url,status,relevance,contact) VALUES ('https://second.example/','complete','yes','current@second.example')")
                db.execute("INSERT INTO run_page_analysis(run_id,url,status,relevance,contact) VALUES (1,'https://first.example/','complete','yes','old@first.example')")
            db.close()
            previous = Path.cwd()
            try:
                os.chdir(folder)
                app = AppTest.from_file(str(root / 'app.py')).run(timeout=30)
                self.assertFalse(app.exception, [item.value for item in app.exception])
                table = app.dataframe[0].value
                self.assertEqual(table['Возможный контакт'].tolist(), ['old@first.example'])
                self.assertEqual(table['Оценка'].tolist(), ['Возможно подходит'])
                next(item for item in app.multiselect if item.label == 'Показать').set_value(['Нет анализа']).run(timeout=30)
                self.assertFalse(app.exception, [item.value for item in app.exception])
                table = app.dataframe[0].value
                self.assertEqual(table['Ссылка на страницу'].tolist(), ['https://second.example/'])
                self.assertEqual(table['Оценка'].tolist(), ['Нет анализа'])
                self.assertNotIn('current@second.example', table['Возможный контакт'].tolist())
                self.assertEqual(table['Возможный контакт'].tolist(), ['public@second.example'])
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
