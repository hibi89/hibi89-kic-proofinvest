# P184 — Nasdaq Data Link rights visibility (zero-network preflight)

Published official notices reviewed 2026-11-05 KST:
- Nasdaq Data Link terms (updated effective 2026-11-01): https://data.nasdaq.com/about/terms
- Nasdaq GIDS official notice (dated 2026-08-03): https://www.nasdaqtrader.com/TraderNews.aspx?id=DN2026-5

Nasdaq Data Link is not automatically the same licensed service as Nasdaq GIDS. Nasdaq Data Link terms govern its relevant products/agreements, not a universal license for Nasdaq-100. The Nasdaq Data Link page is JavaScript-served; current text availability and legal applicability to any eventual contract must be reconfirmed by the account holder. Neither catalog listing nor published index history establishes an NDX dataset subscription, vendor ownership/entitlement, or permitted SaaS, derivative analytics, AI use, public display, redistribution or competition submission.

P184 adds an independent *fail-closed* `nasdaq_data_link` candidate to the existing offline `evaluate_provider` preflight. This is only a safer rights/coverage inventory; no vendor request, account activation, payment, published return series, SEC retry or source transfer occurs. A negotiated order form/rights evidence and explicit owner approvals remain prerequisites.

```sh
python -m proofinvest.provider_rights_preflight --provider nasdaq_data_link --use contest_judge_demo
```

Expected intentionally blocked exit status 2, `network_requests_executed=0`. Existing `nasdaq_gids` remains a distinct candidate. This preflight cannot earn genuine data-rights completion points.
