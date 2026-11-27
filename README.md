# SEO Affiliate Finder

Find potential casino affiliate placements in Google Canada’s English mobile results. The prototype records rankings for ten preset queries, analyzes unique pages with an LLM for relevance, casino brands and contacts, and provides a local review dashboard.

## Review materials

- [Demonstration in English](affiliate-finder-demo-en.mp4) and [in Russian](affiliate-finder-demo.mp4). On GitHub, select **View raw** to play or download.
- [Recorded results](results/run-7-ai-updated.csv) for the included dashboard view.
- [Latest run summary, 27 November](results/RUN_2026-11-27.md) and [20-page sample review](results/INDEPENDENT_SAMPLE_20.md).

## Quick start (Windows, Python 3.11+)

In PowerShell from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Open the displayed URL. When locally collected results are available, the dashboard defaults to **Реальные результаты**. Otherwise, it shows **Сохранённый прогон**, the included [recorded results](results/run-7-ai-updated.csv), without API keys or paid calls. Select **Демо** and click **Обновить демо** for fictional data. The dashboard includes filters, CSV/Excel exports and pages needing review. This setup was tested on Windows with Python 3.13 in an isolated copy without credentials or databases.

The dashboard groups the filtered results by domain and displays the best position and its page and query. Other matching pages and positions remain available in the details panel. A potentially relevant page without an identified contact or contact page is marked for review; this is a dashboard rule and does not alter the stored AI assessment. Dashboard downloads contain this grouped view, not the complete search history. The recorded CSV remains ungrouped.

## Collect real data

Create a local configuration with `Copy-Item .env.example .env`, then fill in your DataForSEO login/password and OpenAI API key; choose a model available to your account. Do not share `.env`. Both services charge separately. Check current pricing and set provider spending controls.

```powershell
# Preview only: no API calls; this does not validate credentials.
.\.venv\Scripts\python pilot.py --mode full
# Paid collection: ten searches and up to 100 page analyses.
.\.venv\Scripts\python pilot.py --mode full --depth 20 --pages 100 --budget 0.60 --serp-reserve 0.004 --llm-reserve 0.005 --allow-paid --confirm-full
```

Results go to `data/live.db` and `exports/`. Complete and incomplete searches are kept separately. A completed keyword/day snapshot replaces that day’s positions without duplicates; earlier days remain in SQLite, but an earlier complete run for the same query and day is replaced. New live runs preserve a per-run snapshot of each processed page analysis, including cached results and failures. The dashboard and exports use that run's analysis when available; pages not analyzed in a tracked run are marked pending instead of borrowing a later result. Older runs predate this tracking and use the latest stored page analysis, not a reconstructed historical assessment. Public contact candidates may also be newer than the run. Paid requests are not automatically retried. Budget reservations are estimates, **not a provider-enforced spending limit**.

For an optional Windows daily schedule, first configure `.venv` and `.env` as above. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\daily_run.ps1 -DryRun` to validate the command without API calls. `powershell -NoProfile -ExecutionPolicy Bypass -File .\install_daily.ps1 -Time 09:00 -Preview` previews the schedule, while omitting `-Preview` registers a daily **paid** task at the chosen local time. It runs for the current user, logs to `logs/`, and needs the machine and user session to be available. Remove it with `Unregister-ScheduledTask -TaskName 'SEO Affiliate Finder - daily'`. No task is installed automatically. The per-run estimate is $0.60 and is not a hard provider spending limit. Existing tasks with that name are never overwritten.

Optionally add `--verify-serp` to detect and replace potentially poisoned results using Google Web mode. At depth 20, increase `--serp-reserve` to at least `0.006` and adjust the budget. Replacement provenance is recorded; restored ranks may differ from the original mobile page, and lack of a restoration flag does not prove verification succeeded.

## Recorded results and cost

The [reviewed 25 November run](results/run-7-reviewed.csv) contains 100 positions for ten queries, including 87 flagged as restored from Google Web. The dashboard uses a separate [updated snapshot](results/run-7-ai-updated.csv): 36 of 69 unique URLs have accepted AI analyses, including [one later analysis](results/AI_UPDATE_2026-11-26.md) based on truncated provider text. Additional indexed-page reviews and public contacts appear in the dashboard and are documented [here](results/COVERAGE_RECHECK.md); they do not change the historical CSV. Supplementary reviews are partial checks, not AI outputs, and do not carry over to new collection dates. The snapshot includes documented manual corrections and is not a pristine model output. For example, three brands visible in an indexed Slotozilla page were added manually to an empty AI result and marked in the row. Public email candidates are separate from AI contacts and require verification. See the [20-URL sample audit](results/INDEPENDENT_SAMPLE_20.md) for evidence and limitations.

The original run’s reported search charges were **$0.046**; its reported 106,981 input and 2,704 output tokens cost approximately **$0.0121**, or **$0.0581** combined at the then-listed [model prices](https://developers.openai.com/api/docs/models/gpt-6-luna). Recovery and diagnostics cost extra, and unreported charges are excluded. Check [current search pricing](https://dataforseo.com/pricing/google-serp/google-organic-serp-api) and provider billing.

An exploratory [SerpApi comparison](results/SERPAPI_COMPARISON_2026-11-26.md) covers all ten keywords: eight complete provider-to-provider comparisons and two partial ones. The providers differed substantially, and neither result is ground truth. A [closer review](results/SERP_DISCREPANCY_REVIEW_2026-11-26.md) examines three queries and two incomplete repeat searches. A separate [diagnostic](results/SERP_COMPARISON.md) includes a direct desktop Google check, which does not verify Canadian mobile rankings.

## Choices and limitations

DataForSEO supplies device/location-specific SERPs; SQLite makes local history easy to reproduce; structured OpenAI responses provide page labels. Claims are checked against extracted text, and blocked or unsupported pages are flagged. Static HTML extraction does not render JavaScript; the separate optional contact-discovery tool checks linked same-origin pages but does not verify partnership suitability. More work: improve access to protected pages, evaluate all brands and contacts, and validate the full flow over multiple days. No public hosting is included. Short narrated demonstrations made from screenshots are available in [English](affiliate-finder-demo-en.mp4) and [Russian](affiliate-finder-demo.mp4).

Run checks with `.\.venv\Scripts\python -m unittest discover -s tests -v` and `.\.venv\Scripts\python tests/ui_smoke.py`. Verify the provided snapshot with `py verify_results.py results/run-7-reviewed.csv`. See [development notes](DEVELOPMENT.md) and [quality review](QUALITY_REVIEW.md).
