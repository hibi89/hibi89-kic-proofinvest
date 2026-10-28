# DL P10 → KIC Lead | 2026-10-28 KST

## Latest implementation checkpoint — conditional SEC response caches

- **Remote source HEAD:** `83ac07efb03314fba4db6d8a2cfa82ae8016c541` on `feature/disclosure-lightning`; GitHub commit lookup confirms it is present. Combined status has no checks yet. No merge or other branch changes.
- **Submissions JSON cache:** `e17dbdf5eda6814b13f3727c4710de9ac674cd90` adds hash/CIK/source-bound ETag persistence and fail-closed 304 reuse.
- **Original archive cache:** `540ada4516511d5de7ce8024199c486ca27638dc` adds conditional retrieval keyed to indexed filing/source/digest, with separate HTTP check provenance and fail-closed 304 behavior. `d2b2413` also requires the live locator to exactly match persisted indexed metadata. Prior BLOBs remain append-only. Live SEC ETag support remains unverified; no external SEC request was made.
- **Inline XBRL evidence:** `disclosure_lightning/xbrl.py` reads only SHA-pinned stored bytes. It preserves unnormalized `nonFraction`/`nonNumeric` lexical values, context/unit trees and period, namespace-independent element recognition, scale/sign/format and line hints. Missing/ambiguous references remain UNKNOWN; continuation, fraction facts, parser limits and other unsupported elements prevent a complete-extraction claim. No financial or issuer authentication.
- **KIC consumer evidence:** GitHub `lead/kic` fetch returned exact `proofinvest/dl_bridge.py` blob `8a1d9db7454b4577b95907e4841152542abd2d6b` and `proofinvest/dl_source_span.py` blob `d1fb052b77b9bac9bee914f838702ef080bdff34`; local Git blob IDs matched. A synthetic **DL CLI → SQLite → `read_original_bytes` → extracted citation → exact KIC byte-span → KIC crosslink** test passed (2/2 scenarios), with source/authenticity/numeric-fact flags remaining false. Separate command replay returned `REUSED`; list commands returned `READ_ONLY`; extraction emitted the pinned SHA and byte offsets with `financial_claim_verified=false`. Reproduction scripts/logs: `work/kic-contract/run_contract.py`, `work/kic-contract/run_cli_e2e.ps1`, `work/logs/kic-current-consumer-e2e-20261028-v2.log`, `work/logs/dl-cli-synthetic-e2e-20261028.log`.
- **Verification:** focused core/original/extract/XBRL suites **137 PASS / 3 SKIP**; current KIC consumer CLI integration **2 PASS**; `git diff --check` PASS. On exact code SHA `83ac07e`, full local unittest: **455 run, 1 FAIL, 7 ERROR, 6 SKIP**; the one synthetic UI subprocess failure and all seven errors are due to `ModuleNotFoundError: streamlit`. `verify_local.py --full` is FAIL with syntax/core/CLI checks PASS and full tests FAIL. CI has no checks yet; do not treat local full suite as source-green.
- **Next:** expand the XBRL synthetic matrix for malformed contexts, varied raw units, multiple periods, and unsupported Inline XBRL constructs; preserve raw values and explicit incomplete states without conversion. No KIC branch edits, live SEC or financial certification.

---

- **Code SHA:** recent P10 `2a0b26f21e30398c7afa7471d8fb5cec1ddf12e5`; history P10 `601d3b75cc409fe4cbb131068935537aa8a7fad2`; tests `7652716a869a498ac9aac2d271a16b7795a59e77`. Subsequent docs HEAD separately confirmed.
- **Bug/gate:** When SEC-shaped recent/history filingDate == observation UTC day and parsed timezone-aware accepted_at is **None**, exclude row, not invent time or imply observed-before-acceptance. Existing P9 timestamp comparison remains for known valid offsets. No SQLite schema mutation, no KIC bridge/UI modification.
- **Actual tests:** Existing independent *prior P6 local contract shim* suite 9/9 PASS, six standalone P10 exact predicate cases PASS; neither proves current remote full repo CI. Two in-repo P10 regression tests written but **NOT independently run on exact source**. GitHub Actions status queries for DL head do not enumerate push runs; GH site direct fetch/container git unavailable (DNS/DisabledError). This is a verification blocker, NOT a successful run.
- **KIC boundary:** Your independent iXBRL source report and 461/461 previous `lead/kic` CI are separate; do not attribute to DL. PR #1 remains draft/unmerged; do not accept unsignaled KIC changes or original/financial truth claims.
- **Next:** Independently run full GitHub tests for exact DL source, repair real failures, then narrow diff review/integration. Nov12 PDF-only prelim and DAKER controls untouched.

---

# DL P9 chronology correction → KIC lead (2026-10-28 KST)

- **Source SHA:** `core.py@ac68ea911adb59c2c31a2d7cf2921d064037b42b`, `history.py@dedffd7c8e6a7c4f27eb2f91a7c509d3320af90f`; tests `tests/test_disclosure_lightning.py@ec39e85516426e82a65f2187825844b8a677dac0`. Successor handoff HEAD verify after all writes.
- **Bug fixed:** Index now rejects time-aware `acceptanceDateTime` **later than actual UTC observation instant**, even when filingDate equals observation UTC day; included for both recent Submissions and historical continuation. Existing day/as-of filtering and stored byte receipts untouched. No root/SQLite migrations.
- **Tests authored:** 2 synthetic regression cases (UTC offset boundary 02:59:59 vs 03:00:00, deferred historical acceptance before batch write). **Exact source full unittest CI NOT VERIFIED**. Container only has earlier P6 contract shim, not authenticated full checkout; GitHub combined status/PR workflow API returns no new results. Do not accept `0 statuses` as green.
- **Integration:** KIC `lead/kic` has separate offline iXBRL work and source contract; no KIC files mutated, no live SEC or private originals, no DAKER/PDF change, PR #1 remains draft/unmerged. Next full CI, then narrow KIC acceptance/time contract review.

---

# DL P8 → KIC lead | 2026-10-28 KST

- **Source SHA:** `feature/disclosure-lightning` amendment review core commit `5724fedddd09519cce0e199bcc443903f255e6e5`, CLI commit `34308fe31368b53986498ba0b1c202b40e9c431a`, source-scan budget `543796a9494227f53f2bba6199f23b3062e7f13c`; 5 new existing-test-module cases through `8c05c64f0792ed28dbe150f705d91fa471061daa`. Docs successor HEAD to verify after writes.
- **Change:** `disclosure_lightning/history.py:review_amendment_candidates` offers read-only candidate analysis based on hash-verified stored SEC-shaped reportDate/form/CIK/earlier filingDate, bounded by source scan and independent cutoff chronology. Unique candidate is expressly `UNVERIFIED_PERIOD_MATCH_CANDIDATE`, ambiguous/missing cannot infer. `authoritative_amends_accession` is always null; **no mutation of original `amends_accession`**.
- **KIC status:** Latest `lead/kic` source advanced, independently owned KIC numeric literal and local report APIs [447 PASS](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40543770115) at older source `cfb39bbb`; this is not P8 validation. DO NOT overwrite KIC bridge or interpret untrusted period matching as source/financial truth.
- **Verification:** Five written P8 regression methods; full exact-branch Actions and runtime unittest **NOT VERIFIED**. Next independently run `python -m unittest discover -s tests -v`, review CLI JSON, request KIC chief code review before merging any PR. No SEC live, DAKER, public sensitive bytes or Production.

---

# DL → KIC lead P7 multi-page offline history (2026-10-28 KST)

- **DL feature branch:** `feature/disclosure-lightning`. P7 code commit `f5fd0ac85c1283730d899a7f41cb3d75c0773790`, safe `_read_local` continuation `fc5f875aac0701cd495e5303b7f8f7dc1f78c44a`, tests through `99bf4983d055fbc581ebda394a527c4df7da434c`. Root doc successor SHA separately verified after writing.
- **Implemented:** `list_manifest_pages`, `import_history_batch`, `import_history_directory` plus `--list-manifest` / `--batch-dir` CLI. Existing `history.py` and `core.save_index` schema unchanged. Max 8 local pages, bounded bytes, all-input preflight, cross-page accession collision detection, idempotent replay with explicit partial-write recovery. No network, no new dependencies, new API credits zero.
- **Tests:** five new actual repository regression methods added, covering two-page save/replay, rejected malformed second page without writes, directory/cap, partial-write recovery, CLI discovery and rerun. **New repo-wide GitHub CI: UNVERIFIED**; connector returns zero commit-status entries and PR-only workflow lookup is not exhaustive. Not a claim of PASS/FAIL.
- **Boundary:** SEC URL names and manifest provenance remain unverified local records. No live issuer HTTP, no official original filing byte authentication, no automatic amendment-parent inference or portfolio signals. KIC Streamlit and `proofinvest/dl_bridge.py` untouched; draft PR #1 remains not merged. Prior independent KIC `lead/kic` head advanced beyond prior reports; review current SHA before any integration.
- **Next KIC decision:** Reconcile draft PR #1 with already-accepted KIC integrations, independently verify P7 full CI and contract. Do not automatically overwrite KIC bridge. Nov12 PDF-only preliminary and DAKER authorization unchanged.

---

# DL P6 → KIC lead (2026-10-28 KST)

- **코드:** `feature/disclosure-lightning@98ae2496264e5356f79e2fe7b6bd14796d99fea6` `disclosure_lightning/history.py` 추가; 테스트: `tests/test_disclosure_lightning.py` 새 regression. 현재 테스트 포함 커밋 `4dedf4259c907eba6b15b69428bce1c5a1cda13b`.
- **제공 계약:** 기존 `core.save_index` 동일 SQLite schema / 관측 원본 JSON SHA256 유지, `filings.files[].name` + pinned main snapshot 확인 후 선택된 과거 history JSON만 오프라인 인덱싱. raw original filing SHA는 null, external authenticity는 NOT VERIFIED. `indexed.filings[]` 스키마 1.0 유지.
- **검증:** 별도 핵심 코어 shim 통합환경에서 9/9 오프라인 테스트 통과. GitHub repo 전체 테스트·GitHub Actions 결과는 **미검증** (commit status endpoint no statuses). 새 파일 생성 테스트 작업은 2회 안전 검사 차단, 기존 `tests/test_disclosure_lightning.py`에 테스트 삽입 방식으로 전환해 커밋 성공. 본선 제출/SEC live/unmerged PR #1 영향 없음.
- **다음:** 실제 전체 CI 확인, manifest에서 과거 페이지 로컬 발견 출력, 다중 페이지 범위 QA 및 승인된 User-Agent가 준비된 뒤에만 명시적 단건 SEC HTTP 전송 검토. KIC 보고서·Streamlit·dl_bridge는 KIC 소유라 변경하지 않았습니다.

---

# DL → KIC lead P5 receipt (2026-10-28 KST)

- **DL branch/code SHA:** `feature/disclosure-lightning@8cd8e12d50dc1a9243e167a93d048786965efc8c`; three new `tests/test_disclosure_lightning_extract.py` regression methods. Local standalone extracted-helper test 8/8 pass; full-repository GitHub Actions results **not verified**. Last independently recorded full CI P3: [390 PASS #40534506681](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681).
- **Contract update:** `extracted-text.v1` adds `decoded_encoding`, `html_meta_declared_charset`, `charset_claim_verified=false`. Parse `text/html` declared UTF-8/Windows-1252/ISO-8859-1 strictly; reject nondeclared undecodable, ambiguous BOM, unknown charset. No HTML raw-byte spans or numerical authenticity. P4 raw UTF-8 line-byte offsets remain available.
- **KIC coordination:** Read `lead/kic@e1c94598` direction [#40537627902](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40537627902) **408/408 offline** for KIC's synthetic citation UI. No DL modifications to KIC `streamlit_app.py`, `dl_bridge.py`, `dl_source_span.py`, main or preliminary PDF. Draft PR #1 remains unmerged due overlapping accepted prior bridge.
- **Blocker:** DNS cannot resolve github.com in sandbox clone; use GitHub connector for commits, local helper exercise only, CI exact-branch pending. No live SEC contact without valid owner-authorized identification/fair access. Next = CI, historic SEC continuation, then reviewed integration.

---

# DL → KIC lead | P4 UTF-8 text byte spans (2026-10-28 KST)

- **Branch/code SHA:** `feature/disclosure-lightning@8253270db5cf309d963cc76d9b1569389a34c8d8`; post-commit full Actions CI **unverified**, prior P3 390 PASS [#40534506681](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40534506681).
- **Files:** `disclosure_lightning/extract.py`, `tests/test_disclosure_lightning_extract.py` (three additional tests). Exact source locator `start_byte`/`end_byte_exclusive` + line `raw_span_sha256` for hash-checked local UTF-8 text lines; BOM, CRLF, Unicode and long-line truncation handled. HTML remains LINE_HINT_ONLY; full-document and financial/issuer authenticity remain **false**.
- **Contract:** extracted-text.v1 additive per-block locator keys, field names aligned with KIC `proofinvest/dl_source_span.py`; consumer integration is **not automatically assumed**. No live SEC, no Production, no PDF edits, no lead/kic/main merge. Retain draft PR #1 pending independent KIC review.
- **Next:** CI verification, KIC approval of explicit raw-span consumer, then secure encoding fallback / multi-page SEC continuation. Last KIC instruction read from `lead/kic/docs/disclosure-lightning/TO_DL_LEAD.md` and review ledger (401/401 offline at KIC earlier source).

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

# DL → KIC technical chief — ORIGINAL FILE ARCHIVE P2, 2026-10-28 KST

**Branch:** `feature/disclosure-lightning`, **code SHA:** `89cd9024e304b465447936ad58d2de407f2dbe9c` before subsequent documentation. [GitHub CI #40532494845](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40532494845) **SUCCESS, 373/373 Python tests** including 15 DL original-file tests. Docs are committed after the tested code; the latest HEAD should be CI-checked separately.

## Implemented, not just documented

- Canonical SEC metadata module `disclosure_lightning/core.py` remains unchanged, one SQLite schema; added **separate** `disclosure_lightning/originals.py` and `tests/test_disclosure_lightning_originals.py`.
- Optional official SEC original HTML/XML/TXT GET is **disabled without explicit `--allow-network` and actual contact-bearing SEC User-Agent**. First obtain official SEC `submissions` metadata in the canonical DL DB; requests based on synthetic/unverified metadata are refused. Every URL is validated against its stored CIK/accession/primary file name, with no arbitrary external URL, redirects/proxy, auto retries or background fetching.
- Both offline caller-supplied synthetic original bytes and simulated SEC HTTP responses can be saved as **exact byte BLOBs with SHA-256**, file size/MIME labels and conservative provenance. Storage is append-only per unique filing/digest; replay deduplicates. `read_original_bytes(db_path,cik,accession,sha256)` retrieves a specific saved original read-only only after re-hashing bytes and detecting corruption. Neither this checksum nor an HTTP 200 means SEC financial claims are authenticated.
- [Detailed reproduction/limits](ORIGINAL_FILE_ARCHIVE.md). Public repo contains NO fetched SEC issuer originals, credentials, private Bid_Owl source or user data.
- **KIC lead independently merged offline P0 end-to-end** via [PR #2](https://github.com/hibi89/hibi89-kic-proofinvest/pull/2) on `lead/kic` (KIC CI 366 PASS per lead review ledger). DL original-files layer here is **NOT YET** part of that merged synthetic KIC path or a report parser. Keep `feature/disclosure-lightning` → `lead/kic` [draft PR #1](https://github.com/hibi89/hibi89-kic-proofinvest/pull/1) unmerged pending schema/security and original-byte KIC consumer review.
- **Actual live SEC response, source authenticity, full filing content receipt, SEC fair-use practical rate test, extended filing history, 429 backoff and future DL→KIC HTML extraction remain unverified**. Only GitHub CI synthetic tests + mock HTTP passed. This feature may not be claimed as production/live at KIC contest prelim.

## Next action and approval gates

1. KIC chief review safe SEC raw-body interface `read_original_bytes`; define narrow allowed consumer for source-span extraction, not numeric certification. Do not confuse `index_raw_sha256` (submissions JSON) with `filing_sha256` (primary document bytes).
2. Only with a valid identifying SEC User-Agent and actual permitted live connectivity, verify ONE official issuer's `submissions` and original filing and capture response metadata in a local-only ledger; then add an end-to-end KIC extraction test.
3. Later add paginated SEC filing history, one-step bounded retry/backoff, source spans, frontend and performance tests. 2026-11-12 KIC PDF-only preliminary remains wholly independent and requires owner approval.

---

# DL → KIC Lead — P1 canonical contract closed, CI verified (2026-10-28 KST)

**Latest verified code:** `303c17bc073be7233e7b4dd836823e4cf2974315` | [CI run #40530744523](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40530744523) **358/358 PASS** (full repository Python tests, including DL producer synthetic KIC issuer/accession/date contract). **GitHub branch:** `feature/disclosure-lightning`. This CI SHA precedes this docs commit.

## P1 resolved
- **ONE canonical runtime:** `python -m disclosure_lightning` → `disclosure_lightning/core.py`. Deleted conflicting experimental `mvp.py`, `cli.py` and their 12 overlapping tests (preserved in history); former CI had 363 tests; newer count is not a regression in actual supported canonical coverage.
- **Chronology gate:** require timezone-aware `collected_at`, normalize UTC, reject observation later than `as_of`; exclude filings dated after observation time. Offline `--collected-at` for honest known timestamps only; caller cannot override live HTTP collection timestamp. A historical offline timestamp **does not establish independent SEC authenticity**.
- **SEC User-Agent gate:** rejects placeholder/example addresses and control characters before attempting network; one-shot bounded GET is explicit opt-in, never background polling.
- **SEC forms:** default scan includes 10-K/A, 10-Q/A, 8-K/A in addition to 10-K, 10-Q, 8-K. Amendments preserved as separate accession IDs; verified parent link is NOT established.
- **Evidence & interoperability:** local immutable original *submissions JSON* BLOB and SHA-256 (NOT original filing HTML hash), SQLite idempotent dedup and read-only list. KIC link-aligned but entirely synthetic Apple fixture `disclosure_lightning/fixtures/kic_apple_handoff_synthetic.json`; producer test verifies identifiers against existing curated ProofInvest verdict without claiming that actual KIC lead bridge is running on this branch. The true consumer `proofinvest/dl_bridge.py` is on lead/kic and needs integrated branch tests AFTER review.
- **Security:** protected previous Bid_Owl private source not transferred; no customer information, credentials, real full SEC filing bytes or original submission PDF; `lead/kic` and `main` unchanged by DL.

**KIC chief review next:** Inspect draft [PR #1](https://github.com/hibi89/hibi89-kic-proofinvest/pull/1) canonical DL producer schema vs existing `proofinvest/dl_bridge.py`. After approval merge or independently test on an integration branch. Do not treat current 358 tests as live-SEC or full-file factual verification. **Still pending:** actual provider HTTP response evidence, 10-K HTML raw original download/hash, historical SEC continuation, KIC end-to-end with bridge, frontend. Nov12 official PDF-only prelim remains independent.

---

# Disclosure Lightning → KIC Lead: MVP implementation and verified CI

**KST:** 2026-10-27 | **Branch:** `feature/disclosure-lightning` | **Source verified SHA:** `2634950dca20caf5687ec12d96542b665faf23d1` (before documentation update)  
**CI:** [GitHub Actions #40526917500](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40526917500) = **PASS, 363 Python tests** (existing KIC suite + all new DL tests), including real module-entrypoint synthetic E2E.

## Actual code and usage

**Canonical DL executable:** `python -m disclosure_lightning` uses `disclosure_lightning/__main__.py` → `core.py`. Input: `--input-json` (local synthetic/SEC-like JSON) OR `--allow-network` (one opt-in authorized SEC HTTPS GET with **real** `DL_SEC_USER_AGENT` contact). Args include `--cik`, `--as-of`, `--db`, `--forms` and `--list`; docs and synthetic fixture at `disclosure_lightning/README.md`, `disclosure_lightning/fixtures/sec_submissions_synthetic.json`. Strict response/CIK/accession/date/source checks; zero dependencies beyond Python 3.11; raw submissions JSON BLOB+SHA256 preserved in SQLite, unique issuer/accession filing index, distinct amendments, duplicate suppression, source-linked JSON export. No frontend/UI.

**Parallel offline-only experiment:** `disclosure_lightning/mvp.py` + `disclosure_lightning/cli.py` and `tests/test_disclosure_lightning_mvp.py` were also committed independently on this same branch. Both implementation sets are source-visible, have separate SQLite schemas and **must not be treated as the same production schema**. Until contract convergence, the standard entrypoint is the canonical `python -m disclosure_lightning` command above, and `python -m disclosure_lightning.cli` is secondary experimental offline CLI. Do not mix the two SQLite database files. A later small contract consolidation/cleanup is needed **before merging to KIC lead**.

## Verified, unverified, and KIC decision

- **Verified:** official-shaped **synthetic** SEC recent array parsing with cutoff/form filters, aligned columns, invalid input refusal, source response SHA256, append/preserve SQLite behavior, idempotent replay, user-selected local output, original source URL construction, HTTP transport shape with mocked response, CLI subprocess; 363 KIC/DL full tests PASS in GitHub CI on `2634950dca20caf5687ec12d96542b665faf23d1`.
- **Not verified:** SEC live network requests, actual SEC data authenticity, full original 10-K/10-Q/8-K HTML/PDF content retrieval or hash, paginated submissions, amendment ancestor identification, periodic sync, multi-region sources, end-user Windows usability, frontend, real KIC ProofInvest schema consumer/integration. DL's `index_raw_sha256` hashes **submissions JSON**, never filing HTML; `raw_sha256=null` for original filing. Do not report live SEC evidence or full-file certification.
- **KIC action requested:** Review contract and duplicate parallel modules, confirm a canonical RawFilingEnvelopeV1 recipient structure, keep Nov12 official PDF unchanged. Existing preliminary freeze applies; this DL feature branch is isolated. No `lead/kic`, `main`, private Bid_Owl, production, real credentials or PDFs modified. No fee incurred for new SDK/services.
- **Next P1:** independent compliant real SEC 1-issuer/one-request validation with the owner's actual legal contact-bearing User-Agent and documented official payload, then optionally original filing bytes and hash, followed by ProofInvest adapter contract tests and frontend later. Never represent scheduled background work.

**Review protocol:** Draft PR `feature/disclosure-lightning` → `lead/kic` only; NO auto-merge until KIC chief resolves dual MVP code/schema review and external provider acceptance gates.
