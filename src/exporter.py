"""CSV export for review; protects spreadsheet users from formula injection."""
import csv
import json
from pathlib import Path
import sqlite3

def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")) else text

def serp_provenance(position: int, ranks: str | None, requested: int | None) -> str:
    if requested is None:
        return "unknown"
    if not requested:
        return "verification_not_requested"
    try:
        web_ranks = json.loads(ranks or "[]")
    except (ValueError, TypeError):
        return "unknown"
    if not isinstance(web_ranks, list):
        return "unknown"
    return "restored_from_google_web" if position in web_ranks else "original_or_verification_unavailable"

def export_observations(conn: sqlite3.Connection, destination: str | Path, run_id: int | None = None) -> int:
    if run_id is None:
        source = "observations o"
        params = ()
    else:
        # Prefer the immutable run snapshot. Legacy runs may only have rows in
        # the current view, so retain those only for keywords without an archive.
        source = """(SELECT day, keyword, position, url, domain, run_id
                     FROM run_observations WHERE run_id = ?
                     UNION ALL
                     SELECT v.day, v.keyword, v.position, v.url, v.domain, v.run_id
                     FROM observations v WHERE v.run_id = ? AND NOT EXISTS
                     (SELECT 1 FROM run_observations a
                      WHERE a.run_id = v.run_id AND a.keyword = v.keyword)) o"""
        params = (run_id, run_id)
    rows = conn.execute(f"""SELECT o.day, o.keyword, o.position, o.url, o.domain,
           CASE WHEN tr.run_id IS NOT NULL THEN COALESCE(h.status, 'pending') ELSE p.status END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.relevance ELSE p.relevance END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.brands_json ELSE p.brands_json END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.contact ELSE p.contact END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.evidence_json ELSE p.evidence_json END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.analysis_version ELSE p.analysis_version END,
           d.from_web_ranks, d.verification_requested, CASE WHEN tr.run_id IS NOT NULL THEN 'not_recorded' ELSE ps.source END,
           (SELECT email FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1),
           (SELECT source_url FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1)
           FROM {source} LEFT JOIN pages p ON p.url = o.url
           LEFT JOIN run_analysis_tracking tr ON tr.run_id=o.run_id
           LEFT JOIN run_page_analysis h ON h.run_id=o.run_id AND h.url=o.url
           LEFT JOIN serp_diagnostics d ON d.run_id=o.run_id AND d.keyword=o.keyword
           LEFT JOIN page_cache_provenance ps ON ps.url=o.url
           ORDER BY o.day DESC, o.keyword, o.position""", params).fetchall()
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "keyword", "position", "url", "domain", "analysis_status", "relevance", "brands", "contact", "evidence", "analysis_version", "serp_provenance", "page_source", "public_contact_candidate", "contact_candidate_source"])
        writer.writerows([safe_cell(value) for value in (*row[:-5], serp_provenance(row[2], row[-5], row[-4]), row[-3] or 'direct_or_unknown', row[-2], row[-1])] for row in rows)
    return len(rows)


def export_partial_observations(conn: sqlite3.Connection, destination: str | Path, run_id: int | None = None) -> int:
    """Export incomplete results separately so they never replace completed history."""
    rows = conn.execute("""SELECT o.run_id, o.day, o.keyword, o.position, o.url, o.domain,
           CASE WHEN tr.run_id IS NOT NULL THEN COALESCE(h.status, 'pending') ELSE p.status END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.relevance ELSE p.relevance END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.brands_json ELSE p.brands_json END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.contact ELSE p.contact END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.evidence_json ELSE p.evidence_json END,
           CASE WHEN tr.run_id IS NOT NULL THEN h.analysis_version ELSE p.analysis_version END,
           d.from_web_ranks, d.verification_requested, CASE WHEN tr.run_id IS NOT NULL THEN 'not_recorded' ELSE ps.source END,
           (SELECT email FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1),
           (SELECT source_url FROM outreach_contact_candidates x WHERE x.page_url=o.url ORDER BY x.observed_at DESC,x.email,x.source_url LIMIT 1)
           FROM partial_observations o LEFT JOIN pages p ON p.url = o.url
           LEFT JOIN run_analysis_tracking tr ON tr.run_id=o.run_id
           LEFT JOIN run_page_analysis h ON h.run_id=o.run_id AND h.url=o.url
           LEFT JOIN serp_diagnostics d ON d.run_id=o.run_id AND d.keyword=o.keyword
           LEFT JOIN page_cache_provenance ps ON ps.url=o.url
           WHERE (? IS NULL OR o.run_id = ?)
           ORDER BY o.run_id DESC, o.keyword, o.position""", (run_id, run_id)).fetchall()
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["run_id", "date", "keyword", "position", "url", "domain", "analysis_status", "relevance", "brands", "contact", "evidence", "analysis_version", "serp_provenance", "page_source", "public_contact_candidate", "contact_candidate_source"])
        writer.writerows([safe_cell(value) for value in (*row[:-5], serp_provenance(row[3], row[-5], row[-4]), row[-3] or 'direct_or_unknown', row[-2], row[-1])] for row in rows)
    return len(rows)
