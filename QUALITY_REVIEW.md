# Live run 5: preliminary quality review

Run date: 2026-11-25. This is a review of relevance signals on 20 cached pages, not a full evaluation of every brand and contact. Ordering is by URL, not random sampling.

For each page below, the recorded model label was compared with the visible cached title or supporting quotation. "Plausible" means the page appears to match the requested page category; it does not establish that the owner accepts placements. Brands and contacts require a separate audit.

| URL or domain/path | Label | Relevance review |
| --- | --- | --- |
| `apps.apple.com/.../playojo-canada-online-casino/...` | no | Plausible: casino app listing. |
| `blog.rocketplay.com/` | no | Uncertain: casino comparison on a site promoting Rocketplay registration; check independence. |
| `calgaryherald.com/.../top-online-gambling-sites-best-online-casinos-for-canadians` | no | Potential false negative: sponsored casino ranking; publisher's placement terms unknown. |
| `canadacasinoonline.org/real-money/` | yes | Plausible: ranked casinos with reviews. |
| `gamblizard.ca/free-spins/bonus-codes-free-spins/` | yes | Plausible: casino bonus ranking. |
| `interaccasinoguide.ca/live-casino/` | yes | Plausible: page describes an independent publisher. |
| `nodepositbonusca.com/10-dollar-no-deposit/` | yes | Plausible: list of casinos and bonuses. |
| `nodepositbonuses.top/canada-no-deposit-bonuses/` | yes | Plausible: Canadian casino bonus comparison. |
| `nostrabet.com/ca/online-casinos-canada/` | yes | Plausible: recommended casinos. |
| `socioscasino.com/en-ca/free-spins/free-spins-no-deposit/` | yes | Plausible: free-spins offer ranking. |
| `vancouversun.com/.../best-instant-withdrawal-casinos-canada...` | yes | Plausible: sponsored casino ranking; placement terms unknown. |
| `wizardofodds.com/online-casinos/best-for-players-from-canada` | yes | Plausible: recommendations for players. |
| `www.bonus.ca/free-spins-no-deposit/120-free-spins` | yes | Plausible: casino offer comparison. |
| `www.bonus.ca/free-spins-no-deposit/50-free-spins` | yes | Plausible: casino offer comparison. |
| `www.canadacasino.ca/bonuses/no-deposit` | yes | Plausible: casino bonus comparison. |
| `www.canadiangamblingchoice.com/best-casino-online-in-canada/` | yes | Plausible: casino guide. |
| `www.online-casinos.ca/.../150-free-chips.html` | yes | Plausible: independent casino information site. |
| `www.online-casinos.ca/.../50-free-chips.html` | yes | Plausible: independent casino information site. |
| `www.promoguy.us/ca/casino/free-spins/` | yes | Plausible: casino reviews. |
| `www.slotfruit.ca/payment-method/interac/` | yes | Plausible: independent guide to casinos. |

| Page | Stored result | Preliminary assessment |
| --- | --- | --- |
| `apps.apple.com/ca/app/playojo-canada-online-casino/id1202888212` | Not relevant | Plausible: this is an app listing for a casino operator, not an independent review or ranking site. |
| `blog.rocketplay.com/` | Not relevant | Plausible but uncertain: the cached text contains a casino comparison, while the page also promotes Rocketplay registration. Ownership and outreach suitability need manual verification. |
| `calgaryherald.com/sponsored/life-sponsored/top-online-gambling-sites-best-online-casinos-for-canadians` | Not relevant | Potential false negative: the cached text describes a sponsored casino ranking. Whether the publisher accepts affiliate placements needs human review; a sponsored article alone does not establish availability. |
| `gamblizard.ca/free-spins/bonus-codes-free-spins/` and `www.canadacasino.ca/bonuses/no-deposit` | Relevant, contact `[email protected]` | The contact is a protection placeholder, not an address. It has been removed from the database and regenerated CSV exports. Relevance and brands have not been independently verified. |

The provider returned fewer than ten organic results for eight keywords at depth 20. A later, separate diagnostic request for `online casino canada` at depth 40 returned six organic results, two `people_also_search` elements and one `people_also_ask` element. DataForSEO reported $0.002. Another diagnostic with `resolve_poisoned_results` enabled returned ten organic results, all marked `from_web`, at a reported cost of $0.004. According to DataForSEO, that flag means the provider replaced affected listings with Google Web mode results; they are not guaranteed to be identical to the original mobile SERP. This was one query at a different time, so it does not establish full coverage for the ten-query set. Future requests retain item-type counts, organic ranks and restored ranks, but not full raw responses.

A spot check of the first reported brand on 20 pages found that `Gamblizard`, the review publisher, had been listed as a casino brand on its own page. That one item was removed from the saved record, and the model instruction now explicitly distinguishes publishers from casino operators. The updated instruction has not yet been evaluated against a new set of model responses. The other names were found in the page text; this is not a full verification of all names or proof that each represents a casino operator. The two unusable `[email protected]` contacts were removed separately. Actual contact ownership and outreach suitability remain unverified.

Next: evaluate a representative 20 unique pages against their cached content and, where accessible, the original pages; record relevance, brands and contact separately. Check failures and protected pages separately rather than assuming they are irrelevant.

## Follow-up: contacts and duplicate names

All three non-null contacts among the 22 saved analyses were checked against the cached page text:

| Page | Contact found | Context and limit |
| --- | --- | --- |
| `nostrabet.com/ca/online-casinos-canada/` | `support@nostrabet.com` | Listed in the site's footer as an email address. It is general support; suitability for partnership outreach is unverified. |
| `yummyspins.com/ca/best-interac-casinos-in-canada/` | `partners@yummyspins.com` | Listed in the footer under “Partnership”. Current deliverability and placement terms are unverified. |
| `apps.apple.com/ca/app/playojo-canada-online-casino/id1202888212` | `Support@playojo.com` | Appears in a developer response to a customer review and is an operator support contact. The app listing was classified as not relevant for outreach. |

One saved result, `www.bonus.ca/free-spins-no-deposit/120-free-spins`, lists both `PartyCasino` and `partycasino`. The validator now removes names that differ only by case or whitespace in new analyses, preserving the first spelling. The existing saved row and exports have not been changed. Other aliases, such as names with and without “Casino”, are not automatically merged because the names may refer to different entities.

These checks establish that the strings occur in the saved text; they do not establish that contacts are live or that every reported brand is a casino operator. Checking one brand per page is not a full brand audit, and this is not a random sample.
