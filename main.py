"""Run the completely offline demo and export its fictional results."""
import argparse
from datetime import date
from src.database import connect
from src.exporter import export_observations
from src.pipeline import run_offline

def main() -> None:
    parser = argparse.ArgumentParser(description="SEO Affiliate Finder: offline fixture run")
    parser.add_argument("--db", default="data/demo.db")
    parser.add_argument("--export", default="exports/offline-demo.csv")
    args = parser.parse_args()
    with connect(args.db) as conn:
        result = run_offline(conn, date.today().isoformat())
        exported = export_observations(conn, args.export)
    print(f"OFFLINE DEMO (fictional data): {result['status']}; {result['observations']} observations; "
          f"{result['analyzed']} analyzed, {result['reused']} reused; {exported} rows exported to {args.export}.")
    for error in result["errors"]:
        print(f"Needs review: {error}")
    if result["status"] != "complete":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
