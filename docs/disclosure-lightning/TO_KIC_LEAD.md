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
