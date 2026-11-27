# Fresh SERP retry - 27 November 2026

This is a new diagnostic, not a reconstruction or replacement of the morning run. At 20:19-20:20 Kyiv time (18:19-18:20 UTC), SerpApi was queried for the six keywords with incomplete DataForSEO responses in the morning run, with Google.ca, Canada, English, mobile and provider cache disabled. [Sanitized results and timestamps](serp-retry-2026-11-27.json) include the actual URLs and ranks.

| Query | Organic results returned |
| --- | ---: |
| real money online casino canada | 1 |
| top 10 online casinos canada | 10 |
| interac casino | 1 |
| fast payout casino canada | 10 |
| online casino ontario | 9 |
| best online casino canada | 10 |

Each of the three complete responses has ranks 1-10 and ten distinct URLs. Completeness does not establish correctness, location precision, or suitability for advertising. The `top 10` response includes YouTube at rank 9, and the `best` response includes Trustpilot at rank 3 and casino operators. These may appear in a search response but are not necessarily target placements. Raw search positions must not be renumbered after filtering.

A separate DataForSEO mobile Android query for `real money online casino canada`, using depth 20 and poisoned-result recovery, returned nine organic results and reported a cost of $0.006. It was a new request, not a completion of the previous run. Six SerpApi searches were made, their actual billing should be checked in the provider account. The diagnostic tests do not prove which provider matches Google ground truth. Previously stored results were not modified.

Two additional fresh DataForSEO requests at approximately 20:22 Kyiv time returned ten organic results each for `top 10 online casinos canada` and `fast payout casino canada`, at $0.004 each. Compared with the earlier SerpApi responses, exact URL overlap was 10/10 and 8/10, and exact rank overlap 10/10 and 3/10 respectively. All twenty DataForSEO results were flagged `from_web`, so the identical `top 10` result does not constitute independent confirmation of an original mobile SERP. The three DataForSEO requests reported $0.014 in total. Their sanitized URLs, ranks, flags, and reported costs are included in the JSON file.

## Additional retrieval test

Two new DataForSEO diagnostics finished at 20:36 and 20:38 Kyiv time. Both used Canada, English, mobile, depth 20, poisoned-result recovery and `group_organic_results=false`. For `interac casino`, the provider returned 20 organic results, including ranks 1–10 with ten distinct URLs. For `real money online casino canada`, it returned ten results with ranks 1–10 and ten distinct URLs. All twenty top-ten results were flagged `from_web`, and neither set contained unresolved Google redirects. The second result set includes YouTube and two distinct pages from one casino operator, so completeness is not the same as suitable outreach candidates.

The provider reported $0.006 and $0.004 respectively, or $0.010 in total. Their top-ten URLs and flags are included in the [sanitized data](serp-retry-2026-11-27.json). These are fresh provider responses, not a reconstruction of the morning run or proof of the mobile ranking. A prior diagnostic had also recovered ten `interac casino` results with these settings, but this small sample cannot establish a general success rate. No historical data was changed.
