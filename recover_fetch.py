"""Retry selected public-page downloads without contacting paid APIs.

Only retries connection failures and pages that previously exceeded the size limit;
does not retry HTTP access denials. Writes cached text only after a successful parse.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

from src.database import connect
from src.fetcher import fetch_page
from src.parser import extract_text
from src.run_lock import RunLock


def download(url):
    try:
        content, charset = fetch_page(url, timeout=6)
        extract_text(content, charset)
        return content, charset, None
    except Exception as exc:
        return None, None, f'{type(exc).__name__}: {exc}'


def select_retry_targets(conn, run_id):
    return conn.execute("""SELECT DISTINCT rp.url, o.day FROM run_pages rp
        JOIN observations o ON o.url=rp.url AND o.run_id=rp.run_id
        WHERE rp.run_id=? AND rp.status='needs_review'
          AND (rp.error='Page connection failed' OR rp.error='Page exceeds size limit')
          AND NOT EXISTS (SELECT 1 FROM page_cache c WHERE c.url=rp.url AND c.day=o.day)
        ORDER BY rp.url""", (run_id,)).fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-run', type=int, required=True)
    args = parser.parse_args()
    with RunLock('data/live.lock'), connect('data/live.db') as conn:
        rows = select_retry_targets(conn, args.search_run)
        print(f'Retrying up to {len(rows)} public URLs, no Google or paid API calls.', flush=True)
        good = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            pending = {executor.submit(download, row['url']): (row['url'], row['day']) for row in rows}
            for index, future in enumerate(as_completed(pending), 1):
                url, day = pending[future]
                content, charset, error = future.result()
                if error is None:
                    with conn:
                        conn.execute("DELETE FROM page_cache_provenance WHERE url=?", (url,))
                        conn.execute("""INSERT INTO page_cache(url,day,content,charset) VALUES (?, ?, ?, ?)
                            ON CONFLICT(url) DO UPDATE SET day=excluded.day, content=excluded.content, charset=excluded.charset""",
                            (url, day, content, charset))
                    good += 1
                print(f'{index}/{len(rows)} {urlsplit(url).hostname}: {"cached" if error is None else error}', flush=True)
        print(f'Recovered {good} of {len(rows)} pages. AI has not been called.')


if __name__ == '__main__':
    main()
