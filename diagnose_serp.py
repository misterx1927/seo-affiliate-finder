"""Single-query DataForSEO diagnostic. Offline by default; no retries or AI calls."""
import argparse
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.config import load_env
from src.keywords import KEYWORDS
from src.providers import RequestAllowance, post_json
from src.serp import build_task

ENDPOINT = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"


def diagnostic_task(*, ungroup=False):
    task = build_task(KEYWORDS[0], 20)
    # The provider charges one extra SERP page for this opt-in verification.
    task["resolve_poisoned_results"] = True
    if ungroup:
        task["group_organic_results"] = False
    return task


def summarize(payload):
    """Keep enough provider metadata to inspect completeness without storing HTML."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid DataForSEO response")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        raise ValueError("Expected one DataForSEO task")
    task = tasks[0]
    results = task.get("result")
    if payload.get("status_code") != 20000 or task.get("status_code") != 20000:
        return {"status_code": payload.get("status_code"), "task_status_code": task.get("status_code"),
                "task_id": task.get("id"), "cost": payload.get("cost"), "check_url": None,
                "pages_count": None, "items_count": None, "counts": {}, "organic": []}
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError("DataForSEO did not return one result")
    result = results[0]
    items = result.get("items")
    if not isinstance(items, list):
        raise ValueError("DataForSEO did not return items")
    counts, organic = {}, []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid item in DataForSEO response")
        kind = item.get("type")
        if isinstance(kind, str):
            counts[kind] = counts.get(kind, 0) + 1
        if kind == "organic":
            related = item.get("related_result")
            organic.append({"rank_group": item.get("rank_group"),
                            "rank_absolute": item.get("rank_absolute"),
                            "page": item.get("page"), "url": item.get("url"),
                            "checks": item.get("checks"),
                            "related_count": len(related) if isinstance(related, list) else 0})
    return {"status_code": payload.get("status_code"), "task_status_code": task.get("status_code"),
            "task_id": task.get("id"), "cost": payload.get("cost"),
            "check_url": result.get("check_url"), "pages_count": result.get("pages_count"),
            "items_count": result.get("items_count"), "counts": counts, "organic": organic}


def run_one(login, password, *, ungroup=False, transport=post_json):
    """Send exactly one paid request; errors are surfaced, not retried."""
    if not login or not password:
        raise ValueError("DataForSEO credentials are required")
    allowance = RequestAllowance(max_serp=1, max_llm=0, approved=True)
    allowance.take("serp")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    payload = transport(ENDPOINT, [diagnostic_task(ungroup=ungroup)],
                        {"Authorization": f"Basic {token}"}, timeout=300)
    return summarize(payload)


def main():
    parser = argparse.ArgumentParser(description="One-query diagnostic; offline unless explicitly authorized")
    parser.add_argument("--allow-paid", action="store_true", help="Authorize one paid DataForSEO request")
    parser.add_argument("--ungroup", action="store_true", help="Also request related results as separate organic items")
    args = parser.parse_args()
    task = diagnostic_task(ungroup=args.ungroup)
    print("One Google Canada mobile query, depth 20, poisoned-results verification enabled.")
    print("Estimated up to $0.006 at the published Live price; this is not a provider-enforced spending limit.")
    print("Request configuration:", json.dumps(task, ensure_ascii=False))
    if not args.allow_paid:
        print("DRY RUN: no network requests or charges.")
        return
    load_env()
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        parser.error("DataForSEO credentials are missing; no request sent")
    report = run_one(login, password, ungroup=args.ungroup)
    report["request"] = task
    folder = Path("exports/serp-diagnostics")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f"Saved {len(report['organic'])} organic results and diagnostic details to {path}.")
    print(f"Provider-reported cost: {report['cost']} USD; check actual billing if unavailable.")
    if report["status_code"] != 20000 or report["task_status_code"] != 20000:
        raise SystemExit("DataForSEO returned an unsuccessful status; inspect the diagnostic report.")


if __name__ == "__main__":
    main()
