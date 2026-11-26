# SERP comparison (one keyword, exploratory)

Query: `online casino canada`. Recorded results use rank_group 1–10. Reference: `results/run-7-reviewed.csv`. Diagnostic source: DataForSEO; see local files named below.

Recorded vs 2026-11-25 diagnostic: 4/10 exact URLs shared.
Recorded vs 2026-11-26 diagnostic: 4/10 exact URLs shared.
2026-11-25 vs 2026-11-26 diagnostics: 9/10 exact URLs shared.

| Rank | Recorded | Diagnostic Nov 25 | Diagnostic Nov 26 |
|---:|---|---|---|
| 1 | https://ca.888casino.com/ | https://www.betmgm.ca/en/casino | https://www.betmgm.ca/en/casino |
| 2 | https://www.betvictor.com/en-ca/casino | https://www.powerplay.com/casino/ | https://www.powerplay.com/casino/ |
| 3 | https://www.olg.ca/en/online-casino.html | https://www.playojo.com/ca/ | https://ca.trustpilot.com/categories/casino |
| 4 | https://www.playojo.com/ca/ | https://ca.trustpilot.com/categories/casino | https://www.playojo.com/ca/ |
| 5 | https://www.powerplay.com/casino/ | https://www.livescore.com/en-ca/online-casinos/ | https://www.livescore.com/en-ca/online-casinos/ |
| 6 | https://ca.trustpilot.com/categories/casino | https://www.betsafe.com/ca/casino | https://www.betsafe.com/ca/casino |
| 7 | https://www.leovegas.com/en-ca | https://www.sportsinteraction.com/en-ca/games | https://www.sportsinteraction.com/en-ca/games |
| 8 | https://www.alc.ca/content/alc/en/play-online/casino.html | https://on.spingenie.ca/ | https://www.casino.org/canada/new/ |
| 9 | https://www.casino.ca/ | https://www.casino.org/canada/new/ | https://www.partycasino.com/en-ca/games |
| 10 | https://www.betmgm.ca/en/casino | https://www.partycasino.com/en-ca/games | https://www.wildz.com/ca/ |

Diagnostics were recorded locally; the summarized URLs and positions are listed above.
The Nov 25 diagnostic marked all ten results `from_web`; the Nov 26 diagnostic returned no such flags for these ten. Both are the same vendor, not independent verification. Requests were taken at different times/configurations; overlap measures consistency only, not accuracy, and does not verify mobile rankings. Google results may vary by time, location and experiment. The retrieved reference run was also substantially restored from Google Web.

Independent Google Canada mobile verification was not obtained: the available web search does not disclose a verifiable Google mobile Canada SERP, while direct automated Google fetch was unavailable in this environment. No live request or charges were made for this comparison.

## Direct browser Google check, 2026-11-26 12:43 UTC

A separate browser request to `https://www.google.ca/search?q=online+casino+canada&hl=en&gl=CA&pws=0` displayed the following ten organic entries, recorded in visual order. This check did not use DataForSEO. Site names/hosts are transcribed from Google search labels; direct destination URLs were not resolved.

| Rank | Domain shown by Google | Recorded rank for same domain |
|---:|---|---:|
| 1 | ca.888casino.com | 1 |
| 2 | www.betvictor.com | 2 |
| 3 | www.olg.ca | 3 |
| 4 | www.powerplay.com | 5 |
| 5 | www.casino.ca | 9 |
| 6 | www.leovegas.com | 7 |
| 7 | www.alc.ca | 8 |
| 8 | ca.trustpilot.com | 6 |
| 9 | www.betmgm.ca | 10 |
| 10 | www.playojo.com | 4 |

All ten domains overlapped with the recorded result; the first three ranks matched. This was a desktop browser, not an actual mobile device, with no verified Canadian IP location. `gl=CA` is a country hint, not proof of Canadian location or mobile results. The comparison covers one query at a different time, so it is not a 10-query accuracy test and does not establish that restored positions were correct. No paid request was made.


## Follow-up: interac casino, 26 November 2026

Run 20 returned two organic results for this query without recovery. A separate DataForSEO diagnostic using `group_organic_results=false` and `resolve_poisoned_results=true` returned 20 organic items; the first ten carried the provider flag `from_web`. The provider reported $0.006 for this diagnostic. This demonstrates increased completeness for this single request, not independently verified Canadian mobile positions. The recovered results were not substituted into the saved snapshot.

Compared with `results/run-7-ai-updated.csv` from 25 November, the first ten of that later diagnostic share 8 exact URLs, of which 2 occupy the same rank. All ten diagnostic positions are flagged `from_web`. This is an exploratory consistency comparison across different dates and request configurations, not a measurement of accuracy. The source diagnostic is stored locally as `exports/serp-diagnostics/20261126T141706641122Z.json`; the recorded snapshot was not changed. Both observations come from the same provider and cannot independently validate one another. A proper independent check requires a second source with verifiable Canadian location and mobile device settings, recorded at approximately the same time.
