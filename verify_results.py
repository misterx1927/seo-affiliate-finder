"""Audit a saved search snapshot without contacting APIs or changing data."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from src.keywords import KEYWORDS


def inspect(path: Path) -> tuple[dict, list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    errors = []
    positions = defaultdict(list)
    by_url = {}
    sources = Counter()
    for row in rows:
        try:
            position = int(row["position"])
            keyword, url = row["keyword"], row["url"]
            if not keyword or not url or not row["date"]:
                raise ValueError("empty keyword, URL or date")
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
                raise ValueError("invalid page URL")
            if row.get("domain") and row["domain"].lower() != parts.hostname.lower():
                raise ValueError("domain does not match page URL")
            positions[(row["date"], keyword)].append(position)
            sources[row.get("serp_provenance", "unknown")] += 1
            previous = by_url.get(url)
            if previous:
                for field in ("analysis_status", "relevance", "brands", "contact"):
                    if field in row and row.get(field) != previous.get(field):
                        errors.append(f"Conflicting {field} for repeated URL: {url}")
            by_url[url] = row
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"Invalid row: {exc}")
    days = {day for day, _ in positions}
    if len(days) != 1:
        errors.append("Expected one search date")
    for day in days:
        for keyword in KEYWORDS:
            found = positions.get((day, keyword), [])
            if sorted(found) != list(range(1, 11)):
                errors.append(f"{keyword}: expected positions 1–10 exactly once")
    if {keyword for _, keyword in positions} != set(KEYWORDS):
        errors.append("Search keyword set differs from the requested ten keywords")
    statuses = Counter()
    for row in by_url.values():
        status = row.get("analysis_status")
        if status == "complete":
            statuses[row.get("relevance") or "uncertain"] += 1
        elif status == "supplementary_review":
            statuses["supplementary_review"] += 1
        else:
            statuses["no_accepted_analysis"] += 1
    return {"rows": len(rows), "keywords": len({key for _, key in positions}),
            "unique_urls": len(by_url), "analysis": dict(statuses), "serp_provenance": dict(sources)}, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path("results/run-7-with-recovery.csv"))
    args = parser.parse_args()
    report, errors = inspect(args.path)
    print(json.dumps({"snapshot": str(args.path), **report, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
