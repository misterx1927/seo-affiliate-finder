"""Find public same-domain email candidates on linked contact pages.

Dry-run by default. No Google or paid API requests. Candidates are unverified.
"""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from src.contact_discovery import choose_contact, contact_pages, public_email_candidates
from src.database import connect
from src.exporter import safe_cell
from src.fetcher import fetch_page
from src.parser import extract_text
from src.run_lock import RunLock


def load_targets(conn, run_id, limit):
    rows = conn.execute("""SELECT DISTINCT p.url, c.content, c.charset FROM observations o
        JOIN pages p ON p.url=o.url JOIN page_cache c ON c.url=p.url
        WHERE o.run_id=? AND (p.relevance IN ('yes', 'needs_review') OR p.status='needs_review')
          AND (p.contact IS NULL OR trim(p.contact)='') ORDER BY p.url LIMIT ?""", (run_id, limit)).fetchall()
    targets = {}
    for row in rows:
        for source in contact_pages(row['content'], row['charset'], row['url']):
            targets.setdefault(source, set()).add(row['url'])
    return targets


def inspect_page(url):
    try:
        content, charset = fetch_page(url, timeout=6, same_origin_only=True)
        text = extract_text(content, charset)
        return choose_contact(public_email_candidates(text), url), None
    except Exception as exc:
        return None, f'{type(exc).__name__}: {exc}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--max-pages', type=int, choices=range(1, 31), default=20)
    parser.add_argument('--fetch', action='store_true', help='Fetch public contact pages; never uses paid APIs')
    args = parser.parse_args()
    with RunLock('data/live.lock'), connect('data/live.db') as conn:
        targets = load_targets(conn, args.run, args.max_pages)
        print(f'{len(targets)} unique same-origin contact pages found; no paid APIs.', flush=True)
        if not args.fetch:
            print('DRY RUN: no page requests.')
            for source in targets: print(urlsplit(source).hostname)
            return
        conn.execute("""CREATE TABLE IF NOT EXISTS outreach_contact_candidates (
            page_url TEXT NOT NULL, source_url TEXT NOT NULL, email TEXT NOT NULL,
            observed_at TEXT NOT NULL, PRIMARY KEY(page_url, source_url, email))""")
        conn.commit()
        found = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            pending = {executor.submit(inspect_page, source): source for source in targets}
            for index, future in enumerate(as_completed(pending), 1):
                source = pending[future]
                email, error = future.result()
                if email:
                    with conn:
                        conn.executemany("""INSERT OR REPLACE INTO outreach_contact_candidates(page_url,source_url,email,observed_at)
                            VALUES(?,?,?,?)""", [(page, source, email, datetime.now(timezone.utc).isoformat()) for page in targets[source]])
                    found += 1
                print(f'{index}/{len(targets)} {urlsplit(source).hostname}: {"candidate found" if email else (error or "no unambiguous same-domain email")}', flush=True)
        path = Path('exports/contact-candidates.csv')
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = conn.execute("""SELECT DISTINCT x.page_url, x.source_url, x.email, x.observed_at FROM outreach_contact_candidates x
            JOIN observations o ON o.url=x.page_url WHERE o.run_id=? ORDER BY x.page_url,x.source_url""", (args.run,)).fetchall()
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['page_url', 'source_url', 'public_email_candidate', 'observed_at', 'verification'])
            writer.writerows([safe_cell(value) for value in (*row, 'unverified public contact; partnership suitability unknown')] for row in rows)
        print(f'{found} contact pages returned a candidate; {len(rows)} candidate rows saved to {path}.')


if __name__ == '__main__':
    main()
