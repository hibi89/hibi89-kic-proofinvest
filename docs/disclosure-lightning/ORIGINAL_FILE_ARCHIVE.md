# Disclosure Lightning — Original Filing Bytes (P2)

## Actual stage

New `disclosure_lightning/originals.py` provides a **separate** source-preserving read/write path for one SEC primary filing from a previously indexed `filings` row. No source URL is accepted from the CLI; it must come from the existing, validated CIK+accession metadata row in the canonical DL SQLite DB. This is deliberately not yet a financial data extractor or KIC numeric verdict.

### Offline deterministic test (safe synthetic input only)

First prepare a disposable index (example for a Unix-style temp directory; Windows use local paths):

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --collected-at 2026-10-27T00:00:00Z --db ./dl-local.sqlite3 --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json
```

Then explicitly supply a locally-created **synthetic** HTML file; this file is only for development and must NEVER be labelled as an SEC-fetched original:

```bash
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --input-file ./synthetic-filing.html
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --list
python -m unittest tests.test_disclosure_lightning_originals -v
```

The first import returns `SAVED`, an identical second import returns `REUSED`. Both keep raw bytes, `filing_sha256` and the acquisition origin `OFFLINE_FILE_UNVERIFIED`. Different bytes under the same filing ID append another receipt; previous ones remain unchanged. The original SEC submissions response and its separate `index_raw_sha256` remain intact.

### Real SEC primary HTTP (opt-in, not yet provider-verified)

1. Use `python -m disclosure_lightning --allow-network` to fetch official `submissions/CIK##########.json` metadata **first**, with a true contact-bearing SEC `DL_SEC_USER_AGENT`. Synthetic/offline metadata is NOT accepted for live original retrieval.
2. For a CIK/accession already indexed as `INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED`, run:

```bash
python -m disclosure_lightning.originals --db ./dl-real.sqlite3 --cik 0000320193 --accession YOUR_VERIFIED_SEC_ACCESSION --allow-network
```

The same `DL_SEC_USER_AGENT` environment variable is required in both commands. `YOUR_VERIFIED_SEC_ACCESSION` is a placeholder, not a valid accession. The original GET is one request to its official `https://www.sec.gov/Archives/edgar/data/...` primary file, with a bounded size (25MB), 15-second timeout, no external proxies, redirects, background crawling, retries or invisible follow-on links. It accepts HTML/XML/plain text response types only; do not interpret 200/HTML as independent attestation or content-based SEC authentication. Follow SEC fair-access rules: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data .

A successful authorized HTTPS transfer is labelled `SEC_HTTPS_RESPONSE_UNVERIFIED`, `authenticated_external_source=false`. No live SEC request or actual original filing body has been validated in this development session. A `source_uri` found in a synthetic fixture is only a constructed link and cannot authorize live network mode.

### KIC / security boundary

- Import: `from disclosure_lightning.originals import read_original_bytes`; call `read_original_bytes(db_path=..., cik=..., accession=..., sha256=...)`. The SQLite database is opened read-only; content is returned only after recalculating SHA-256 and matching the selected digest. The caller must sanitize untrusted HTML and separately validate financial facts.
- The `original_filing_receipts` schema is **additive** to the canonical DL store. The already existing `proofinvest/dl_bridge.py` is metadata-only. Never automatically promote `raw_sha256` to official verification, or silently fuse original bytes into the KIC numeric verifier.
- A single per-file original response and bounded single-company submissions response are tested with synthetic/mock HTTP. No live SEC access, original-content claim certification, EDGAR pagination, 429 backoff, bulk synchronization, full KIC document extraction, or production/frontend release is proven. These are separate next acceptance gates.
- No customer data, SEC keys or private `hibi89/Bid_Owl` code is committed. The KIC public repo, Nov12 PDF-only preliminary requirements and the KIC lead's `lead/kic` approval gate remain unchanged.
