"""Read the bundled, reviewed snapshot without altering the live database."""
import csv
import json
from pathlib import Path


def snapshot_review(reviews: dict, url: str, day: str, status: str):
    """Apply the dated, manual review only to its original saved run.

    Later collections must not inherit old page content as a fresh assessment.
    """
    if day != "2026-11-25" or status == "complete":
        return None
    return reviews.get(url)


def load_snapshot(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        raw = list(csv.DictReader(source))
    rows = []
    for row in raw:
        position = int(row["position"])
        status = row["analysis_status"]
        restored = row.get("serp_provenance") == "restored_from_google_web"
        verification = row.get("serp_provenance") in {"restored_from_google_web", "original_or_verification_unavailable"}
        rows.append({
            "Date": row["date"], "Keyword": row["keyword"], "Position": position,
            "Domain": row["domain"], "URL": row["url"],
            "Relevance": row.get("relevance") or "needs_review",
            "Brands": row.get("brands") or "[]", "Contact": row.get("contact") or "",
            "Status": "complete" if status == "complete" else "needs_review",
            "Evidence": row.get("evidence") or "", "Error": "",
            "AnalysisVersion": row.get("analysis_version") or "",
            "WebRanks": json.dumps([position] if restored else []),
            "VerificationRequested": 1 if verification else None,
            "SnapshotSerpSource": row.get("serp_provenance") or "unknown",
            "PageSource": row.get("page_source") or "direct_or_unknown",
            "SnapshotReviewNote": row.get("review_note") or "",
            "ContactCandidate": row.get("public_contact_candidate") or "",
            "ContactCandidateSource": row.get("contact_candidate_source") or "",
        })
    return rows
