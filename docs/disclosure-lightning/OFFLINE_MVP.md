# Disclosure Lightning — canonical SEC MVP

**2026-10-28 consolidation:** the parallel experimental `disclosure_lightning/mvp.py` and `disclosure_lightning/cli.py` plus their overlapping tests were RETIRED from this branch. Their history remains in Git, but do not import or execute them. There is now only one supported public SEC ingest and SQLite schema: `disclosure_lightning/core.py` invoked by `python -m disclosure_lightning`.

See [canonical CLI usage](../../disclosure_lightning/README.md). Offline synthetic example (no network, no secret, no live SEC proof):

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --collected-at 2026-10-27T00:00:00Z --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json --db /tmp/dl.sqlite3
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db /tmp/dl.sqlite3 --list
```

A new source digest covers only the exact original **SEC submissions API JSON** bytes, NOT original 10-K/10-Q/8-K filing bytes. `raw_sha256` remains null until full filing retrieval actually exists. Unknown amendment links stay null. Both original source response and index metadata persist in a local SQLite ledger. The server-side ingestion is idempotent for exactly unchanged API bytes, and later changed snapshots are separately recorded.

Chronology control: `collected_at` is required to be an offset-aware instant which normalizes to UTC and is **not after** `as_of`. If importing old archive data, the caller-provided observed-at timestamp is still UNVERIFIED, not an attestation of historical SEC availability; do not invent this timestamp. For live `--allow-network`, observed-at is derived from actual process time and cannot be replaced with a caller-supplied date.

Opt-in online mode requires a real identifying `DL_SEC_USER_AGENT`, performs one bounded official SEC HTTP GET without redirects, and remains unverified until actual provider response evidence is preserved. No recurrent polling, original filing HTML ingestion, company ticker lookup or PDF/front-end has been implemented.

KIC `lead/kic` already has a **separate** bridge `proofinvest/dl_bridge.py`; its real merged end-to-end integration with this DL producer remains pending KIC review. Do not copy private Bid_Owl source or alter the Nov12 PDF submission.
