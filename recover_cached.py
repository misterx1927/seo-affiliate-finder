"""Analyze previously saved pages without fetching Google or the pages again.

Dry-run by default. Never retries an ambiguous paid request automatically.
"""
import argparse
import os
from decimal import Decimal

from src.budget import PersistentAllowance
from src.cached_pilot import run_cached_pilot, select_cached
from src.config import load_env
from src.database import connect
from src.exporter import export_observations
from src.providers import OpenAIAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Recover cached page analyses without new searches")
    parser.add_argument('--search-run', type=int, required=True)
    parser.add_argument('--pages', type=int, choices=range(1, 9), required=True)
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    with connect('data/live.db') as conn:
        rows = select_cached(conn, args.search_run, args.pages, max_allowed=8)
        estimate = Decimal('0.005') * len(rows)
        print(f"{len(rows)} cached pages; estimated reservation ${estimate:.3f}; no Google requests or page downloads.")
        print("Reservations are estimates, not a provider-enforced limit; no automatic paid retries.")
        if not args.allow_paid:
            print('DRY RUN: no paid API requests.')
            return
        if not rows:
            print('No eligible pages; no API request made.')
            return
        load_env()
        api_key, model = os.getenv('OPENAI_API_KEY'), os.getenv('OPENAI_MODEL')
        if not api_key or not model:
            parser.error('OpenAI API key and model are required; no request sent')
        def factory(run_id):
            allowance = PersistentAllowance(conn, run_id, approved=True, max_serp=0, max_llm=len(rows),
                budget_usd=str(estimate), serp_reservation_usd='0.002', llm_reservation_usd='0.005')
            return OpenAIAnalyzer(api_key, model, allowance)
        result = run_cached_pilot(conn, args.search_run, len(rows), factory, 'data/live.lock', max_allowed=8)
        path = f'exports/run-{args.search_run}-recovered.csv'
        count = export_observations(conn, path, args.search_run)
        usage = conn.execute("SELECT SUM(input_tokens), SUM(output_tokens) FROM api_usage WHERE run_id=? AND service='llm'", (result['run_id'],)).fetchone()
        print(f"Recovery run {result['run_id']}: {result['completed']}/{result['attempted']} accepted, status {result['status']}.")
        print(f"Reported tokens: {usage[0]} input, {usage[1]} output. Updated snapshot: {path} ({count} rows).")
        for error in result['errors']:
            print(error)
        if result['status'] != 'complete':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
