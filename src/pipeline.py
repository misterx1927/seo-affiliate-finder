"""Offline end-to-end pipeline. Fixture providers cannot access the network."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from .analyzer import validate_analysis
from .database import replace_keyword_results
from .keywords import KEYWORDS
from .parser import extract_text
from .serp import parse_response

def run_offline(conn: sqlite3.Connection, day: str, fixtures: Path = Path("tests/fixtures")) -> dict:
    """Run fixtures, retain successful work and collect per-page errors."""
    raw = json.loads((fixtures / "dataforseo.json").read_text(encoding="utf-8-sig"))
    results = [asdict(item) for item in parse_response(raw)]
    demo_pages = json.loads((fixtures / "pages.json").read_text(encoding="utf-8-sig"))
    started = datetime.now(timezone.utc).isoformat()
    with conn:
        run_id = conn.execute("INSERT INTO runs (started_at, mode, status) VALUES (?, 'offline', 'running')", (started,)).lastrowid
    errors, analyzed, reused = [], 0, 0
    try:
        for keyword in KEYWORDS:
            replace_keyword_results(conn, day, keyword, results, run_id)
        for result in results:
            url = result["url"]
            try:
                sample = demo_pages[url]
                text = extract_text(sample["html"].encode("utf-8"))
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                existing = conn.execute("SELECT content_hash, status FROM pages WHERE url=?", (url,)).fetchone()
                if existing and existing["status"] == "complete" and existing["content_hash"] == digest:
                    reused += 1
                    continue
                analysis = validate_analysis(sample["analysis"], text)
                with conn:
                    conn.execute("""INSERT INTO pages (url, content_hash, analyzed_at, status, relevance, brands_json, contact, evidence_json, error)
                        VALUES (?, ?, ?, 'complete', ?, ?, ?, ?, NULL)
                        ON CONFLICT(url) DO UPDATE SET content_hash=excluded.content_hash, analyzed_at=excluded.analyzed_at,
                        status=excluded.status, relevance=excluded.relevance, brands_json=excluded.brands_json,
                        contact=excluded.contact, evidence_json=excluded.evidence_json, error=NULL""",
                        (url, digest, datetime.now(timezone.utc).isoformat(), analysis.relevance,
                         json.dumps(analysis.brands, ensure_ascii=False), analysis.contact, json.dumps(analysis.evidence, ensure_ascii=False)))
                analyzed += 1
            except (KeyError, ValueError, TypeError) as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
                with conn:
                    conn.execute("""INSERT INTO pages (url, status, error) VALUES (?, 'needs_review', ?)
                        ON CONFLICT(url) DO UPDATE SET status='needs_review', error=excluded.error""", (url, str(exc)))
        status = "partial" if errors else "complete"
    except Exception as exc:
        status = "failed"
        errors.append(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        with conn:
            conn.execute("UPDATE runs SET finished_at=?, status=?, error=? WHERE id=?",
                         (datetime.now(timezone.utc).isoformat(), status, json.dumps(errors, ensure_ascii=False), run_id))
    return {"run_id": run_id, "status": status, "observations": len(results) * len(KEYWORDS),
            "analyzed": analyzed, "reused": reused, "errors": errors}
