# P111 — Twelve Data source entitlement and fail-closed first-response preflight
**2026-11-02 KST — source review; no new live provider HTTP or paid entitlement.**

## Verified official facts
- Twelve Data developer documentation allows HTTP `Authorization: apikey YOUR_KEY` (safer than exposing secrets in query). Source: https://twelvedata.com/docs/markets/market-state
- Official historical-series docs say `start_date` and `end_date` together bound an interval, and omit `outputsize` to avoid truncation. https://support.twelvedata.com/en/articles/5214728-getting-historical-data
- Terms 2.1–2.4 disallow free-tier commercial data use and require separately authorized external display/redistribution. Combining sources into competing products may also require prior consent. https://twelvedata.com/terms
- Official commercial-vs-personal guidance says individual subscriptions are for internal/development use; licensing/derived public metrics depend on plan and exchange. https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage
- Market data EOD can include indices, **but the public page does NOT verify NDX coverage for Basic or entitlement on the user's account**. https://support.twelvedata.com/en/articles/12682324-end-of-day-eod-pricing-market-data
- FRED NASDAQ100 is explicitly Nasdaq-copyrighted and must **not** be treated as rights-free for public/commercial rendering. https://fred.stlouisfed.org/series/NASDAQ100

## Two design options and choice
1. Directly treat `NDX` catalog/support pages and operator flags as commercial access evidence: lower coding effort, but material license and index identity risk. **Rejected.**
2. Preserve the dormant two-request provider adapter, and re-use exact strict P109 parser on *first* HTTP response before even spending the possible second credit. **Selected:** no new service, secrets, cost or API traffic; reduced risk of wasting quota on wrong type, duplicate dates, invalid prices. It does NOT prove NDX access or vendor rights.

## CI evidence — finished 2026-11-02 KST
- Functional commit: `74818cb3447130689c3341aa69fb5aa8549b7e45` on `lead/kic`.
- [GitHub Actions #41330955984](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41330955984): 3/3 SUCCESS; Python 1408/1408 PASS, Windows SQLite PASS, existing Chromium A/B/C/Guard/report PASS.
- Not tested: real Twelve Data HTTP, NDX account/index access, public licensing, paid API, real production, new UI.

## Current true status and recovery
- Provider licensed/verified index identifier: **UNVERIFIED**; Basic external display: **NOT ALLOWED BY DEFAULT**; secure key transfer: **NOT AUTHORIZED**.
- P111 fixes `proofinvest/twelvedata_consent_client.py` first-response parser, adds exact negative tests. P110 default remains no HTTP; user owner approvals still required for any external transfer or payment. Original data, source files and V13 PDF unchanged.
- Must NOT send provider questions, create account, execute NDX calls, bypass SEC 403, or pay without owner approval. When owner authorizes provider outreach, ask: **(a)** exact genuine Nasdaq-100 index symbol and Basic plan availability, **(b)** minimum appropriate plan and exchange license, **(c)** contest judge demonstration rights, **(d)** public dashboard of derived analytics and investor research use, **(e)** storage/retention/redistribution limits, **(f)** written cost and source-attribution terms.
- Automated full CI for exact SHA distinguishes synthetic/mock tests from real provider access. P111 has no new Production or Vercel work.
