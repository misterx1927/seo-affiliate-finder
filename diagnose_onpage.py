"""One-page, one-request diagnostic. Dry-run by default; no AI or SERP calls.

It does not feed downloaded text into the production cache or analysis pipeline.
The permanent attempt marker prevents a second paid attempt after an ambiguous
failure. Delete nothing automatically: inspect billing and marker manually.
"""
import argparse
import base64
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_env
from src.providers import post_json

ENDPOINT = "https://api.dataforseo.com/v3/on_page/content_parsing/live"
TARGET = "https://www.casino.org/canada/"
SOURCE = "DataForSEO OnPage Content Parsing Live"
REPORT_DIR = Path("exports/onpage-diagnostic")


def task():
    # Static parsing only: no JS, browser rendering, custom proxy or pool.
    return {"url": TARGET, "markdown_view": True, "accept_language": "en-CA"}


def eligible(conn):
    """A narrowly selected former connection error only, never a site block."""
    row = conn.execute("SELECT error FROM run_pages WHERE run_id=7 AND url=?", (TARGET,)).fetchone()
    return bool(row and row[0] == "Page connection failed")


def reported_cost(payload):
    cost = payload.get("cost") if isinstance(payload, dict) else None
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 <= cost < 1000:
        return None
    return float(cost)


def parse_response(payload):
    """Return bounded page markdown only when the documented response is coherent."""
    if not isinstance(payload, dict) or payload.get("status_code") != 20000:
        raise ValueError("Provider did not report success")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        raise ValueError("Expected exactly one provider task")
    entry = tasks[0]
    if entry.get("status_code") != 20000 or not isinstance(entry.get("data"), dict) or entry["data"].get("url") != TARGET:
        raise ValueError("Task failed or target does not match")
    results = entry.get("result")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError("Expected one page result")
    items = results[0].get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ValueError("Expected one page item")
    item = items[0]
    if item.get("type") != "content_parsing_element" or item.get("status_code") != 200:
        raise ValueError("Page unavailable or blocked")
    text = item.get("page_as_markdown")
    if not isinstance(text, str) or len(text.strip()) < 80:
        raise ValueError("Page content missing or too short")
    lowered = text.lower()
    if any(marker in lowered for marker in ("verify you are human", "checking your browser", "captcha", "just a moment...", "are you a robot", "êtes-vous un robot")):
        raise ValueError("Possible access challenge; manual review required")
    if "ist in deinem gebiet" in lowered[:1000] or "not available in your region" in lowered[:1000]:
        raise ValueError("Possible regional mismatch; manual review required")
    # Content can be truncated here; the report remains a diagnostic, not an analysis.
    return {"task_id": entry.get("id") if isinstance(entry.get("id"), str) else None,
            "fetch_time": item.get("fetch_time") if isinstance(item.get("fetch_time"), str) else None,
            "page_http_status": 200, "text_characters": len(text),
            "text_truncated": len(text) > 40_000}, text[:40_000]


def run_one(login, password, transport=post_json):
    """Exactly one request; caller creates the persistent marker first."""
    if not login or not password:
        raise ValueError("Missing DataForSEO credentials")
    token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    return transport(ENDPOINT, [task()], {"Authorization": "Basic " + token}, timeout=180)


def main():
    parser = argparse.ArgumentParser(description="Single page content diagnostic, dry-run by default")
    parser.add_argument("--allow-paid", action="store_true", help="Allow one paid request")
    args = parser.parse_args()
    print(f"Target: {TARGET}; source: {SOURCE}")
    print("Static content only; published base price $0.00015/page, subject to provider billing.")
    print("Request:", json.dumps(task()))
    if not args.allow_paid:
        print("DRY RUN: no credentials loaded, no network requests or charges.")
        return
    if not Path("data/live.db").is_file():
        raise SystemExit("Run 7 database missing; no request made")
    conn = sqlite3.connect("file:data/live.db?mode=ro", uri=True)
    try:
        if not eligible(conn):
            raise SystemExit("Page is not the selected run 7 connection error; no request made")
    finally:
        conn.close()
    load_env()
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise SystemExit("Missing credentials; no request made")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    marker = REPORT_DIR / "attempt.json"
    report = {"source": SOURCE, "url": TARGET, "request": task(),
              "started_at": datetime.now(timezone.utc).isoformat(), "status": "started",
              "reported_cost_usd": None}
    try:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    except FileExistsError:
        raise SystemExit("Attempt already exists; no repeated request made")
    try:
        payload = run_one(login, password)
        report["reported_cost_usd"] = reported_cost(payload)
        summary, text = parse_response(payload)
        report.update(summary)
        (REPORT_DIR / "page.txt").write_text(text, encoding="utf-8")
        report["status"] = "text_returned_unverified"
        print("Page text received for manual verification; it was not sent to AI.")
    except Exception as exc:
        report["status"] = "needs_review"
        report["error_type"] = type(exc).__name__
        print("Diagnostic did not provide usable text; inspect cost and billing before any retry.")
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved source, status and reported cost in {marker}.")


if __name__ == "__main__":
    main()
