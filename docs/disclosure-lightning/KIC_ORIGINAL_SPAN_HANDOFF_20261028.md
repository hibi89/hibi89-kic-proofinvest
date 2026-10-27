# KIC read-only Disclosure Lightning original-byte source-span integration

## Stage verified by offline CI

DL chief implemented `disclosure_lightning/originals.py` on feature/disclosure-lightning. This KIC integration branch includes the same independently reviewed module and its synthetic tests, plus a NEW KIC read-only source-span consumer. Existing `disclosure_lightning/core.py` is the canonical SEC Submissions index, and `proofinvest/dl_bridge.py` remains metadata-only. No duplication of the original collector and no private Bid_Owl code.

### One-command full synthetic chain

    python -m proofinvest.kic_dl_original_demo

Runs SEC-shaped invented issuer metadata -> canonical DL SQLite immutable Submissions JSON -> invented original HTML bytes -> separate original-content SHA256 stored without overwrite -> reimport dedup -> hash-verified read -> exact ASCII phrase byte offsets -> HTML-escaped context for manual review -> KIC metadata/numeric contract check. This is ALL synthetic offline; no actual SEC HTTP response or original 10-K was obtained and no displayed source facts are authenticated.

### KIC review method

`proofinvest.dl_source_span.anchored_source_span(db_path=..., cik=..., accession=..., sha256=..., needle='LITERAL_PHRASE')` returns first/last byte offsets from exact SHA256-verified stored original bytes. Rejects wrong issuer/accession, hash mismatch, duplicate or absent phrase, unsafe limits and unapproved receipt linkage. Escapes HTML; does not render it, derive numeric facts, execute JS or certify original filing authenticity.

Original archive SHA256 and Submissions JSON SHA256 are DIFFERENT. Labels `OFFLINE_FILE_UNVERIFIED` or `SEC_HTTPS_RESPONSE_UNVERIFIED` describe input acquisition mode, not independent legal/source verification. Do not promote either to verified SEC financial figures or contest claim.

### Limitations and next

Real external SEC submission + official filing GET is opt-in only with an actual approved SEC User-Agent. It has NOT been run in this development session. Historical continuation paging, extracts with rule/version and source span validation, full independent source rights, Windows compatibility, production and frontend remain separately tested tasks. User-private PDF and official DAKER upload remain unchanged.

Read [DL archive interface](ORIGINAL_FILE_ARCHIVE.md); run `python -m unittest tests.test_dl_original_span_bridge -v` or the full offline CI.
