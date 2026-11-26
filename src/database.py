"""SQLite persistence for daily observations and reusable page analyses."""
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from .urls import normalize_url

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS runs (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
 mode TEXT NOT NULL, status TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS observations (
 day TEXT NOT NULL, keyword TEXT NOT NULL, position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 10),
 url TEXT NOT NULL, domain TEXT NOT NULL, run_id INTEGER REFERENCES runs(id),
 PRIMARY KEY(day, keyword, position)
);
CREATE INDEX IF NOT EXISTS observations_url ON observations(url);
CREATE TABLE IF NOT EXISTS run_keywords (
 run_id INTEGER NOT NULL REFERENCES runs(id), day TEXT NOT NULL, keyword TEXT NOT NULL,
 status TEXT NOT NULL, error TEXT, PRIMARY KEY(run_id, keyword)
);
CREATE TABLE IF NOT EXISTS partial_observations (
 run_id INTEGER NOT NULL REFERENCES runs(id), day TEXT NOT NULL, keyword TEXT NOT NULL,
 position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 10), url TEXT NOT NULL, domain TEXT NOT NULL,
 PRIMARY KEY(run_id, keyword, position)
);
CREATE TABLE IF NOT EXISTS page_cache (
 url TEXT PRIMARY KEY, day TEXT NOT NULL, content BLOB NOT NULL, charset TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_cache_provenance (
 url TEXT PRIMARY KEY, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 content_sha256 TEXT, details_json TEXT
);
CREATE TABLE IF NOT EXISTS outreach_contact_candidates (
 page_url TEXT NOT NULL, source_url TEXT NOT NULL, email TEXT NOT NULL,
 observed_at TEXT NOT NULL, PRIMARY KEY(page_url, source_url, email)
);
CREATE TABLE IF NOT EXISTS api_usage (
 id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id), service TEXT NOT NULL,
 model TEXT, cost_usd REAL, input_tokens INTEGER, output_tokens INTEGER, recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS serp_diagnostics (
 run_id INTEGER NOT NULL REFERENCES runs(id), keyword TEXT NOT NULL,
 items_by_type TEXT NOT NULL, organic_ranks TEXT NOT NULL,
 from_web_ranks TEXT, verification_requested INTEGER,
 PRIMARY KEY(run_id, keyword)
);
CREATE TABLE IF NOT EXISTS run_pages (
 run_id INTEGER NOT NULL REFERENCES runs(id), url TEXT NOT NULL, status TEXT NOT NULL,
 error TEXT, PRIMARY KEY(run_id, url)
);
CREATE TABLE IF NOT EXISTS pages (
 url TEXT PRIMARY KEY, content_hash TEXT, analyzed_at TEXT, status TEXT NOT NULL,
 relevance TEXT, brands_json TEXT, contact TEXT, evidence_json TEXT, error TEXT,
 analysis_version TEXT
);
"""

def connect(path: str | Path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(pages)")}
    if "analysis_version" not in columns:
        conn.execute("ALTER TABLE pages ADD COLUMN analysis_version TEXT")
    diagnostic_columns = {row["name"] for row in conn.execute("PRAGMA table_info(serp_diagnostics)")}
    if "from_web_ranks" not in diagnostic_columns:
        conn.execute("ALTER TABLE serp_diagnostics ADD COLUMN from_web_ranks TEXT")
    if "verification_requested" not in diagnostic_columns:
        conn.execute("ALTER TABLE serp_diagnostics ADD COLUMN verification_requested INTEGER")
    source_columns = {row['name'] for row in conn.execute('PRAGMA table_info(page_cache_provenance)')}
    if 'content_sha256' not in source_columns:
        conn.execute('ALTER TABLE page_cache_provenance ADD COLUMN content_sha256 TEXT')
    if 'details_json' not in source_columns:
        conn.execute('ALTER TABLE page_cache_provenance ADD COLUMN details_json TEXT')
    return conn

def replace_keyword_results(conn: sqlite3.Connection, day: str, keyword: str, results: list[dict], run_id: int | None = None) -> None:
    """Atomically replace one complete result set; invalid input leaves prior data intact."""
    if not results or len(results) > 10:
        raise ValueError("Expected between 1 and 10 organic results")
    rows = []
    seen = set()
    for result in results:
        position = result["position"]
        if type(position) is not int or not 1 <= position <= 10 or position in seen:
            raise ValueError("Invalid or duplicate position")
        seen.add(position)
        url = normalize_url(result["url"])
        rows.append((day, keyword, position, url, urlsplit(url).hostname, run_id))
    with conn:
        conn.execute("DELETE FROM observations WHERE day=? AND keyword=?", (day, keyword))
        conn.executemany("INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)", rows)
