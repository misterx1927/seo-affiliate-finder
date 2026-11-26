"""Run a small AI pilot against already downloaded pages; never issues SERP requests."""
from datetime import datetime, timezone
import hashlib
import json
from .parser import extract_text
from .run_lock import RunLock


def _now(): return datetime.now(timezone.utc).isoformat()


def select_cached(conn, search_run, limit, *, max_allowed=2):
    if type(max_allowed) is not int or not 1 <= max_allowed <= 8 or type(limit) is not int or not 1 <= limit <= max_allowed:
        raise ValueError("Invalid cached page limit")
    return conn.execute("""SELECT o.url, c.content, c.charset FROM (
        SELECT run_id, day, position, url FROM partial_observations
        UNION ALL
        SELECT run_id, day, position, url FROM observations
        ) o
        JOIN page_cache c ON c.url=o.url AND (c.day=o.day OR EXISTS (
            SELECT 1 FROM page_cache_provenance psource WHERE psource.url=c.url))
        LEFT JOIN pages p ON p.url=o.url
        WHERE o.run_id=? AND COALESCE(p.status, 'pending') != 'complete'
        AND NOT EXISTS (
            SELECT 1 FROM run_pages later_page JOIN runs later_run ON later_run.id=later_page.run_id
            WHERE later_page.url=o.url AND later_page.run_id>o.run_id
              AND later_run.mode='analysis_pilot' AND later_page.status!='complete')
        GROUP BY o.url ORDER BY MIN(o.position) LIMIT ?""", (search_run, limit)).fetchall()


def run_cached_pilot(conn, search_run, limit, analyzer_factory, lock_path, *, max_allowed=2):
    with RunLock(lock_path):
        rows = select_cached(conn, search_run, limit, max_allowed=max_allowed)
        if not rows:
            raise ValueError("No cached unanalyzed pages available")
        with conn:
            run_id = conn.execute("INSERT INTO runs(started_at,mode,status) VALUES (?, 'analysis_pilot', 'running')", (_now(),)).lastrowid
        errors, completed = [], 0
        status = 'failed'
        try:
            analyzer = analyzer_factory(run_id)
            for row in rows:
                url = row['url']
                with conn:
                    conn.execute("INSERT INTO run_pages(run_id,url,status) VALUES (?,?,'started')", (run_id,url))
                try:
                    text = extract_text(row['content'], row['charset'])
                    result, usage = analyzer.analyze(text)
                    if not isinstance(usage, dict): usage = {}
                    inp, out = usage.get('prompt_tokens'), usage.get('completion_tokens')
                    inp = inp if type(inp) is int and inp >= 0 else None
                    out = out if type(out) is int and out >= 0 else None
                    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
                    with conn:
                        conn.execute("""INSERT INTO pages(url,content_hash,analyzed_at,status,relevance,brands_json,contact,evidence_json,error,analysis_version)
                        VALUES (?, ?, ?, 'complete', ?, ?, ?, ?, NULL, ?) ON CONFLICT(url) DO UPDATE SET
                        content_hash=excluded.content_hash,analyzed_at=excluded.analyzed_at,status=excluded.status,
                        relevance=excluded.relevance,brands_json=excluded.brands_json,contact=excluded.contact,
                        evidence_json=excluded.evidence_json,error=NULL,analysis_version=excluded.analysis_version""", (url,digest,_now(),result.relevance,
                            json.dumps(result.brands,ensure_ascii=False),result.contact,json.dumps(result.evidence,ensure_ascii=False),getattr(analyzer,'cache_version','default-v1')))
                        conn.execute("UPDATE run_pages SET status='complete' WHERE run_id=? AND url=?", (run_id,url))
                        conn.execute("INSERT INTO api_usage(run_id,service,model,input_tokens,output_tokens,recorded_at) VALUES (?, 'llm', ?, ?, ?, ?)", (run_id,getattr(analyzer,'model',None),inp,out,_now()))
                    completed += 1
                except Exception as exc:
                    errors.append(f"{url}: {type(exc).__name__}: {exc}")
                    with conn:
                        failed_usage = getattr(exc, 'usage', {})
                        if isinstance(failed_usage, dict) and failed_usage:
                            inp, out = failed_usage.get('prompt_tokens'), failed_usage.get('completion_tokens')
                            inp = inp if type(inp) is int and inp >= 0 else None
                            out = out if type(out) is int and out >= 0 else None
                            conn.execute("INSERT INTO api_usage(run_id,service,model,input_tokens,output_tokens,recorded_at) VALUES (?, 'llm', ?, ?, ?, ?)", (run_id,getattr(analyzer,'model',None),inp,out,_now()))
                        conn.execute("UPDATE run_pages SET status='needs_review', error=? WHERE run_id=? AND url=?", (str(exc),run_id,url))
                        conn.execute("UPDATE pages SET status='needs_review',relevance=NULL,brands_json=NULL,contact=NULL,evidence_json=NULL,error=? WHERE url=?", (str(exc),url))
            status = 'partial' if errors else 'complete'
        except BaseException as exc:
            errors.append(f"Interrupted: {type(exc).__name__}")
            raise
        finally:
            with conn:
                conn.execute("UPDATE runs SET finished_at=?,status=?,error=? WHERE id=?", (_now(),status,json.dumps(errors,ensure_ascii=False),run_id))
        return {'run_id':run_id, 'status':status, 'attempted':len(rows), 'completed':completed, 'errors':errors}
