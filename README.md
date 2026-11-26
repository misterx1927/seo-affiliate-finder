# SEO Affiliate Finder

Find potential casino affiliate placements in Google Canada’s English mobile results. The prototype records rankings for ten preset queries, analyzes unique pages with an LLM for relevance, casino brands and contacts, and provides a local review dashboard.

## Quick start (Windows, Python 3.11+)

In PowerShell from the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py
```

Open the displayed URL, select **Демо**, and click **Обновить демо**. The demo uses fictional data and makes no paid calls. The dashboard also displays locally collected live results, filters, CSV/Excel exports and pages needing review. A fresh checkout has no live database: see the included [recorded results](results/) instead. This setup was tested on Windows with Python 3.13 in an isolated copy without credentials or databases.

## Collect real data

Create a local configuration with `Copy-Item .env.example .env`, then fill in your DataForSEO login/password and OpenAI API key; choose a model available to your account. Do not share `.env`. Both services charge separately. Check current pricing and set provider spending controls.

```powershell
# Preview only: no API calls; this does not validate credentials.
.\.venv\Scripts\python pilot.py --mode full
# Paid collection: ten searches and up to 100 page analyses.
.\.venv\Scripts\python pilot.py --mode full --depth 20 --pages 100 --budget 0.60 --serp-reserve 0.004 --llm-reserve 0.005 --allow-paid --confirm-full
```

Results go to `data/live.db` and `exports/`. Complete and incomplete searches are kept separately. A completed keyword/day snapshot replaces that day’s positions without duplicates; earlier days remain in SQLite. Run the command with an external scheduler for daily collection: no scheduler is installed. Paid requests are not automatically retried. Budget reservations are estimates, **not a provider-enforced spending limit**.

Optionally add `--verify-serp` to detect and replace potentially poisoned results using Google Web mode. At depth 20, increase `--serp-reserve` to at least `0.006` and adjust the budget. Replacement provenance is recorded; restored ranks may differ from the original mobile page, and lack of a restoration flag does not prove verification succeeded.

## Recorded results and cost

The [reviewed 25 November run](results/run-7-reviewed.csv) contains 100 positions for ten queries, including 87 flagged as restored from Google Web. Among 69 unique URLs, 35 have accepted AI analyses (seven uncertain), 21 have separately identified supplementary reviews, and 13 have no accepted analysis or supplementary review. Supplementary reviews are partial checks of indexed content, not AI outputs. The snapshot includes documented manual corrections and is not a pristine model output. Public email candidates are separate from AI contacts and are not verified partnership addresses. See [results notes](results/README.md), [recovery review](RECOVERY_REVIEW.md), and the [random-sample review](RUN7_RANDOM_EVALUATION.md).

The original run’s reported search charges were **$0.046**; its reported 106,981 input and 2,704 output tokens cost approximately **$0.0121**, or **$0.0581** combined at the then-listed [model prices](https://developers.openai.com/api/docs/models/gpt-6-luna). Recovery and diagnostics cost extra, and unreported charges are excluded. Check [current search pricing](https://dataforseo.com/pricing/google-serp/google-organic-serp-api) and provider billing.

## Choices and limitations

DataForSEO supplies device/location-specific SERPs; SQLite makes local history easy to reproduce; structured OpenAI responses provide page labels. Claims are checked against extracted text, and blocked or unsupported pages are flagged. Static HTML extraction does not render JavaScript; the separate optional contact-discovery tool checks linked same-origin pages but does not verify partnership suitability. More work: improve access to protected pages, evaluate all brands and contacts, add scheduling and validate the full flow over multiple days. No public hosting is included. A short narrated demonstration using screenshots of the application is available in [affiliate-finder-demo.mp4](affiliate-finder-demo.mp4).

Run checks with `.\.venv\Scripts\python -m unittest discover -s tests -v` and `.\.venv\Scripts\python tests/ui_smoke.py`. Verify the provided snapshot with `py verify_results.py results/run-7-reviewed.csv`. See [development notes](DEVELOPMENT.md) and [quality review](QUALITY_REVIEW.md).
