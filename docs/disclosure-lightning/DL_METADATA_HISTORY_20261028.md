# DL SEC metadata revision history (KIC branch)

**Scope:** local, offline version-index for actual *submissions JSON metadata* only. Does NOT download, authenticate or hash an original 10-K filing.

Changed SEC Submissions metadata for the same issuer CIK + accession is now retained under a distinct metadata fingerprint, without overwriting the original first-seen filing row or source JSON snapshots. The stored JSON source SHA-256 remains distinct from an original filing-content SHA (null). An unchanged filing encountered in a later changed submissions response creates an observation linkage, not a new metadata version.

## CLI

    python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db path/to/filings.sqlite3 --history-accession 0000320193-25-000901

Requires a previously initialized SQLite DB. This is read-only. Python API: disclosure_lightning.core.list_filing_versions(db_path, cik='0000320193', accession='0000320193-25-000901'). Results are first-seen ordered and include metadata_sha256, metadata, first_submissions_sha256 and observed_in_snapshots. Amendment /A accessions remain separate; matching parent is UNKNOWN.

Existing SQLite databases are transparently backfilled with their original filing entries the next time the normal save_index() routine ingests an input. The migration is local and additive; original observations and raw bytes are preserved. The legacy list_filings() still returns first-seen data for backward compatibility.

Reproduce with `python -m unittest tests.test_dl_metadata_versions -v` or the full repository suite. No API key, SEC GET or private Bid_Owl imports needed.
