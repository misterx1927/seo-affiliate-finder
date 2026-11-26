"""Guarded live runner. Default is a free configuration check; no network calls."""
import argparse
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from src.budget import PersistentAllowance
from src.config import load_env
from src.database import connect
from src.exporter import export_observations, export_partial_observations
from src.fetcher import fetch_with_retry
from src.keywords import KEYWORDS
from src.live_pipeline import run_live
from src.providers import DataForSEO, OpenAIAnalyzer

def positive_money(value: str) -> str:
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -6:
            raise ValueError
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError("Enter a positive USD amount with at most 6 decimals") from exc
    return value

def main():
    parser = argparse.ArgumentParser(description="One-key pilot: dry-run unless --allow-paid is explicitly passed")
    parser.add_argument("--allow-paid", action="store_true", help="Explicitly authorize paid API requests")
    parser.add_argument("--mode", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--confirm-full", action="store_true", help="Additional explicit authorization for full run")
    parser.add_argument("--budget", type=positive_money, default="0.10", help="Estimated maximum USD")
    parser.add_argument("--serp-reserve", type=positive_money, default=None, help="Conservative USD reservation per SERP request")
    parser.add_argument("--llm-reserve", type=positive_money, default=None, help="Conservative USD reservation per LLM request")
    parser.add_argument("--pages", type=int, default=None, help="Maximum pages to analyze")
    parser.add_argument("--depth", type=int, choices=(10,20), default=20, help="DataForSEO search depth")
    parser.add_argument("--verify-serp", action="store_true", help="Opt in to provider verification; corrected results may come from Google Web and cost extra")
    parser.add_argument("--resume", type=int, default=None, help="Resume a previous incomplete run")
    args = parser.parse_args()
    pages = args.pages if args.pages is not None else (2 if args.mode == "pilot" else 100)
    max_pages = 3 if args.mode == "pilot" else 100
    if not 1 <= pages <= max_pages:
        parser.error(f"Page limit must be between 1 and {max_pages} for {args.mode} mode")
    keywords = list(KEYWORDS[:1] if args.mode == "pilot" else KEYWORDS)
    print(f"{args.mode.title()}: {len(keywords)} keyword(s), depth {args.depth}, up to {pages} pages; estimated budget ${args.budget}.")
    if args.verify_serp:
        print("SERP verification enabled: restored results may come from Google Web mode and incur an extra charge.")
    print("Account-level spending controls are still required; estimates cannot guarantee actual charges.")
    if not args.allow_paid:
        print("DRY RUN: no API calls. Live requests require explicit --allow-paid and configured credentials and reservations.")
        return
    if args.mode == "full" and not args.confirm_full:
        parser.error("Full mode requires --confirm-full. No API call was made.")
    try:
        load_env()
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot read .env configuration: {exc}. No API call was made.")
    login, password = os.getenv("DATAFORSEO_LOGIN"), os.getenv("DATAFORSEO_PASSWORD")
    api_key, model = os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")
    if not all((login, password, api_key, model, args.serp_reserve, args.llm_reserve)):
        parser.error("Paid pilot requires credentials, model, --serp-reserve and --llm-reserve. No API call was made.")
    minimum_serp = (Decimal('0.004') if args.depth == 20 else Decimal('0.002')) + (Decimal('0.002') if args.verify_serp else Decimal('0'))
    if Decimal(args.serp_reserve) < minimum_serp:
        parser.error(f"SERP reservation must be at least ${minimum_serp} for the chosen depth. No API call was made.")
    if Decimal(args.serp_reserve) + Decimal(args.llm_reserve) > Decimal(args.budget):
        parser.error("Budget must cover at least one search and one analysis. No API call was made.")
    with connect("data/live.db") as conn:
        def factory(run_id):
            allowance = PersistentAllowance(conn, run_id, approved=True, max_serp=len(keywords), max_llm=pages,
                budget_usd=args.budget, serp_reservation_usd=args.serp_reserve, llm_reservation_usd=args.llm_reserve)
            return DataForSEO(login, password, allowance, depth=args.depth, verify_serp=args.verify_serp), OpenAIAnalyzer(api_key, model, allowance)
        result = run_live(conn, datetime.now(timezone.utc).date().isoformat(), keywords, None, None,
                          fetch_with_retry, "data/live.lock", pages, args.resume, factory,
                          progress=lambda message: print(message, flush=True))
        count = export_observations(conn, "exports/live-results.csv")
        partial_count = export_partial_observations(conn, "exports/partial-results.csv")
        usage = conn.execute("""SELECT COALESCE(SUM(cost_usd), 0) AS serp_cost,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    SUM(CASE WHEN service='serp' AND cost_usd IS NULL THEN 1 ELSE 0 END) AS unreported_costs
                    FROM api_usage WHERE run_id=?""", (result["run_id"],)).fetchone()
        reserved = conn.execute("SELECT COALESCE(SUM(estimated_microusd), 0) AS total FROM request_reservations WHERE run_id=?", (result["run_id"],)).fetchone()["total"]
    print(f"Run {result['run_id']}: {result['status']}; {count} complete rows exported to exports/live-results.csv; {partial_count} incomplete rows exported to exports/partial-results.csv")
    print(f"Estimated reservation ${reserved / 1_000_000:.6f}; SERP costs reported by provider ${usage['serp_cost']:.6f}; "
          f"SERP responses without a cost: {usage['unreported_costs'] or 0}; "
          f"reported LLM tokens: {usage['input_tokens']} input / {usage['output_tokens']} output. "
          "Actual billing may differ, especially on errors; consult provider accounts.")
    for error in result["errors"]: print(error)
    if result["status"] != "complete": raise SystemExit(1)

if __name__ == "__main__": main()
