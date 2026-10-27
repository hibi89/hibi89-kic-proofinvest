# DL → KIC technical chief | P3 verified extractor (2026-10-28 KST)

**DL source SHA:** `eda89fe461279ab683872469b04437ab1e959be1` · [GitHub Actions CI #40534506681](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681) **SUCCESS / 390 of 390 Python tests PASS**. All tests are repo-level and synthetic/mock/offline; no actual SEC live HTTP was performed.

## Actual implementation

- `disclosure_lightning/extract.py`: read only saved original filing receipt by CIK/accession/SHA256, independently verify raw bytes, decode UTF-8, use stdlib HTMLParser without network or script execution, skip script/style/head/noscript, return capped source-line-anchored text blocks with per-block digests. `truncated` is explicit when size limits are hit. HTML source-line is a **hint**, not exact raw byte span. No automatic fact verification, no inflation of source rights or financial evidence confidence.
- `--find Revenue`: safe bounded literal search returns `evidence-candidates.v1` with conservative `financial_claim_verified=false`, `source_authenticity_verified=false`, `SOURCE_LINE_HINT_NEEDS_REVIEW`.
- `disclosure_lightning/originals.py`: explicit `--content-type text/html` for a **local OFFLINE_FILE_UNVERIFIED** file, allowing one CLI synthetic source→stored raw→extracted text→candidate search E2E test. Live transfer Content-Type comes from official HTTP response only; CLI overrides rejected.
- Tests: `tests/test_disclosure_lightning_extract.py` (15 tests); `tests/test_disclosure_lightning_originals.py` (+2 tests). Full latest CI 390/390 PASS. See `docs/disclosure-lightning/ORIGINAL_FILE_ARCHIVE.md` for canonical commands and limits.
- The original metadata pipeline remains `python -m disclosure_lightning`; no extra SQLite format. `lead/kic` ProofInvest consumer currently reads DL **metadata only**. We did not edit other branches, the 11/12 submission PDF, production, secrets, private Bid_Owl, or implement actual live SEC authenticity.

## KIC review requested

Review P3 `extracted-text.v1` + `evidence-candidates.v1` contracts for a *future* KIC source-span extractor consumer, expressly as unverified candidate evidence. KIC's existing metadata bridge is already merged separately via PR #2. Draft PR #1 for DL remains **unmerged**. The exact HTML byte span/financial contextual extraction, live official SEC original filing retrieval validation, SEC HTML encoding fallback, paginated historical EDGAR filings and actual KIC end-to-end original-document integration remain pending. Integration changes require KIC chief review and permission to merge.

---

> **2026-10-28 DL P2:** New `disclosure_lightning/originals.py` collects bounded SEC primary filing bytes via explicit contact-bearing opt-in, or reads explicitly provided offline files; stores immutable SHA256 receipts and provides read-only digest-checked byte retrieval. [GitHub CI 373 tests PASS at `89cd9024e304b465447936ad58d2de407f2dbe9c`](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40532494845). Official live SEC success/real content verification and KIC parser integration NOT done. Source `docs/disclosure-lightning/ORIGINAL_FILE_ARCHIVE.md`; KIC recipient status at `TO_KIC_LEAD.md`. Supersedes metadata-only last-state claims below. No automatic main or lead merge.

> **2026-10-28 CURRENT VERIFIED P1:** `feature/disclosure-lightning` canonical only `disclosure_lightning/core.py` via `python -m disclosure_lightning`; removed alternative `mvp.py` / `cli.py` and obsolete tests. Historical as-of measured UTC gate, explicit SEC User-Agent validation, amendment forms default, source-digest safety, fixture against ProofInvest Apple identifiers. **[Latest tested 358/358 PASS at `303c17bc073be7233e7b4dd836823e4cf2974315`](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40530744523).** Last docs update is newer than verified CI SHA. KIC [draft PR #1](https://github.com/hibi89/hibi89-kic-proofinvest/pull/1) remains unmerged. No real live SEC HTTP/HTML retrieval, confirmed external authentic source or full DL→KIC merged runtime. Next priority: KIC bridge integration review and real authorized SEC GET/original bytes. For canonical commands read `disclosure_lightning/README.md`. This header overrides older pending/duplicate-code directions below.

---

> **LATEST DL IMPLEMENTATION 2026-10-27 KST:** Minimum SEC recent-filings indexer is ACTUALLY IMPLEMENTED on `feature/disclosure-lightning` using `python -m disclosure_lightning` (`disclosure_lightning/core.py`). Offline synthetic SEC-shaped JSON→index & provenance SHA256→immutable SQLite→JSON/list CLI works; explicit opt-in, validated contact-bearing `DL_SEC_USER_AGENT` permits one bounded SEC HTTPS GET but live SEC response not tested. GitHub [CI 363 Python tests PASS at `2634950dca20caf5687ec12d96542b665faf23d1`](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40526917500); includes 17 added `test_disclosure_lightning.py` and independently pushed 12 `test_disclosure_lightning_mvp.py` tests. Parallel `mvp.py`/`cli.py` has a different schema; standard CLI is `python -m disclosure_lightning`, do NOT combine DBs and resolve dual implementation before KIC merging. No actual original filing bytes, real SEC live verification, cross-package ProofInvest integration, or frontend. Full current handoff: `docs/disclosure-lightning/TO_KIC_LEAD.md`. The later historical 'NO DL RUNTIME CODE' statement below is superseded. No production / main / lead/kic / preliminary PDF modification.

> **LATEST OWNER DIRECTIVE 2026-10-27 23:50 KST:** KIC DL lead is the former Bid Owl chief, and standalone technical MVP due **Oct28–29**. This overrides earlier direction to wait for Dec03 finalist *for isolated DL branch development only*. Build NOW on feature/disclosure-lightning, then test/harden and implement frontend toward submission. KIC preliminary PDF-only scope remains unchanged. See KIC chief orders at https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/disclosure-lightning/TO_DL_LEAD.md and write progress at docs/disclosure-lightning/TO_KIC_LEAD.md. New standalone code is original PUBLIC implementation, not a copy of private Bid_Owl. No automatic concurrent agent runs or live SEC calls.
# Disclosure Lightning — DL Team Handoff

**Owner:** DL technical lead (GPT-6 in the owner's ChatGPT workflow)  
**Source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`  
**Created:** 2026-10-27 KST, from `lead/kic` at `38cc09b6ee058783a3b9f1b1c240b039386f6410`

## Owner decision — 2026-10-27

The owner has **retired Bid_Owl as the active Kmong product-development target** and redirected this working role to **Disclosure Lightning (DL)** in an isolated KIC repository branch. Do not continue the procurement CSV/product roadmap on the DL branch. Previous `hibi89/Bid_Owl` branches remain untouched and are not to be merged into KIC.

This is a *role and worktree boundary* for collaboration in separate chats, not a claim that two autonomous assistants are concurrently running or that an actual SEC connector has already been implemented.

## Responsibilities and interfaces

DL independently handles **official public filing retrieval**, indexing, provenance, incremental changes, original-source hashes and amendment history. First provider **SEC EDGAR** (`data.sec.gov` issuer submissions/companyfacts and verified official primary filing links). Secondary providers such as OpenDART require a separate, validated provider adapter and proper authorization.

The output to KIC ProofInvest is a versioned **RawFilingEnvelopeV1** JSON/file boundary, not an import of the full historical procurement Bid_Owl app, and not an unverified financial claim. Essential fields: `schema_version`, `provider`, `issuer_cik`, `accession`, `form`, `source_uri`, `filed_at`, `collected_at`, `raw_sha256`, `as_of_cutoff`, `evidence_status`, and optional `amends_accession`. Raw original records and historical versions are immutable. Reject ambiguous CIK/ticker matches and missing/invalid provenance; keep an explicit UNKNOWN state.

The *independent* preprocessor, potentially SMAX after contract validation, handles financial fact normalization (scale, currency, fiscal period, source span). KIC ProofInvest owns financial verification, research/risk calculations, conditional ML/DL and final investment-research report. DL does **not** output buy/sell recommendations or financial risk scores.

## Public repository / private code policy

**KIC repo visibility is PUBLIC.** Do not paste, commit or transplant any code, secrets, datasets or proprietary documents from private `hibi89/Bid_Owl` into this repo. Reimplement general reusable design patterns independently, review licenses and rights before publication. Never commit SEC API credentials, private institutional evidence or customer data. Use synthetic fixtures for initial offline QA; live fetch only through compliant official read-only endpoints with a contact-bearing User-Agent, fair access, bounded retries/timeouts/rate limits and verified source identifiers.

## KIC lead reconciliation — two separate tracks

- **Prelim (2026-11-12 10:00 KST):** KIC existing 7-section, <=10-page official PDF is the submission deliverable. New DL code is **not** a gate for this PDF. Do not modify organizer PDF, `lead/kic`, `main`, production or submission without explicit approval.
- **DL technical track (this feature branch):** allowed to develop/QA separately now under the owner's newer explicit role/branch direction. The older preliminary `SUBMISSION_SCOPE_FREEZE_20261027.md` still controls what may be claimed in the initial PDF, not the existence of this isolated development branch.
- **If finalist (Dec 03):** use successfully QA-validated DL SEC records through a narrow interface for ProofInvest; ensure live source verification, rights, user-approved integration. Final submission 2026-12-22 10:00 KST.

## Ordered implementation stages

1. **Offline MVP:** Python stdlib package, typed RawFilingEnvelopeV1 contract, strict CIK/accession/time/source checks, synthetic fixture, immutable SQLite provenance and deterministic tests. No external network or credentials needed for unit tests.
2. **SEC provider:** official `submissions/CIK##########.json` with bounded compliant retrieval, 10-K / 10-Q / 8-K records, accession/index links, optional `companyfacts`, idempotent incremental sync/checkpoints, safe retry, clear source/availability timestamps. Verify with official SEC documentation and actual permitted responses before calling LIVE VERIFIED.
3. **KIC read-only handoff:** `RawFilingEnvelopeV1` JSON/manifest output with hashes and source provenance; independent proofinvest consumer tests and filing-specific corrections. No private Bid_Owl code import.
4. **Hardening:** amendment preservation, incomplete/stale as-of data rules, bad JSON/rate-limit/adversarial parsing tests, Windows/local reliability/performance with measured results.

## Current state and next action

**BRANCH CREATED; NO DL RUNTIME CODE / SEC FETCH VERIFIED.** Next development `ㄱ` proceeds with stage 1 code, not more proposal-only docs. The current lead source contract is `docs/architecture/DISCLOSURE_LIGHTNING_INTERFACE_20261027.md`; original KIC requirements remain at `docs/architecture/FINAL_KIC_PRODUCT_DIRECTION_20261027.md`. This file is the authoritative DL role/branch handoff and does not change the frozen preliminary submission.
