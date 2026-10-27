# Disclosure Lightning — standalone public KIC feature branch

**Status:** minimum offline vertical unit; does NOT perform live SEC HTTP, authenticate actual filings or download original HTML.

Source facts: SEC official Submissions API uses 10-digit CIK at https://data.sec.gov/submissions/CIK##########.json. SEC fair access applies. No API key is needed for this public GET, but network code is intentionally NOT implemented in this offline unit.

## Reproduce with a local SEC-shaped JSON

    python -m disclosure_lightning.cli --input ./sample.json --database ./dl.sqlite --cik 0000320193 --collected-at 2026-10-27T10:00:00Z --as-of 2026-10-27

Output: JSON result with source payload hash, records, inserted versions/observations, metadata-only envelopes. The input must include official-shaped cik and filings.recent columns accessionNumber, form, filingDate, primaryDocument. No HTTP is made. Initial automated fixture only uses wholly synthetic values.

## Contract

RawFilingEnvelopeV1 has schema_version 1.0, SEC_EDGAR, issuer_cik, accession, form, filed_at, collected_at, as_of_cutoff, source_uri, submissions_uri, raw_sha256, raw_sha256_scope, filing_content_sha256 (null), original_filing_retrieved (false), evidence_status METADATA_ONLY_UNVERIFIED, amends_accession (unknown), amendment_form.

**IMPORTANT:** raw_sha256 hashes the provided SUBMISSIONS JSON, **not** original issuer filing content. Generated filing URL is a locator from untrusted metadata and remains unverified. No automatic amendment accession association, ownership verification, redistribution clearance, or investment advice. Only 10-K/10-Q/8-K and /A accepted; unmatched forms are skipped. Metadata changes create new immutable versions; repeat source snapshots are idempotent.

## Next implementation

Owner target 2026-10-28/29: add official SEC transport as a separate explicit consent/API-policy gate, confirm official-shaped real inputs, KIC read-only consumer integration, clearer status/controls. After MVP: resilience, resumption, frontend, amendment linking with verified source, Windows/performance. Do not import private Bid_Owl code.
