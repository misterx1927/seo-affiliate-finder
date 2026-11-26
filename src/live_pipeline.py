"""Live pipeline building blocks. Not exposed as a runnable command yet."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from .database import replace_keyword_results
from .parser import extract_text
from .run_lock import RunLock
from .serp import is_google_redirect
from urllib.parse import urlsplit

def _now(): return datetime.now(timezone.utc).isoformat()

def run_live(conn, day, keywords, serp, analyzer, fetch, lock_path, max_pages, resume_id=None, provider_factory=None, progress=None):
    """Persist each successful keyword and page independently. Providers enforce request limits.

    No paid retries are automatic: ambiguous failures may have already incurred charges.
    This internal function requires explicit caller-provided authorized providers.
    """
    if not keywords or max_pages < 0:
        raise ValueError("Keywords and non-negative page limit are required")
    with RunLock(lock_path):
        with conn:
            if resume_id is None:
                run_id = conn.execute("INSERT INTO runs(started_at, mode, status) VALUES (?, 'live', 'running')", (_now(),)).lastrowid
            else:
                previous = conn.execute("SELECT mode, status FROM runs WHERE id=?", (resume_id,)).fetchone()
                checkpoints = conn.execute("SELECT DISTINCT day FROM run_keywords WHERE run_id=?", (resume_id,)).fetchall()
                if not previous or previous["mode"] != "live" or previous["status"] == "complete" or any(row["day"] != day for row in checkpoints):
                    raise ValueError("Run cannot be resumed for this day")
                run_id = resume_id
                conn.execute("UPDATE runs SET status='running', finished_at=NULL WHERE id=?", (run_id,))
        errors, urls, complete_keywords = [], [], 0
        report = progress or (lambda message: None)
        status = "failed"
        try:
            if provider_factory is not None:
                serp, analyzer = provider_factory(run_id)
            if serp is None or analyzer is None:
                raise ValueError("Providers are required")
            for keyword_index, keyword in enumerate(keywords, 1):
                report(f"Search {keyword_index}/{len(keywords)}: {keyword}")
                checkpoint = conn.execute("SELECT status FROM run_keywords WHERE run_id=? AND keyword=?", (run_id, keyword)).fetchone()
                if checkpoint:
                    if checkpoint["status"] == "complete":
                        saved = conn.execute("SELECT url FROM observations WHERE run_id=? AND day=? AND keyword=? ORDER BY position", (run_id, day, keyword)).fetchall()
                        if len(saved) == 10:
                            urls.extend(row["url"] for row in saved)
                            complete_keywords += 1
                        else:
                            errors.append(f"search {keyword}: checkpoint data no longer available; manual review required")
                    elif checkpoint["status"] == "partial":
                        saved = conn.execute("SELECT url FROM partial_observations WHERE run_id=? AND day=? AND keyword=? ORDER BY position", (run_id, day, keyword)).fetchall()
                        urls.extend(row["url"] for row in saved if not is_google_redirect(row["url"]))
                        errors.append(f"search {keyword}: incomplete result retained ({len(saved)} of 10); manual review required")
                    else:
                        errors.append(f"search {keyword}: previous attempt needs manual review; no automatic paid retry")
                    continue
                with conn:
                    conn.execute("INSERT INTO run_keywords(run_id, day, keyword, status) VALUES (?, ?, ?, 'started')", (run_id, day, keyword))
                try:
                    results = serp.search(keyword)
                    if not results:
                        raise ValueError("No organic results; prior observations retained")
                    cost = getattr(serp, "last_cost", None)
                    with conn:
                        conn.execute("INSERT INTO api_usage(run_id,service,cost_usd,recorded_at) VALUES (?, 'serp', ?, ?)", (run_id, cost, _now()))
                        diagnostics = getattr(serp, "last_diagnostics", None)
                        if isinstance(diagnostics, dict):
                            conn.execute("INSERT OR REPLACE INTO serp_diagnostics(run_id,keyword,items_by_type,organic_ranks,from_web_ranks,verification_requested) VALUES (?, ?, ?, ?, ?, ?)",
                                         (run_id, keyword, json.dumps(diagnostics.get("items_by_type", {})), json.dumps(diagnostics.get("organic_ranks", [])), json.dumps(diagnostics.get("from_web_ranks", [])), int(diagnostics['verification_requested']) if isinstance(diagnostics.get('verification_requested'), bool) else None))
                    rows = [asdict(r) for r in results]
                    unresolved = [r for r in results if is_google_redirect(r.url)]
                    if len(results) != 10 or {r.position for r in results} != set(range(1, 11)) or unresolved:
                        with conn:
                            conn.executemany("INSERT INTO partial_observations(run_id,day,keyword,position,url,domain) VALUES (?, ?, ?, ?, ?, ?)",
                                [(run_id, day, keyword, r.position, r.url, urlsplit(r.url).hostname) for r in results])
                            conn.execute("UPDATE run_keywords SET status='partial' WHERE run_id=? AND keyword=?", (run_id, keyword))
                        errors.append(f"search {keyword}: {len(results)} results, {len(unresolved)} unresolved Google redirects; manual review required")
                    else:
                        replace_keyword_results(conn, day, keyword, rows, run_id)
                        with conn:
                            conn.execute("UPDATE run_keywords SET status='complete' WHERE run_id=? AND keyword=?", (run_id, keyword))
                        complete_keywords += 1
                    for r in unresolved:
                        with conn:
                            conn.execute("""INSERT INTO pages(url,status,error) VALUES (?, 'needs_review', 'Unresolved Google redirect')
                            ON CONFLICT(url) DO UPDATE SET status='needs_review', relevance=NULL, brands_json=NULL,
                            contact=NULL, evidence_json=NULL, error=excluded.error""", (r.url,))
                    urls.extend(r.url for r in results if not is_google_redirect(r.url))
                except Exception as exc:
                    errors.append(f"search {keyword}: {type(exc).__name__}: {exc}")
                    with conn:
                        if hasattr(exc, "serp_response_cost"):
                            conn.execute("INSERT INTO api_usage(run_id,service,cost_usd,recorded_at) VALUES (?, 'serp', ?, ?)",
                                         (run_id, exc.serp_response_cost, _now()))
                        conn.execute("UPDATE run_keywords SET status='needs_review', error=? WHERE run_id=? AND keyword=?", (str(exc), run_id, keyword))
            unique_urls = list(dict.fromkeys(urls))
            for page_index, url in enumerate(unique_urls[:max_pages], 1):
                report(f"Page {page_index}/{min(len(unique_urls), max_pages)}: {urlsplit(url).hostname}")
                checkpoint = conn.execute("SELECT status FROM run_pages WHERE run_id=? AND url=?", (run_id, url)).fetchone()
                if checkpoint:
                    if checkpoint["status"] != "complete":
                        errors.append(f"page {url}: previous attempt needs manual review; no automatic paid retry")
                    continue
                with conn:
                    conn.execute("INSERT INTO run_pages(run_id, url, status) VALUES (?, ?, 'started')", (run_id, url))
                try:
                    cached = conn.execute("SELECT content, charset FROM page_cache WHERE url=? AND day=?", (url, day)).fetchone()
                    if cached:
                        content, charset = cached["content"], cached["charset"]
                    else:
                        content, charset = fetch(url)
                    text = extract_text(content, charset, base_url=url)
                    if not cached:
                        with conn:
                            conn.execute("DELETE FROM page_cache_provenance WHERE url=?", (url,))
                            conn.execute("""INSERT INTO page_cache(url,day,content,charset) VALUES (?, ?, ?, ?)
                                ON CONFLICT(url) DO UPDATE SET day=excluded.day, content=excluded.content, charset=excluded.charset""",
                                (url, day, content, charset))
                    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    version = getattr(analyzer, "cache_version", "default-v1")
                    old = conn.execute("SELECT content_hash, status, analysis_version FROM pages WHERE url=?", (url,)).fetchone()
                    if old and old["status"] == "complete" and old["content_hash"] == digest and old["analysis_version"] == version:
                        with conn: conn.execute("UPDATE run_pages SET status='complete' WHERE run_id=? AND url=?", (run_id, url))
                        continue
                    analysis, usage = analyzer.analyze(text)
                    with conn:
                        if not isinstance(usage, dict): usage = {}
                        prompt_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                        if type(prompt_tokens) is not int or prompt_tokens < 0: prompt_tokens = None
                        if type(output_tokens) is not int or output_tokens < 0: output_tokens = None
                        conn.execute("INSERT INTO api_usage(run_id,service,model,input_tokens,output_tokens,recorded_at) VALUES (?, 'llm', ?, ?, ?, ?)",
                                     (run_id, getattr(analyzer, "model", None), prompt_tokens, output_tokens, _now()))
                        conn.execute("""INSERT INTO pages(url,content_hash,analyzed_at,status,relevance,brands_json,contact,evidence_json,error,analysis_version)
                        VALUES (?, ?, ?, 'complete', ?, ?, ?, ?, NULL, ?) ON CONFLICT(url) DO UPDATE SET
                        content_hash=excluded.content_hash, analyzed_at=excluded.analyzed_at,status=excluded.status,
                        relevance=excluded.relevance, brands_json=excluded.brands_json,contact=excluded.contact,
                        evidence_json=excluded.evidence_json,error=NULL,analysis_version=excluded.analysis_version""", (url, digest, _now(), analysis.relevance,
                        json.dumps(analysis.brands, ensure_ascii=False), analysis.contact, json.dumps(analysis.evidence, ensure_ascii=False), version))
                        conn.execute("UPDATE run_pages SET status='complete' WHERE run_id=? AND url=?", (run_id, url))
                except Exception as exc:
                    errors.append(f"page {url}: {type(exc).__name__}: {exc}")
                    with conn:
                        usage = getattr(exc, "usage", None)
                        if isinstance(usage, dict):
                            prompt_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
                            if type(prompt_tokens) is not int or prompt_tokens < 0: prompt_tokens = None
                            if type(output_tokens) is not int or output_tokens < 0: output_tokens = None
                            conn.execute("INSERT INTO api_usage(run_id,service,model,input_tokens,output_tokens,recorded_at) VALUES (?, 'llm', ?, ?, ?, ?)",
                                         (run_id, getattr(analyzer, "model", None), prompt_tokens, output_tokens, _now()))
                        conn.execute("UPDATE run_pages SET status='needs_review', error=? WHERE run_id=? AND url=?", (str(exc), run_id, url))
                        conn.execute("""INSERT INTO pages(url,status,error) VALUES (?, 'needs_review', ?)
                          ON CONFLICT(url) DO UPDATE SET status='needs_review', relevance=NULL, brands_json=NULL,
                          contact=NULL, evidence_json=NULL, error=excluded.error""", (url, str(exc)))
            if len(unique_urls) > max_pages: errors.append(f"{len(unique_urls)-max_pages} pages not analyzed due to page limit")
            status = "partial" if errors else "complete"
        except BaseException as exc:
            errors.append(f"Run interrupted: {type(exc).__name__}")
            raise
        finally:
            with conn:
                conn.execute("UPDATE runs SET finished_at=?, status=?, error=? WHERE id=?",
                             (_now(), status, json.dumps(errors, ensure_ascii=False), run_id))
        return {"run_id": run_id, "status": status, "keywords_complete": complete_keywords, "errors": errors}
