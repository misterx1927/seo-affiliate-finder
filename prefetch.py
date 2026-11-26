"""Fetch public pages from one existing partial run without any paid API calls."""
import argparse
from src.database import connect
from src.fetcher import fetch_with_retry
from src.parser import extract_text
from src.serp import is_google_redirect

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", type=int)
    args = parser.parse_args()
    with connect("data/live.db") as conn:
        rows = conn.execute("SELECT DISTINCT url, day FROM partial_observations WHERE run_id=? ORDER BY position", (args.run_id,)).fetchall()
        if not rows: raise SystemExit("No partial URLs found for this run.")
        for index, row in enumerate(rows, 1):
            url, day = row['url'], row['day']
            if is_google_redirect(url):
                print(f"{index}/{len(rows)}: unresolved redirect; skipped", flush=True)
                continue
            try:
                content, charset = fetch_with_retry(url)
                text = extract_text(content, charset)
                with conn:
                    conn.execute("DELETE FROM page_cache_provenance WHERE url=?", (url,))
                    conn.execute("""INSERT INTO page_cache(url,day,content,charset) VALUES (?, ?, ?, ?)
                        ON CONFLICT(url) DO UPDATE SET day=excluded.day, content=excluded.content, charset=excluded.charset""", (url,day,content,charset))
                    conn.execute("INSERT INTO pages(url,status) VALUES (?, 'pending') ON CONFLICT(url) DO NOTHING", (url,))
                print(f"{index}/{len(rows)}: text available ({len(text)} characters)", flush=True)
            except Exception as exc:
                with conn:
                    conn.execute("""INSERT INTO pages(url,status,error) VALUES (?, 'needs_review', ?) ON CONFLICT(url)
                        DO UPDATE SET status='needs_review', relevance=NULL, brands_json=NULL, contact=NULL, evidence_json=NULL, error=excluded.error""", (url, str(exc)))
                print(f"{index}/{len(rows)}: needs review ({type(exc).__name__}: {exc})", flush=True)

if __name__ == "__main__": main()
