# Review of SERP discrepancies, 26 November 2026

This review examines the previously recorded provider responses, not the saved 25 November results or direct ground truth from Google. Both providers were requested with Canada, English and mobile settings. Provider methods, geography and request time may differ. Domain comparison below removes only a leading `www.` and does not merge other subdomains.

| Query | SerpApi position 1 | DataForSEO position 1 | Shared exact URLs | Shared hostnames |
| --- | --- | --- | ---: | ---: |
| online casino canada | ca.888casino.com | ca.888casino.com | 10/10 | 10/10 |
| new online casinos canada | casino.guru | covers.com | 0/10 | 1/10 |
| interac casino | thelines.com | livescore.com | 0/10 | 0/10 |

For `online casino canada`, five exact URLs also occupy the same rank. For `interac casino`, all ten DataForSEO results carried the provider's `from_web` flag. For `new online casinos canada`, five did. Those observations alone do not establish that the flag caused a discrepancy or that either provider is correct. DataForSEO included a YouTube watch URL at rank 2 for the latter query. The complete lists and their timestamps are in [the comparison data](serpapi-comparison-2026-11-26.json).

Two additional SerpApi requests were made for `interac casino` at approximately 19:33 UTC. Neither supplied ten unique ranks. The second returned just two organic URLs, `theklcinc.com/2024/08/12/best-casino-sites-that-accept-interac/` and `interaccasinoguide.ca/live-casino/`. No corresponding DataForSEO request was sent, so this is not a new paired comparison. A provider result containing a URL does not verify its relevance or reliability. The first incomplete response was not saved by the earlier diagnostic implementation. The diagnostic now saves partial responses without making the second provider request.

The two repeat attempts used two SerpApi searches and incurred no DataForSEO request. Check the SerpApi account for actual billing. Further comparison needs a complete paired sample and, to assess accuracy, an independently observed mobile Google result captured at a comparable time and location.
