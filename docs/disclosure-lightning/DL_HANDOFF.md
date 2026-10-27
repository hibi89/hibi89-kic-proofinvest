# DL P8 — Verified index bytes / unverified amendment candidates (2026-10-28 KST)

1. **Goal:** Add useful amendment exploration without falsely turning metadata heuristics into an authenticated original/amendment relationship.
2. **Design/alternatives:** Chose read-only SHA-pinned SQLite original response lookup + `reportDate`/form + strictly earlier filingDate candidate. Rejected write-back/guessing from nearby accession sequences or same-form filings alone: SEC submissions metadata does not reliably encode amendment target. Ambiguity and missing report periods produce no inferred parent. No core schema change.
3. **Tests:** Five methods appended in `tests/test_disclosure_lightning.py`: unique matching source period, two originals ambiguous, missing reportDate, excluded post-as-of observation, tampered stored bytes, and CLI no-import path (last two integrated into other test names). Code written and GitHub pushed; *actual full repo unittest/GitHub Actions P8 results NOT VERIFIED*.
4. **Outcome:** `history.review_amendment_candidates` returns read-only fields `candidate_parent_accession` (only unique, still unverified), `authoritative_amends_accession=null` and `authenticated_amendment_relation=false`. Does not edit immutable `filings.filing_json`. CLI `--review-amendments` added, no network.
5. **Failure/recovery:** GitHub Actions head/commit status inaccessible via available current connector endpoints, previous P7 suite remained unverified. Local git checkout still blocked DNS. Do not claim any newly run full-repo tests. Git parent keeps rollback and feature isolation.
6. **Repo/branch/SHA:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`, first review source `5724fedddd09519cce0e199bcc443903f255e6e5`; CLI `34308fe31368b53986498ba0b1c202b40e9c431a`; bounded scan latest `543796a9494227f53f2bba6199f23b3062e7f13c`, tests `8c05c64f0792ed28dbe150f705d91fa471061daa`. Docs HEAD updated separately.
7. **Runtime/deployment:** `python -m disclosure_lightning.history --review-amendments` on local SQLite, JSON read-only output. No hosted DL Production URL.
8. **Sources/backup/security:** Only existing local untrusted synthetic/historical SEC-shaped JSON observations; SHA256 checks detect local corruption, not actual SEC authenticity or source rights. Real SEC GET, private Bid_Owl and KIC PDF/DAKER unchanged.
9. **Next:** Run exact source tests/CI; audit amendment candidate false positives and possibility of genuine explicit original reference in licensed source files, then narrow reviewed KIC integration. No automatic relation certification.
10. **As-of / date / verification:** 2026-10-28 KST, P8 source/tests GitHub pushed but full CI unverified; KIC lead independent numeric literal CI 447 PASS is different source/branch. Nov12 prelim PDF unchanged.

---

# DL P7 — Multi-page SEC history offline batch (2026-10-28 KST)

1. **Goal:** Support several pinned manifest-listed historic SEC submissions pages in a single explicit offline run, retain existing backend, zero API expenses and no auto network requests.
2. **Architecture/decision:** Compared (A) small sequential idempotent `core.save_index` with full preflight / explicit partial recovery (selected: low change/cost) against (B) refactoring canonical SQLite for a single cross-page atomic transaction (stronger all-or-nothing but larger regression and migration risk). Implemented max 8 pages, 8MB/page, 32MB total, SHA-bound manifest, UTC chronology and cross-page accession uniqueness.
3. **Tests:** Five regression methods added to existing `tests/test_disclosure_lightning.py`; end-to-end whole-repository GitHub Actions **NOT VERIFIED** on P7 SHA. Previous stable recorded DL P3 source was 390/390 PASS. Current CI status tool lists no commit statuses; PR-only workflow query does not prove workflow absence. Run `python -m unittest discover -s tests -v` when code locally available.
4. **Outcome/status:** Batch parser, CLI listing, directory ingestion, prevalidate-before-write and partial-recovery implemented and GitHub pushed. No live SEC authentication/production or passed newest whole-repo CI evidence.
5. **Errors/rollback:** Prior P6 separate new-test-file write twice blocked; P7 extends existing test module. Local `git ls-remote` cannot resolve github.com; tested source execution in local container is blocked without faithful repository materialization. Git ancestors allow rollback without force push. P7 errors explicitly label incomplete saves rather than silently calling them success.
6. **Repository/branch/SHA:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; P7 source `f5fd0ac85c1283730d899a7f41cb3d75c0773790` and secure read `fc5f875aac0701cd495e5303b7f8f7dc1f78c44a`, tests through `99bf4983d055fbc581ebda394a527c4df7da434c`. Files `disclosure_lightning/history.py`, `tests/test_disclosure_lightning.py`, README, handoffs.
7. **Runtime/deployment:** `python -m disclosure_lightning.history --list-manifest`, `--batch-dir` offline; no DL Production/Vercel project/URL.
8. **Data/security:** Keep original SEC index response, original filing hash distinction, issuer/authenticity status as UNVERIFIED; no private Bid_Owl, KIC PDF/PPTX, token, SEC contact or real issuer originals moved to public GitHub. Only bounded on-disk local input; no HTTP.
9. **Next:** Verify full P7 exact-source CI; test multi-page real-format fixtures when permitted; consider amendment-parent candidate linking without unsupported truth claims. KIC lead must approve any merge/integration. Real HTTP and DAKER final submit need separate authorization.
10. **KST verification:** 2026-10-28. Remote branch code/test commits confirmed, whole-suite and Production UNVERIFIED, no official contest submission action. Documentation successor SHA to be checked after update.

---

# DL P6 — SEC historical continuation offline minimum unit (2026-10-28 KST)

1. **Goal:** Extend existing recent-only SEC Submissions metadata indexing to explicitly supplied historical `filings.files` JSON, without new network side effects or extra SQLite schema.
2. **Design/alternatives:** Avoid automatic GET/pagination (would require real SEC User-Agent, rate/HTTP policy and network verification). Prefer offline one-page ingest gated by previously stored pinned main observation SHA, allowed SEC exact page name, declared filing range/count and UTC collection chronology. Uses existing `core.save_index`, preserves original records and idempotence. No full issuer document authenticity or ML/AI claims.
3. **Tests:** Added regression in `tests/test_disclosure_lightning.py`; 9 independent local history behavior tests PASS with a **local core-contract shim**, not actual repository GitHub CI. Original full suite remains **NOT_VERIFIED** on this source. Verification command `python -m unittest discover -s tests -v` needs actual repo CI; earlier P3 390/390 succeeded at [#40534506681](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681).
4. **Progress:** History parser/CLI code and in-repo canonical SQLite regression committed, static source retrieval verified. Live SEC historical requests, immutable source authenticity and KIC original filing integration remain unverified.
5. **Errors/recovery:** Two GitHub `create_file` attempts for separate regression file blocked by tool safety checks; pivoted to minimal test in existing DL test file via `update_file` and confirmed remote file. One bad timezone expectation in local test corrected before final 9/9 run. No force push or schema migration. Previous Git parent provides rollback.
6. **Repo/branch/SHA:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`. Code addition `98ae2496264e5356f79e2fe7b6bd14796d99fea6`, first included test commit `4dedf4259c907eba6b15b69428bce1c5a1cda13b`; successor docs HEAD to verify after writes. Source `disclosure_lightning/history.py`, tests `tests/test_disclosure_lightning.py`, usage `disclosure_lightning/README.md`.
7. **Runtime/production:** `python -m disclosure_lightning.history` command works in local shim integration; no DL hosted Production/Vercel URL. Existing KIC runtime separate.
8. **Originals/credentials:** No live SEC HTTP, identification email, private Bid_Owl code, user PDFs/PPTX, original issuer documents or secrets written to public GitHub. Parent main manifest and page bytes preserved in immutable ledger when run.
9. **Next priorities:** Exact-code Actions CI and full suite; bounded manifest discovery/continuation continuation testing; future opt-in HTTP single page only after owner-approved SEC User-Agent; KIC lead review before any bridge or UI merge. DAKER remains exact file/title separately owner-gated.
10. **Timestamp/verification:** 2026-10-28 KST, GitHub feature branch source verified, 9 shim integration tests PASS; full source CI/live API/Production unverified. Prelim due 2026-11-12 10:00 KST PDF only, independent of DL.

---

# DL P5 — bounded HTML charset support (2026-10-28 KST)

1. **Objective:** Decode legitimately non-UTF-8 saved HTML evidence without broad heuristic guessing or silently changing immutable original bytes.
2. **Design:** Strict `text/html` only, first 4096 raw bytes, first bounded meta charset declaration. Allow UTF-8 and Windows-1252; ISO-8859-1 means Windows-1252 per HTML parsing convention. Unsupported/conflicting declarations and invalid bytes fail closed. MIME-labeled XML/XHTML, plain text remain UTF-8-only.
3. **Tests:** Three new `tests/test_disclosure_lightning_extract.py` methods; **8/8 local standalone helper behavior checks passed**, however the local test repeats just the helper because repository clone failed DNS. Full exact-branch GitHub Actions **not verified**; previously tested P3 390/390 at [#40534506681](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681).
4. **Outcome:** New code committed; receipts expose declared/applied encoding while `charset_claim_verified=false`, `source_authenticity_verified=false`, `suitable_for_automatic_financial_facts=false`. P4 line-byte locators remain only for plain UTF-8; HTML uses conservative line hints.
5. **Failure/recovery:** Local `git clone` failed `Could not resolve host: github.com`; retry not useful in blocked DNS runtime. Continued via authenticated GitHub connector and static diff review; local helper tests 8 pass. Full repo tests/CI pending. Prior code recoverable via Git parents, no force push.
6. **Repo/branch:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`, code/test SHA `8cd8e12d50dc1a9243e167a93d048786965efc8c`; `disclosure_lightning/extract.py`, `tests/test_disclosure_lightning_extract.py`.
7. **Runtime:** `python -m disclosure_lightning.extract`, offline local original store only; no DL Vercel/Production URL.
8. **Originals/secrets:** No actual SEC traffic, API keys, private Bid_Owl files or KIC confidential PDF/PPTX in public commits. Git history is rollback; local archived bytes remain immutable.
9. **Next:** Verify full-suite CI exact source; review KIC latest 408/408 synthetic citation card (KIC `lead/kic@e1c94598`), then SEC historical pagination/continuation or HTML source-context review. KIC owns bridging/UI; do not overwrite.
10. **Time/status:** 2026-10-28 KST. Code is pushed; full suite and live SEC remain UNVERIFIED. Official KIC 2026-11-12 PDF-only prelim/user approval untouched.

---

# DL P4 — UTF-8 raw text line span implementation (2026-10-28 KST)

**Scope/owner:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; source/tests through `8253270db5cf309d963cc76d9b1569389a34c8d8`. **New full-suite GitHub CI not yet confirmed**. Previous exact-run baseline P3 at `eda89fe`: [390/390 PASS](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681).

**Implementation:** `disclosure_lightning/extract.py` records exact raw byte `start_byte`/`end_byte_exclusive` and per-line `raw_span_sha256` for decoded local UTF-8 text/plain (or offline explicit opaque text) backed by the stored full-filing SHA. Checks UTF-8 BOM, Unicode multibyte, CRLF and skipped line positions without changing raw storage. Normalized display text remains separate and is not an original-byte transcription. HTML/XML retains line hints only; never promotes financial or source authenticity. `tests/test_disclosure_lightning_extract.py` adds three tests (BOM/Unicode/CRLF, candidate contract, skipped long line). **No live SEC request, no paid API, no Production or cross-branch merge.**

**Cross-project reconciliation:** KIC lead's `proofinvest/dl_source_span.py` uses `start_byte`/`end_byte_exclusive`; P4 aligned names for a future consumer, but the two schemas are NOT automatically integrated. KIC lead last documented 401/401 offline tests at source `9ab9163`, different branch. Draft PR #1 remains unmerged; do not overwrite lead/kic bridge.

**Next P5:** Check exact branch CI at source SHA; if green update verification ledger. Then review SEC HTML encoding + full historical continuation and source-context consumer with KIC chief. Official 2026-11-12 preliminary PDF-only remains separate and unmodified. No private Bid_Owl content, tokens or external issuer originals in public GitHub.

---

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
