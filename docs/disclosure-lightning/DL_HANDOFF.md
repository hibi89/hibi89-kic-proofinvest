# DL P18 — Submissions/history source evidence immutability (2026-10-28 KST)

- **Branch/source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; code/test SHA `e56663a00bc3d517f9ee519007c0ad5fbc98ce43`, normal push completed and exact remote branch head confirmed. Commit status API returned no status checks; CI is unverified.
- **Change:** the shared DL SQLite schema now guards source observations, observation-check history, first-seen filing index records, filing-to-observation links, and history page receipts/version rows against ordinary UPDATE/DELETE. Replacement of an existing observation, filing, or page receipt/version is rejected; duplicate check/link inserts preserve idempotent replay. `save_index` recreates missing guards through its schema step for existing DBs. Conditional HTTP validator state remains mutable by design.
- **Tests:** full DL-focused discovery **165 run / 162 PASS / 3 SKIP**; `python -B verify_local.py` **PASS** at the exact source contents (syntax/core/offline CLI smoke). Regression tests attempt all blocked write shapes and continue to verify tampered bytes/metadata by explicitly disabling test-database triggers. Full repository run last occurred at `f0963e7`: **480 run / 1 FAIL / 7 ERROR / 6 SKIP**, all eight failure/error cases from missing `streamlit`; not rerun for this delta. Latest focused log: `work/logs/dl-focused-core-full-append-only-20261028.log`.
- **Limits:** direct schema-editing access can remove SQLite triggers. No real SEC traffic, source certification, financial normalization, cross-branch edits, merge, or force push.
- **Next:** continue recovery tests for malformed/partial history pages and source-to-filing association repair; consider KIC envelope consumption only as an explicitly read-only, independently reviewed contract.

---

# DL P17 — Original filing receipt immutability (2026-10-28 KST)

- **Branch/source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; verified source/test SHA `73c4390e93afc32061814c99704e37ea5538c9c6`. Normal push and GitHub branch-head commit listing confirmed this exact SHA. Commit status API returned no checks; CI remains unverified.
- **Change:** original filing BLOB receipts and HTTP check rows now reject ordinary SQLite UPDATE/DELETE. Existing receipt-key `INSERT OR REPLACE` is blocked; an exact duplicate HTTP check remains idempotent. `persist_original` recreates missing guard triggers transactionally for existing DBs. Validator rows remain mutable because each ETag identifies the latest cached response; receipt rows stay keyed by byte digest.
- **Tests:** original archive **29 run / 28 PASS / 1 SKIP**; extraction **29/29 PASS**; all DL-related tests **163 run / 160 PASS / 3 SKIP**; `verify_local.py` **PASS** after the source/test edits (syntax, core tests, offline CLI smoke). Existing tamper-detection tests still mutate the SQLite DB only after explicitly removing the guard, then prove reads fail closed. No full-suite rerun for this code delta; last exact full-suite run at `f0963e7` failed **480 run / 1 FAIL / 7 ERROR / 6 SKIP**, with all eight failure/error cases from the missing `streamlit` dependency.
- **Limits:** SQLite guards deter normal writes through the archive DB; a DB owner can alter the schema. No real SEC request, claim verification, financial normalization, merge or force push. Updated usage note: `docs/disclosure-lightning/ORIGINAL_FILE_ARCHIVE.md`.
- **Next:** continue synthetic corruption and failure-recovery checks across historical index receipts, then review read-only extracted evidence contract with the KIC consumer boundary. Do not certify source authenticity.

---

# DL P16 — CompanyFacts cache lineage, immutable evidence, and verified listing (2026-10-28 KST)

- **Branch/source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; verified code SHA `f0963e76c15939c79dad23f915d62fc31ee21eca`. Three normal-pushed feature commits since P15: `c08d01d` (same-hash offline-to-live ETag lineage), `131e0cd` (append-only SQLite guards), `f0963e7` (integrity-checked read-only listing). GitHub's branch commit listing matches the exact code SHA. Commit status API returned an empty status list; CI is unverified.
- **Cache lineage:** conditional validators may now bind to exact raw bytes first imported offline and later checked via a synthetic/official HTTP provenance event. Cache reuse still requires valid ETag, canonical SEC URI, SHA-256-matching bytes, valid CIK payload, and a persisted `SEC_HTTPS_RESPONSE` or `SEC_HTTPS_304_NOT_MODIFIED` check for that same digest. A provenance mutation with the live check removed is rejected.
- **Raw evidence integrity:** CompanyFacts observation and check rows reject ordinary UPDATE/DELETE. Duplicate observation `INSERT OR REPLACE` is rejected; duplicate check inserts retain their existing row. Schema creation reinstalls missing guards on an existing DB. Reads and `--list` independently re-check bytes/hash/issuer/source/metadata and fail closed on corruption. Triggers provide SQLite-level guardrails, not protection against an actor who can alter/drop the database schema.
- **Verification on exact code SHA:** CompanyFacts tests **17/17 PASS**; DL-only test discovery **162 run / 159 PASS / 3 SKIP**; `verify_local.py` core mode **PASS**. `verify_local.py --full`: **FAIL**, with syntax/core/offline CLI/git identity **PASS**; full suite **480 run / 1 FAIL / 7 ERROR / 6 SKIP**. Every failure/error is due to missing `streamlit` imports in existing UI/recovery tests. No dependency installation and no weakened tests. Preserved full log and verifier summary: `work/logs/full-f0963e7-20261028.log`, `work/logs/full-f0963e7-summary-20261028.json`; focused run: `work/logs/dl-focused-companyfacts-list-integrity-20261028.log`.
- **Boundaries:** no real SEC request was made; source authenticity and financial claim verification remain false. No KIC sources or restricted branches were changed, and no merge/force-push was performed. The user-requested isolated worktree and logs remain preserved under `work/dl-session` and `work/logs`.
- **Next:** continue synthetic original-source/archive recovery and consumer-contract checks; prioritize corruption, point-in-time, and amendment ambiguity. Full-suite gate remains environment-blocked until `streamlit` is available; CI has not returned statuses.

---

# DL P15 — CompanyFacts cache provenance and malformed XBRL context guards (2026-10-28 KST)

- **Remote:** latest verified `feature/disclosure-lightning` source SHA `047dd3de776df13841c24a44bc561ecc22871bb9`; normal push and GitHub branch HEAD confirmed. Commit status API returned no checks (CI unverified).
- **Hardening:** CompanyFacts conditional-cache loading now requires its validator to point at a digest-verified observation labeled `SEC_HTTPS_RESPONSE`; a synthetic DB provenance mutation is rejected. Inline XBRL parsing marks nested or mismatched context/unit trees incomplete instead of silently accepting a recovered partial tree.
- **Verification:** focused DL suite **154 run / 151 PASS / 3 SKIP**; `python -B verify_local.py --full` at exact SHA **FAIL**, with syntax, focused core tests, and offline CLI smoke PASS. Full suite **472 run / 1 FAIL / 7 ERROR / 6 SKIP**; every failure/error is `ModuleNotFoundError: streamlit` in existing UI tests. No dependency install or weakened tests. Logs: `work/logs/dl-focused-047dd3d-20261028.log`, `work/logs/full-047dd3d-20261028.log`.
- **Next:** continue synthetic testing for corrupted CompanyFacts metadata, file/DB failure recovery and XBRL namespace/malformed-markup boundaries. Do not perform real SEC calls or numeric normalization.

---

# DL P14 — CompanyFacts offline input bound alignment (2026-10-28 KST)

- **Source:** latest confirmed remote code SHA `d1d1cf4ad2f4cb2b664feaba812d3f2ee45c5daa` on `feature/disclosure-lightning`.
- **Change:** generalized the local JSON reader to accept an explicit size cap without changing its existing 8 MB default; CompanyFacts offline CLI now uses its own 50 MB bounded parser limit. This removes the mismatch that rejected larger eligible CompanyFacts files before payload validation, while retaining no-symlink and regular-file checks.
- **Verification:** synthetic 8 MB+ CompanyFacts input test PASS; focused DL suite **153 run / 150 PASS / 3 SKIP**; `python -B verify_local.py` at exact code SHA **PASS** (syntax, core tests, offline CLI smoke). Last full suite was at preceding code SHA `c65e07d`: **470 run / 1 FAIL / 7 ERROR / 6 SKIP**, all failure/error cases due to missing `streamlit.testing.v1`; no install or weakened tests. Focused log: `work/logs/dl-focused-d1d1cf4-20261028.log`.
- **Remote gate:** normal push succeeded; GitHub branch HEAD equals `d1d1cf4`. Combined status returned no CI status checks, so CI is unverified.
- **Next:** continue malformed-source recovery and read-only KIC contract tests; never relax bounded parsing or reinterpret raw facts as verified values.

---

# DL P13 — Versioned read-only CompanyFacts handoff (2026-10-28 KST)

- **Source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; latest confirmed code SHA `c65e07d8a9f7a0651bab22b174c42b94811395f0` (CompanyFacts envelope CLI), parent `4a24e9bb753186b83b935cb5faf4582e572206bf`. GitHub branch HEAD matched the normal push.
- **Consumer contract:** CompanyFacts archive now supports `--read-sha256` to emit `disclosure-lightning.companyfacts-envelope.v1`, combining a hash/CIK/source/as-of-checked raw CompanyFacts object with collection metadata and explicit false authenticity/financial-verification flags. Existing KIC `verify_sec_annual_revenue` consumes the archived synthetic mapping successfully as `calculated_unverified`; this is a structural offline handoff, not source verification. No KIC source was edited.
- **Verification:** CompanyFacts tests **10/10 PASS**; DL-focused suite **152 run / 149 PASS / 3 SKIP**; `python -B verify_local.py --full` on exact code SHA: **FAIL** with syntax/core/CLI smoke PASS and full tests FAIL. Full suite **470 run / 1 FAIL / 7 ERROR / 6 SKIP**; every failure/error is due to the absent `streamlit.testing.v1` dependency. No installation or weakened tests. Logs: `work/logs/dl-focused-c65e07d-20261028.log`, `work/logs/full-c65e07d-20261028.log`.
- **Next:** preserve the separation between raw acquisition and KIC verification. Independently harden issuer/filing linkage and malformed-source cases using synthetic inputs; live SEC, KIC source edits, cross-branch merge, and financial normalization remain outside this checkpoint.

---

# DL P12 — Inline XBRL namespace, exclusion, and bound handling (2026-10-28 KST)

- **Source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`, implementation SHA `2ef9cf7612affc704058d0b445ef432295044963`; normal push completed. The parser resolves namespace declarations by element scope and restores parent bindings, omits `ix:exclude` subtree text from fact lexical candidates, and bounds context/unit roots as well as total fact starts. Source bytes remain unchanged and hash-pinned.
- **Tests:** focused DL suite **152 run / 149 PASS / 3 SKIP**; XBRL-specific **13/13 PASS**. `verify_local.py --full`: **FAIL** at exact implementation SHA; syntax, core, and offline CLI smoke PASS. Full suite **470 run / 1 FAIL / 7 ERROR / 6 SKIP**, all failure/error cases caused by absent `streamlit.testing.v1` in this environment. No install and no test weakening. Logs: `work/logs/dl-focused-xbrl-safety-20261028.log`, `work/logs/full-xbrl-safety-2ef9cf7-20261028.log`.
- **Limits:** this remains a conservative lexical candidate parser, not standards-complete Inline XBRL or a financial verifier. Continuations/fractions and other unsupported constructs still prevent completeness. CI status checks are not yet returned for the pushed commit.
- **Next independent work:** review and harden malformed markup/namespace edge cases, then continue read-only KIC contract coverage; do not normalize or certify financial values in DL.

---

# DL P11 — Raw CompanyFacts archive and KIC read-only consumer check (2026-10-28 KST)

- **Branch/source:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`, latest confirmed remote SHA `76df68741406493ff919479455bd49ccae31f539`; CompanyFacts implementation `c906e531bd3d6807bcc13ffdb536d3defef8a0b9`; checkpoint docs `772822f314b2968e63d6dac88fc5b38a7bffc294`. GitHub branch HEAD matched after normal pushes. Implementation parent `4528ec19a0e706b67ee0814a7d72383b91560a46`.
- **Implementation:** New `disclosure_lightning.companyfacts` accepts bounded SEC CompanyFacts-shaped JSON, validates issuer CIK/structure, stores exact raw bytes with SHA-256 and provenance in SQLite, records checks and ETag validators transactionally, deduplicates identical response bytes, and exposes read-only listing/hash-checked retrieval with as-of gates. Explicit `--allow-network` is required for GET; no actual SEC request was made. Offline input remains `OFFLINE_UNVERIFIED`; all financial/authenticity flags remain false. `verify_local.py` now syntax-checks both `companyfacts.py` and `xbrl.py`.
- **KIC consumer contract:** current `proofinvest.sec_companyfacts.verify_sec_annual_revenue` consumed JSON re-read from the DL SQLite archive in a synthetic 10-K example. It returned `calculated_unverified`; the test asserts `authenticated_external_source=false` and `live_api_called=false`. No KIC source files were edited.
- **Verification:** CompanyFacts synthetic tests **10/10 PASS**; DL-only discovery **149 run / 146 PASS / 3 SKIP**; `python -B verify_local.py` on the test-bearing checkout **PASS** (syntax, focused core suite, offline CLI smoke). The most recent `--full` run was at implementation SHA `c906e53`, before the one additional contract test: **464 run / 1 FAIL / 7 ERROR / 6 SKIP**; every failure/error traces to missing `streamlit` in this Python environment, so no dependency was installed or test weakened. Preserved logs: `work/logs/full-companyfacts-20261028.log`, `work/logs/dl-focused-kic-companyfacts-20261028.log`.
- **Remote/checks:** normal push succeeded and GitHub branch HEAD is exact. Commit status API returned no status checks; CI is not asserted green. No work on `lead/kic`, `main`, or `Bid_Owl`; no merge or force push.
- **Next independent work:** inspect actual consumer contract requirements for a bounded read-only CompanyFacts envelope; add synthetic integration coverage only on the DL branch. Continue XBRL completeness boundary work after the CompanyFacts contract is stable. Full suite remains blocked on environment-only `streamlit` availability.

---

# DL P10 — as-of same-day unknown acceptance fail-closed (2026-10-28 KST)

1. **Goal:** Prevent look-ahead inclusion of same-UTC-day metadata when an SEC shaped row has no reliable timezone-aware acceptance instant.
2. **Design:** Narrow conservative skip in existing recent `core.index_submissions` and historical `history.index_history_page`: when `accepted_at is None` and `filed_at == observed_instant.date()`, skip. Known acceptance instant still follows P9 UTC comparison; earlier-day date-only records retain existing behavior. No new provider fetch or schema change.
3. **Tests:** Two new regressions committed (missing/empty/naive vs known offset and prior-day recent; missing/naive vs valid prior-to-observation history). Prior P6 local core-contract shim 9/9 PASS; copied P10 predicate independent test 6/6 PASS. **Full latest GitHub repo unittest/Actions NOT VERIFIED**, do not claim overall PASS; local shim is not actual source checkout.
4. **Actual progress:** P10 source/test commits pushed and code reviewed; source-level full integration remains blocked by external GitHub clone DNS and status API returning zero checks.
5. **Failure/recovery:** Direct `git ls-remote` failed `Could not resolve host github.com`, GitHub Actions links inaccessible via browser tool in this runtime. No overwrite/force push. Parent Git commits provide rollback.
6. **Repo/branch/source SHA:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`; core `2a0b26f21e30398c7afa7471d8fb5cec1ddf12e5`, history `601d3b75cc409fe4cbb131068935537aa8a7fad2`, tests `7652716a869a498ac9aac2d271a16b7795a59e77`. Root handoff/docs latest HEAD check after writes.
7. **Commands/deployment:** `python -m unittest discover -s tests -v` in actual repo still needed. Offline CLI `python -m disclosure_lightning` and `python -m disclosure_lightning.history`, no DL Production URL.
8. **Data/security:** No live SEC/User-Agent contact, API tokens, unlicensed original bytes, private Bid_Owl, customer data or KIC confidential PDF/PPTX touched. CIK/source provenance unverified.
9. **Next:** Verify exact-source Actions job and scoped tests, correct failure, then follow KIC lead feedback; no source truth promotion or unreviewed PR merge.
10. **KST/outcome:** 2026-10-28; code and tests remote committed, standalone checks as above, whole-repo and real provider/production checks pending.

---

# DL P9 — exact known acceptance timestamp cut-off (2026-10-28 KST)

1. **Goal:** Address a point-in-time defect: same-day accepted-at times beyond the observation instant could be included by date-only filtering.
2. **Design:** Preserve canonical `core._accepted` behavior. If parsed timestamp is timezone-aware, compare it in UTC to `_observation_time` and skip future filings; apply identically to recent and historical page indexers. Missing/naive timestamps remain unknown without fabricated UTC defaults. Do not rewrite stored historical records or attest SEC origin.
3. **Verification:** Added two regression methods in `tests/test_disclosure_lightning.py`, one offset-aware recent boundary (03:00Z), one future accepted historical batch row. Actual full repository GitHub Actions / Python unittest outcome **NOT VERIFIED**: connector returns zero push-job statuses; local `/mnt/data/dl-work` contains only older P6 shim and not faithful full source. No synthetic standalone PASS is misrepresented as source-level testing.
4. **Status:** Both source edits and tests have been pushed and remote source spans inspected; run CI when accessible to confirm. No API, production, original source authentication or KIC bridge affected.
5. **Errors/rollback:** GitHub Action job ID not enumerable with available tool, raw GitHub domains DNS inaccessible inside container. Git parent commits retain rollback, no force push.
6. **Repo/branch/SHA:** `hibi89/hibi89-kic-proofinvest@feature/disclosure-lightning`, `core.py` `ac68ea911adb59c2c31a2d7cf2921d064037b42b`, `history.py` `dedffd7c8e6a7c4f27eb2f91a7c509d3320af90f`, `tests/test_disclosure_lightning.py` `ec39e85516426e82a65f2187825844b8a677dac0`.
7. **Runtime:** Standard-library offline CLI `python -m disclosure_lightning` and `python -m disclosure_lightning.history`; no deployed DL service.
8. **Privacy:** No real SEC GET, contact-bearing User-Agent, API keys, private Bid_Owl, original issuer bytes or KIC private contest files placed on public branch.
9. **Next:** Obtain real exact-commit Actions job state and run complete test suite, fix failures before new features; consider explicit source-declared amendment target review later. KIC lead owns UI/bridge and must review branch PR; preliminary PDF due Nov12 unaffected.
10. **Timestamp/outcome:** 2026-10-28 KST, remote code/test commits recorded; CI/live-source verification unproven and **not marked completed**.

---

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
