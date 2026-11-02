# P112 — Nasdaq-100 supplier cost, symbol and rights preflight (2026-11-02 KST)

**Result: supplier candidate identified, live provider integration still BLOCKED.** This is a public-page research snapshot, not an account test, purchase, written contract, data license, market-data download or legal opinion. Do not send outreach or key before separate owner approval. No SEC requests (P105 403 permanent STOP).

## Evidence-checked candidates

| Provider | Public quote (USD, monthly, billed monthly where stated) | Nasdaq-100 availability | Permissions and remaining proof |
| --- | --- | --- | --- |
| Massive Indices | Individual Basic $0, Starter $49, Advanced $99. Business Indices $2,500/month publicly listed; actual index/exchange licensing details require confirmation | Official Indices FAQ **explicitly lists NDX as covered by Basic**; platform attributes Nasdaq-100 to NasdaqGIDS. No account-level / exact endpoint response verified | Standard market-data terms personal, non-business only; third-party data/derived analytics, non-display research and any contest/judge/public presentation require separate written permissions. Paid individual tier is NOT a public-use grant. |
| Twelve Data | Basic $0 (8 API credits/min, 800/day), individual Grow $79; business Venture $499 month (indicative page) | General indices API public, but **actual NDX instrument symbol and Basic account entitlement not demonstrated** | Individual plans non-commercial/internal. Business rights, exchange/index add-ons, contest judges and derived display require separate provider confirmation. P110 dormant code assumes tentative NDX and cannot establish rights. |
| FRED | Free-to-view web series NASDAQ100 | Public daily close series, Nasdaq as copyright/source | Copyrighted; public/commercial reuse cannot be treated as free. Historical table availability does not grant a vendor API/display/derivative license. |
| Nasdaq GIDS | Contact sales; no verified public per-use quote | Nasdaq's index source, real-time/historical index feeds, direct/cloud/authorized vendors | License scope and cost for a contest and future research product must be negotiated/confirmed. |

Official source links (checked 2026-11-02 KST):
- https://massive.com/indices
- https://massive.com/pricing?product=indices
- https://massive.com/knowledge-base/article/where-does-massive-source-their-indices-data
- https://massive.com/legal/market-data-terms-of-service
- https://massive.com/knowledge-base/article/how-can-i-redistribute-massives-market-data
- https://massive.com/business-indices
- https://twelvedata.com/indices
- https://twelvedata.com/pricing
- https://twelvedata.com/pricing-business
- https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage
- https://fred.stlouisfed.org/series/NASDAQ100
- https://www.nasdaq.com/products/global-indexes/data/gids

**Important:** The $0 plans do not make a usable/redistributable KUODRA investor-research feed. Massive free NDX *catalog inclusion* is verified only as an official vendor claim, not account authentication, exact `I:NDX` response, rights to share market values/derivatives, or price+NVDA bundled rights. Budget for full NVDA+NDX + public judge demo remains **unknown**; monthly published prices exclude possible extra contracts/fees. No product's usage may be activated based on this document.

## Designs and selected approach

A. Switch the P110 Twelve Data client straight to Massive Basic and fetch NDX under guessed free rights: seemingly $0 and easy code but violates the consent/derived-publication boundary and leaves individual NVDA share-price vendor contract unsolved. **Rejected.**

B. Keep all provider transport inert, preserve P110/P111 source contract and install an independent read-only `proofinvest.provider_rights_preflight` audit for Massive, Twelve Data, FRED and Nasdaq GIDS. This yields structured, **BLOCKED** receipts for internal research, judge demos, public dashboards and commercial release, without HTTP or plan purchase. **Selected**, low cost and safe to revert.

Run locally: `python -m proofinvest.provider_rights_preflight --provider massive --use contest_judge_demo`. **Exit 2 is intentional denial** and reports no authorized provider use. Focused tests: `python -m unittest tests.test_provider_rights_preflight -v` (6 tests). Existing P110 planner remains dormant and unmodified; the preflight is not an automatically integrated live ingestion gate. This does not produce authentic NDX candles.

## Owner-dependent decision (not executed)

Get written vendor replies for (1) exact Nasdaq-100 **index** identity and endpoint/Basic coverage, (2) NVDA stock plus index history usage within one app, (3) non-display Engine A calculations and derived-score storage, (4) exact KIC judge screen-share/video and DAKER PDF permissions, (5) public site/demo/commercial rights, (6) cache/retention/distribution and display attribution, (7) contract fees, cap and applicable exchange pass-through. Contact/purchase/account/GET only after explicit owner approval. For a non-licensed submission use synthetic fixture visuals labeled SYNTHETIC, not copied actual vendor price series.

DAKER 10-page V13 PDF original must not change. Owner's final authorized DAKER upload and receipt before **2026-11-12 10:00 KST** remains top priority.
