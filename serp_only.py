"""One-query SERP-only pilot; default mode is free and offline."""
import argparse
import os
from datetime import datetime, timezone
from src.budget import PersistentAllowance
from src.config import load_env
from src.database import connect
from src.exporter import export_observations, export_partial_observations
from src.keywords import KEYWORDS
from src.live_pipeline import run_live
from src.providers import DataForSEO

class NotUsedAnalyzer:
    def analyze(self, text):
        raise RuntimeError("AI analysis is disabled for this pilot")

def main():
    parser = argparse.ArgumentParser(description="One-query DataForSEO pilot; dry-run unless approved")
    parser.add_argument("--depth", type=int, choices=(10, 20, 40), default=20)
    parser.add_argument("--allow-paid", action="store_true", help="Authorize one paid DataForSEO request")
    args = parser.parse_args()
    reserved = {10: "0.002", 20: "0.004", 40: "0.008"}[args.depth]
    print(f"One search, Google Canada / mobile / English, depth {args.depth}; estimated reservation ${reserved} (not a provider billing cap).")
    if not args.allow_paid:
        print("DRY RUN: no network requests or charges. No OpenAI request.")
        return
    load_env()
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        parser.error("DataForSEO credentials are missing; no request sent")
    with connect("data/live.db") as conn:
        def factory(run_id):
            allowance = PersistentAllowance(conn, run_id, approved=True, max_serp=1, max_llm=0,
                budget_usd=reserved, serp_reservation_usd=reserved, llm_reservation_usd="0.001")
            return DataForSEO(login, password, allowance, depth=args.depth), NotUsedAnalyzer()
        result = run_live(conn, datetime.now(timezone.utc).date().isoformat(), [KEYWORDS[0]], None, None,
                          lambda url: (_ for _ in ()).throw(RuntimeError("Page fetching disabled")),
                          "data/live.lock", 0, provider_factory=factory)
        complete = conn.execute("SELECT count(*) FROM observations WHERE run_id=?", (result['run_id'],)).fetchone()[0]
        partial = conn.execute("SELECT count(*) FROM partial_observations WHERE run_id=?", (result['run_id'],)).fetchone()[0]
        usage = conn.execute("SELECT cost_usd FROM api_usage WHERE run_id=? AND service='serp'", (result['run_id'],)).fetchone()
        diagnostics = conn.execute("SELECT items_by_type,organic_ranks FROM serp_diagnostics WHERE run_id=? AND keyword=?", (result['run_id'], KEYWORDS[0])).fetchone()
        export_observations(conn, "exports/live-results.csv")
        export_partial_observations(conn, "exports/partial-results.csv")
    print(f"Run {result['run_id']}: {complete or partial} organic results saved; {'complete' if complete else 'incomplete'}.")
    print(f"Provider-reported cost: {usage['cost_usd'] if usage else 'unknown'} USD. No OpenAI request made.")
    if diagnostics:
        print(f"Element counts: {diagnostics['items_by_type']}; organic ranks returned: {diagnostics['organic_ranks']}")
    if not (complete or partial):
        for error in result['errors']: print(error)
        raise SystemExit(1)

if __name__ == "__main__": main()
