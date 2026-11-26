"""Compare a single fresh SerpApi result with DataForSEO; opt-in and key required.

Set SERPAPI_API_KEY in the environment. The key is never printed or persisted.
This diagnostic does not modify the stored run or claim to establish ground truth.
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from diagnose_serp import run_one
from src.config import load_env
from src.keywords import KEYWORDS
from src.providers import _NoRedirect
from src.tls import tls_context


def serpapi_request(keyword, key):
    params = {"engine": "google", "q": keyword, "google_domain": "google.ca",
              "gl": "ca", "hl": "en", "location": "Canada", "device": "mobile", "no_cache": "true",
              "api_key": key}
    request = urllib.request.Request("https://serpapi.com/search.json?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=tls_context())).open(request, timeout=90) as response:
            data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError("SerpApi response too large")
        result = json.loads(data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Never include exceptions: URLs can contain the API key.
        raise RuntimeError("SerpApi request failed; no DataForSEO request was sent") from None
    if not isinstance(result, dict) or result.get("error") or not isinstance(result.get("search_metadata"), dict) or result["search_metadata"].get("status") != "Success":
        raise RuntimeError("SerpApi did not return a successful search; no DataForSEO request was sent")
    rows = result.get("organic_results")
    if not isinstance(rows, list):
        raise RuntimeError("SerpApi returned no organic results; no DataForSEO request was sent")
    return [{"rank": row.get("position"), "url": row.get("link")} for row in rows[:10]
            if isinstance(row, dict) and isinstance(row.get("link"), str)]


def compare(serpapi_rows, dataforseo_rows):
    a = {r["url"] for r in serpapi_rows if r.get("url")}
    b = {r["url"] for r in dataforseo_rows if r.get("url")}
    by_rank = {r.get("rank"): r.get("url") for r in dataforseo_rows}
    exact_rank = sum(1 for r in serpapi_rows if r.get("url") and by_rank.get(r.get("rank")) == r["url"])
    return {"exact_url_overlap": len(a & b), "exact_rank_matches": exact_rank}


def main():
    parser = argparse.ArgumentParser(description="Compare fresh Google Canada mobile SERPs from two providers")
    parser.add_argument("--keyword", choices=KEYWORDS, default=KEYWORDS[0])
    parser.add_argument("--allow-paid", action="store_true", help="Make one request to each provider")
    args = parser.parse_args()
    if not args.allow_paid:
        print("Dry run: one SerpApi and one DataForSEO request would be made; no requests sent.")
        return
    key = os.getenv("SERPAPI_API_KEY")
    if not key:
        parser.error("SERPAPI_API_KEY is missing; no requests sent")
    load_env()
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        parser.error("DataForSEO credentials are missing; no requests sent")
    started = datetime.now(timezone.utc).isoformat()
    first = serpapi_request(args.keyword, key)
    if len(first) != 10 or {r.get("rank") for r in first} != set(range(1, 11)):
        raise RuntimeError("SerpApi did not return ten unique ranks; no DataForSEO request was sent")
    diagnostic = run_one(login, password, keyword=args.keyword)
    second = [{"rank": r.get("rank_group"), "url": r.get("url"), "checks": r.get("checks")}
              for r in diagnostic["organic"][:10]]
    report = {"keyword": args.keyword, "started_at_utc": started,
              "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "settings": "google.ca, Canada, English, mobile; SerpApi cache disabled",
              "serpapi": first, "dataforseo": second,
              "dataforseo_reported_cost": diagnostic.get("cost"),
              "comparison": compare(first, second),
              "limitations": "Different providers/times. Agreement does not establish Google ground truth. DataForSEO from_web flags are retained."}
    folder = Path("exports/serp-diagnostics")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (datetime.now(timezone.utc).strftime("comparison-%Y%m%dT%H%M%S%fZ") + ".json")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print("Comparison saved to", path)
    print(json.dumps(report["comparison"]))


if __name__ == "__main__":
    main()
