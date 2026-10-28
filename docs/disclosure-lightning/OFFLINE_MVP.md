# Disclosure Lightning — canonical SEC MVP

**2026-10-28 consolidation:** the parallel experimental `disclosure_lightning/mvp.py` and `disclosure_lightning/cli.py` plus their overlapping tests were RETIRED from this branch. Their history remains in Git, but do not import or execute them. There is now only one supported public SEC ingest and SQLite schema: `disclosure_lightning/core.py` invoked by `python -m disclosure_lightning`.

See [canonical CLI usage](../../disclosure_lightning/README.md). Offline synthetic example (no network, no secret, no live SEC proof):

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --collected-at 2026-10-27T00:00:00Z --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json --db /tmp/dl.sqlite3
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db /tmp/dl.sqlite3 --list
```

A new source digest covers only the exact original **SEC submissions API JSON** bytes, NOT original 10-K/10-Q/8-K filing bytes. `raw_sha256` remains null until full filing retrieval actually exists. Unknown amendment links stay null. Both original source response and index metadata persist in a local SQLite ledger. The server-side ingestion is idempotent for exactly unchanged API bytes, and later changed snapshots are separately recorded.

Chronology control: `collected_at` is required to be an offset-aware instant which normalizes to UTC and is **not after** `as_of`. If importing old archive data, the caller-provided observed-at timestamp is still UNVERIFIED, not an attestation of historical SEC availability; do not invent this timestamp. For live `--allow-network`, observed-at is derived from actual process time and cannot be replaced with a caller-supplied date.

Opt-in online mode requires a real identifying `DL_SEC_USER_AGENT` and performs official SEC GET operations without redirects. For HTTP 408/429/500/502/503/504 and transient transport failures, each operation retries serially at most three total attempts. A valid `Retry-After` delta or HTTP date is respected; waits above 30 seconds fail closed. Retry waits are at least 0.2 seconds; missing or malformed values use bounded 0.5/1-second backoff. Each attempt times out after 15 seconds. This is per operation, not a cross-process rate limiter or scheduler. Transport success remains unverified until actual provider response evidence is preserved. No recurrent polling, company ticker lookup or PDF/front-end has been implemented.

For the submissions endpoint, a saved ETag is sent as `If-None-Match` only after its cached response BLOB, SHA-256, CIK, and source URI pass local checks. For original archive files, the CLI applies the same rule against an immutable stored filing BLOB, SHA-256, MIME, and source URI. A 304 reuses only that validated BLOB and records a distinct check event; it does not claim a new response body was received. If no valid cache exists, a 304 fails closed. ETag behavior from either live SEC endpoint is unverified; mocked response tests cover 200/304 handling for both.

KIC `lead/kic` already has a **separate** bridge `proofinvest/dl_bridge.py`; its real merged end-to-end integration with this DL producer remains pending KIC review. Do not copy private Bid_Owl source or alter the Nov12 PDF submission.
