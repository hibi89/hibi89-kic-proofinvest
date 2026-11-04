# P187 public first-party filing vintage review, no SEC retry

Checked **2026-11-05 KST** from searchable official records (NOT a fresh
programmatic SEC GET, and without capturing SEC 10-K original HTML bytes):

- FY2026 Apple Form 10-K; period ended **2026-09-26**, accession
  `0000320193-26-000026`, filed **2026-11-03**.
  Official SEC indexed metadata:
  https://www.sec.gov/Archives/edgar/data/320193/000032019326000026/0000320193-26-000026-index.htm
- FY2025 period ended **2025-09-27**, accession
  `0000320193-25-000079`, filed **2025-10-31**.
  Official SEC indexed metadata:
  https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm
- Apple first-party SEC filings catalog:
  https://investor.apple.com/sec-filings/default.aspx

## Reason and safeguards

The older FY2025 manually transcribed local AAPL case is historical and
must not masquerade as the newest available issuer filing as of
2026-11-05. P187 offers a strictly opt-in read-only *public metadata*
preflight. It checks date-only as-of eligibility, exact accession and
fiscal period. Date-only freshness conservatively becomes available the
day AFTER filing, never on the unqualified filing day. Its last checked
date is frozen at 2026-11-05; any later `as_of` requires rechecking.

P187 does not make the issuer HTML bytes available or authenticate them;
neither does it grant Apple/SEC original copying/display/AI rights, source
completeness, accounting E2E or public Production rights. SEC P105 403
MUST NOT BE RE-REQUESTED. No owner original, filing data, keys, PDF or
Vercel/DAKER account is altered; zero API GET/cost/trades. A public catalog
entry is **not sufficient to earn any of the 14 currently unearned original
publisher provenance points**. This module deliberately does not change
the existing historical user request or original Engine B behavior.

```sh
python -B -m scripts.apple_filing_vintage_preflight --ticker AAPL \
  --as-of 2026-11-05 --accession 0000320193-26-000026 --period-end 2026-09-26
python -B -m unittest tests.test_apple_public_filing_vintage -v
```

A matching public catalog date-only metadata check is still explicitly
unverified for original bytes; wrong or stale filing metadata returns exit 2.
