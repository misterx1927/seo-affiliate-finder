"""Bounded OnPage diagnostic for eight previously unreachable URLs.

Dry-run by default. No AI calls, SERP calls, retries, JavaScript or browser
rendering. An SQLite marker is committed before each request so an ambiguous
failure will never be automatically retried. This is a diagnostic, not an
automatic fallback for HTTP blocks or access challenges.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from diagnose_onpage import ENDPOINT, SOURCE, reported_cost
from src.config import load_env
from src.database import connect
from src.parser import extract_text
from src.providers import post_json
from src.run_lock import RunLock

# One URL per host. Each had "Page connection failed" in run 7. The earlier
# single-page diagnostic URL is intentionally excluded, even if re-run.
CANDIDATES = (
    "https://chipy.com/ca/bonus-blog/free-spins-no-deposit",
    "https://www.slotozilla.com/ca/free-spins",
    "https://www.alc.ca/content/alc/en/play-online/casino.html",
    "https://ca.888casino.com/",
    "https://www.betsafe.com/ca/casino",
    "https://www.comeon.com/on/casino/explore",
    "https://casino.draftkings.com/on-ca-online-casino",
    "https://www.leovegas.com/en-ca",
    # Additional distinct pages from domains for which the prior provider
    # diagnostic returned page content, not a challenge or an HTTP denial.
    "https://www.casino.org/canada/bonus-no-deposit/",
    "https://www.casino.org/canada/bonus/free-spins/",
    "https://www.casino.org/canada/new/",
    "https://www.slotozilla.com/ca/no-deposit-bonus",
)
MAX_URLS = 8


class OnPageRejected(ValueError):
    """A safe, locally generated diagnostic reason."""
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def eligible_urls(conn):
    """Allow only the fixed URLs which were connection errors in run 7.

    Never follow up on a host with a recorded run 7 HTTP block. Previously
    attempted and already cached URLs are excluded.
    """
    rows = conn.execute("SELECT url, error FROM run_pages WHERE run_id=7").fetchall()
    errors = {row[0]: row[1] for row in rows}
    blocked_hosts = {urlsplit(url).hostname for url, error in errors.items()
                     if isinstance(error, str) and ("HTTP 403" in error or "HTTP 451" in error
                                                    or "captcha" in error.lower())}
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    attempted = set()
    if "onpage_batch_attempts" in tables:
        attempted = {row[0] for row in conn.execute("SELECT url FROM onpage_batch_attempts")}
    cached = {row[0] for row in conn.execute("SELECT url FROM page_cache")}
    return [url for url in CANDIDATES if errors.get(url) == "Page connection failed"
            and urlsplit(url).hostname not in blocked_hosts and url not in attempted and url not in cached]


def prepare_attempts(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS onpage_batch_attempts (
        url TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL, reported_cost_usd REAL, error TEXT, content_sha256 TEXT
    )""")
    conn.commit()


def reserve(conn, url):
    """One persistent marker per URL; committed before calling the provider."""
    cursor = conn.execute("INSERT OR IGNORE INTO onpage_batch_attempts(url, started_at, status) VALUES (?, ?, 'started')", (url, now()))
    conn.commit()
    return cursor.rowcount == 1


def task(url):
    if url not in CANDIDATES:
        raise ValueError("URL is outside the fixed diagnostic set")
    return {"url": url, "markdown_view": True, "accept_language": "en-CA"}


def extract(payload, url):
    """Accept only one successful page result with useful non-challenge text."""
    if not isinstance(payload, dict) or payload.get("status_code") != 20000:
        raise OnPageRejected("Provider did not report success")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        raise OnPageRejected("Expected exactly one provider task")
    entry = tasks[0]
    if entry.get("status_code") != 20000 or not isinstance(entry.get("data"), dict) or entry["data"].get("url") != url:
        raise OnPageRejected("Task failed or target did not match")
    results = entry.get("result")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise OnPageRejected("Expected one page result")
    items = results[0].get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise OnPageRejected("Expected one page item")
    item = items[0]
    if item.get("type") != "content_parsing_element" or item.get("status_code") != 200:
        raise OnPageRejected("Page unavailable or blocked")
    text = item.get("page_as_markdown")
    if not isinstance(text, str) or len(text.strip()) < 80:
        raise OnPageRejected("Page content missing or too short")
    if any(s in text.lower() for s in ("verify you are human", "checking your browser", "captcha", "just a moment...", "are you a robot", "êtes-vous un robot")):
        raise OnPageRejected("Possible access challenge; manual review required")
    if "ist in deinem gebiet" in text.lower()[:1000] or "not available in your region" in text.lower()[:1000]:
        raise OnPageRejected("Possible regional mismatch; manual review required")
    clipped = text[:40_000]
    # A container for plain provider-extracted text, not claimed as original HTML.
    blob = ("<html><body><p>" + html.escape(clipped) + "</p></body></html>").encode("utf-8")
    extract_text(blob, "utf-8")  # Apply existing quality/size checks before saving.
    meta = {"task_id": entry.get("id") if isinstance(entry.get("id"), str) else None,
            "fetch_time": item.get("fetch_time") if isinstance(item.get("fetch_time"), str) else None,
            "page_http_status": 200, "text_characters": len(text), "text_truncated": len(text) > len(clipped),
            "representation": "provider markdown in HTML-escaped text container", "endpoint": ENDPOINT,
            "reported_cost_usd": reported_cost(payload), "verification": "provider result, manually unverified"}
    return blob, meta


def store_result(conn, url, blob, meta):
    digest = hashlib.sha256(blob).hexdigest()
    retrieved = now()
    with conn:
        # Do not replace content fetched or imported by another process meanwhile.
        conn.execute("INSERT INTO page_cache(url,day,content,charset) VALUES (?, ?, ?, 'utf-8')",
                     (url, retrieved[:10], blob))
        conn.execute("INSERT INTO page_cache_provenance(url,source,retrieved_at,content_sha256,details_json) VALUES (?,?,?,?,?)",
                     (url, SOURCE, retrieved, digest, json.dumps(meta, ensure_ascii=False)))
        conn.execute("UPDATE onpage_batch_attempts SET status='text_returned_unverified', finished_at=?, reported_cost_usd=?, content_sha256=? WHERE url=?",
                     (now(), meta['reported_cost_usd'], digest, url))


def run_batch(conn, login, password, urls, transport=post_json, progress=print):
    """Perform at most eight new requests; failures are never retried."""
    if not login or not password:
        raise ValueError("Missing credentials")
    if len(urls) > MAX_URLS or len(set(urls)) != len(urls) or any(url not in CANDIDATES for url in urls):
        raise ValueError("Invalid diagnostic set")
    prepare_attempts(conn)
    token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    outcomes = []
    for url in urls:
        # Re-check eligibility before each reservation; only the failed run 7 URLs.
        if url not in eligible_urls(conn) or not reserve(conn, url):
            outcomes.append((url, "skipped"))
            continue
        progress("Page " + (urlsplit(url).hostname or "unknown"))
        cost = None
        provider_failed = False
        try:
            response = transport(ENDPOINT, [task(url)], {"Authorization": "Basic " + token}, timeout=180)
            cost = reported_cost(response)
            provider_failed = not isinstance(response, dict) or response.get("status_code") != 20000
            if not provider_failed:
                entries = response.get("tasks")
                provider_failed = (not isinstance(entries, list) or len(entries) != 1 or
                                   not isinstance(entries[0], dict) or entries[0].get("status_code") != 20000)
            blob, meta = extract(response, url)
            store_result(conn, url, blob, meta)
            outcomes.append((url, "text_returned_unverified"))
        except Exception as exc:
            with conn:
                conn.execute("UPDATE onpage_batch_attempts SET status='needs_review', finished_at=?, reported_cost_usd=?, error=? WHERE url=?",
                             (now(), cost, str(exc) if isinstance(exc, OnPageRejected) else type(exc).__name__, url))
            outcomes.append((url, "needs_review"))
            # Network/provider errors may indicate a billing or availability issue;
            # stop rather than blindly submit remaining paid requests.
            if cost is None or provider_failed:
                break
    return outcomes


def main():
    parser = argparse.ArgumentParser(description="Up to eight one-shot page diagnostics; dry-run by default")
    parser.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    db = Path("data/live.db")
    if not db.is_file():
        raise SystemExit("Live database missing; no request made")
    if not args.allow_paid:
        conn = sqlite3.connect("file:data/live.db?mode=ro", uri=True)
        try:
            urls = eligible_urls(conn)
        finally:
            conn.close()
        print("DRY RUN: no network, no credentials loaded, no database changes.")
        for url in urls: print(url)
        print(f"Eligible: {len(urls)}; published estimate ${len(urls)*0.00015:.5f}; actual provider billing may differ.")
        return
    load_env()
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise SystemExit("Missing credentials; no request made")
    with RunLock('data/live.lock'):
        conn = connect(db)
        try:
            urls = eligible_urls(conn)
            print(f"Eligible: {len(urls)}; at most one request per URL, no AI calls.")
            outcomes = run_batch(conn, login, password, urls)
            print("Results:", json.dumps(outcomes, ensure_ascii=False))
        finally:
            conn.close()


if __name__ == "__main__":
    main()
