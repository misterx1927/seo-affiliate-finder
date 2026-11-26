"""AI pilot for cached pages. Defaults to a dry run with no network calls."""
import argparse
import os
from src.budget import PersistentAllowance
from src.cached_pilot import select_cached, run_cached_pilot
from src.config import load_env
from src.database import connect
from src.exporter import export_partial_observations
from src.providers import OpenAIAnalyzer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-run', type=int, default=2)
    parser.add_argument('--pages', type=int, choices=(1,2), default=2)
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    with connect('data/live.db') as conn:
        rows = select_cached(conn, args.search_run, args.pages)
        print(f"Cached pages available for pilot: {len(rows)} (maximum {args.pages}). No Google search will be performed.")
        if not args.allow_paid:
            print('DRY RUN: no API request. Estimated reservation: $0.005 per page, at most $0.01 total; actual cost may differ.')
            return
        load_env()
        api_key, model = os.getenv('OPENAI_API_KEY'), os.getenv('OPENAI_MODEL')
        if not api_key or not model: parser.error('OpenAI API key and model are required; no request sent')
        def factory(run_id):
            allowance = PersistentAllowance(conn,run_id,approved=True,max_serp=0,max_llm=args.pages,
                  budget_usd='0.01',serp_reservation_usd='0.002',llm_reservation_usd='0.005')
            return OpenAIAnalyzer(api_key,model,allowance)
        result = run_cached_pilot(conn,args.search_run,args.pages,factory,'data/live.lock')
        export_partial_observations(conn,'exports/real-pilot-run-2.csv',args.search_run)
        tokens = conn.execute("SELECT sum(input_tokens),sum(output_tokens) FROM api_usage WHERE run_id=? AND service='llm'",(result['run_id'],)).fetchone()
    print(f"Analysis run {result['run_id']}: {result['completed']}/{result['attempted']} pages completed, status {result['status']}.")
    print(f"Reported tokens: input={tokens[0]}, output={tokens[1]}. Verify actual billing in OpenAI Platform.")
    for error in result['errors']: print(error)
    if result['status'] != 'complete': raise SystemExit(1)

if __name__ == '__main__': main()
