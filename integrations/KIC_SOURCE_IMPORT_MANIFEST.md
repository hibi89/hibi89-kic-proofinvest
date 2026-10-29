# KIC integrated-components provenance and verification

Updated 2026-10-30 KST. Working branch: `feature/kic-integrated-components`.
Base: `lead/kic@2394d18e0ae3e7e17f5e77f30b0b62e5e3694ca0`.
No mutation to `lead/kic`, `feature/disclosure-lightning` or the AutoML source repository.

## Source boundaries

- **Original KIC engine unchanged**: `disclosure_lightning/core.py` and `originals.py` were restored byte-for-byte from `lead/kic` after the first direct overlay caused CI regressions. Existing `proofinvest/dl_bridge.py`, Guard and SEC pipeline remain in place.
- **Complete newer DL source**: `integrations/dl_vendor/` contains the pinned `feature/disclosure-lightning@760ddd3a0e4ad5814e76146c0d536bebc4520f81` package (core, originals, companyfacts, extract, history, xbrl, fixtures and CLI) under an isolated Python namespace.
- **DL regression suites**: original reference tests preserved under `integrations/dl_vendor/reference_tests/`; ported, runnable tests under `tests/test_kic_dl_vendor_{companyfacts,extract,xbrl}.py`.
- **AutoML reference + narrow adapted baseline**: `integrations/automl_source/evaluator.py` and `model_selector.py` are still reference-only; they are NOT imported or run. The separate KIC-authored `proofinvest/temporal_baseline.py` uses only a deterministic train-mean baseline (no sklearn dependency) with strict point-in-time, publication-vintage, rights and train/holdout gates, and returns `NO_TRAIN` for all non-self-authored source data. No live financial data or financial ML fit has occurred.
- **KIC vendor evidence-to-Guard adapter**: `proofinvest/dl_vendor_evidence.py` reads SHA-checked, date-scoped locally stored primary filing bytes via vendor DL, extracts bounded human-review text candidates and passes an unavailable-numeric verdict to the deterministic Guard. Result is **HOLD** and never promotes text to authenticated SEC numeric evidence, approves a trade or calls the network.
- **Integration regression tests**: `tests/test_kic_dl_vendor_evidence.py` covers archived synthetic original -> text candidates -> Guard HOLD, missing evidence, SHA mismatch, cutoff, input bounds, and noncreation of absent SQLite DB.

## Verified CI

- Full GitHub Actions on `57a257e852f12314d5b4b071b68a8cc13922bfba`: run `40904164527` **SUCCESS**.
- Full offline Python verifier: **659 executed, 0 failures, 0 skipped**; 121 syntax checks passed; Guard dedicated stage successful.
- Chromium Guard UI click-through job: successful (this is existing Guard UI; the new DL vendor adapter has **not** been wired into the browser).
- No live SEC queries, source authentication, customer credentials, real financial verification, actual trading, cloud deployment, or contest submission took place.

## Verified offline DL -> Guard -> SQLite -> report

Implemented at `21e23ee349825747b4fb32a74b31f96b213d3d9a`:
- `proofinvest/dl_vendor_audit_report.py`: reads date-pinned SHA-checked DL source, binds a canonical SHA-256 fingerprint of the entire unverified evidence result to Guard's run-id, writes deterministic HOLD to a **separate** SQLite audit ledger, validates the tamper-evident chain, optionally records ACKNOWLEDGE or REQUEST_EXCEPTION human review, then returns a report with source/citation digests and explicit trust limitations. Changed source/search term with identical run-id fails closed.
- `proofinvest/guard_workflow.py`: optional bounded 64-hex `source_evidence_digest` request binding. Existing callers preserve their unchanged behavior.
- `tests/test_kic_dl_vendor_audit_report.py`: verification of persistence, deterministic replay, changed-evidence refusal, source date/digest refusal, forbidden authorization, human-review integrity, audit tamper response and safe Markdown.

CLI added at `8f123a1f189b11c7ec2d0780e0542b03ae2f0f97`:

```bash
python -m proofinvest.dl_vendor_audit_report \
  --dl-db /path/to/existing-dl.sqlite \
  --audit-db /path/to/separate-guard.sqlite \
  --cik 0000320193 --accession 0000320193-25-000079 \
  --sha256 <ACTUAL_SAVED_ORIGINAL_SHA256> --as-of 2025-11-01 \
  --term Revenue --run-id demo-1 --format markdown
```

Requires a real pre-existing **local** DL ledger and its saved SHA; no SEC HTTP is made.

Self-contained synthetic demonstration added at `81607de86557458afe4e5e952415e91f4e56ff1b`:

```bash
python -m proofinvest.kic_dl_guard_demo --format json
python -m proofinvest.kic_dl_guard_demo --format markdown
```

The synthetic demo exercises the actual local ledger, original-file extractor, Guard HOLD, SQLite audit, human acknowledgement and report generation; temporary SQLite files are discarded on exit. **It is NOT a real SEC filing or SEC certification.**

Latest verified CI: `81607de86557458afe4e5e952415e91f4e56ff1b` -> GitHub Actions run `40905577717` **SUCCESS**, full offline Python verifier **675 tests, 0 failures, 0 skipped**, syntax checks **125 PASS**, Chromium Guard click-through **SUCCESS**.

Previous milestone 5/8 at the CLI-only phase is historical; the current scoped integration ledger is **6/8 = 75%** after Streamlit and Chromium verification. Not overall KIC production/submission completion.

## ProofInvest UI integration verified (2026-10-30 KST)

- `proofinvest/dl_guard_ui.py` and `streamlit_app.py` add a new offline DL -> Guard -> SQLite audit/report mode with **explicit run only**. Synthetic demo uses disposable databases; local saved-DL mode requires an existing user-selected DL SQLite ledger, separate audit SQLite, pinned original SHA/as-of and user-supplied run ID. Optional human acknowledgement/exception request is explicit; no simulation authorization, trades, or SEC network.
- The view displays only SHA/citation positions, Guard HOLD, and audit chain integrity, with guarded JSON/Markdown exports; untrusted source HTML is never rendered as trusted Markdown.
- `tests/test_kic_dl_guard_streamlit.py`: five headless AppTest cases covering no implicit writes, synthetic click path, actual saved-DL submit and audit writes, bad SHA failure, and untrusted/forged verdict suppression.
- `scripts/guard_browser_smoke.py`: real Playwright Chromium clicks through the synthetic DL/Guard report mode, confirms HOLD/PASS, verifies that no new record was written into the separate curated Guard ledger, and captures `dl-guard-browser-report.png`. CI archives the screenshot as a public-safe evidence artifact.
- **Verified code SHA** `ebd10935618c74c80ddf51c87557bdb8312c06e6`; GitHub Actions run `40906694316` **SUCCESS**. Full offline Python verifier **680/680 PASS**, no skips, 127 syntax checks, Chromium UI job **SUCCESS** with actual DL Guard screenshot.
- These results demonstrate **synthetic** real browser E2E and local saved-source headless UI only. The owner's Windows environment, independent live SEC provenance, target-machine deployment, AutoML and official organizer PDF remain unverified/not done.

**Integration workstream: 6/8 = 75% complete** (isolation, DL reader, evidence-to-Guard, comprehensive CI, SQLite audit/report, UI/Chromium demo). This is a scoped integration milestone percentage, **not** KIC full product/submission completion. KIC main implementation's earlier provisional **84%** is a different denominator.

## Remaining ordered gates

1. Owner independently validates the new UI on the intended Windows machine (CI Chromium and synthetic UI completed; Windows remains unverified).
2. Owner reviews the latest separate PRIVATE 10-page organizer-template-based PDF and exact proposed title; PDF bytes are not kept in this PUBLIC repository.
3. After explicit owner approval, repeat exact-byte organizer preflight and use authorized DAKER account to submit before **2026-11-12 10:00 KST**; only an actual DAKER receipt can prove submission.

**Historical** 5/8 reflected the prior CLI-only phase. Current integration status and the complete 8-item denominator appear below; the main branch's older **84%** estimate used a different scope and must not be combined.

## Current technical milestone ledger (2026-10-30 KST)

Verified code SHA: `2bfa1717bce9cde45033b95d17594976600a9311` on `feature/kic-integrated-components`.
GitHub Actions full workflow: [40911940757](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40911940757) **SUCCESS**:
Python tests **702/702 PASS, 0 failed, 0 skipped**, syntax **131 PASS**; Playwright Chromium Guard/DL click-through **SUCCESS**.

- 1/8 — Dedicated isolated KIC integration branch and source assembly: **DONE**
- 2/8 — KIC DL baseline contract restored; newer DL package isolated: **DONE**
- 3/8 — Saved original text candidates linked to fail-closed Guard: **DONE**
- 4/8 — Offline source/date/tamper/integration regression verification: **DONE**
- 5/8 — Guard + human review + SQLite hash-chain and report CLI: **DONE**
- 6/8 — Streamlit DL audit view + actual Chromium synthetic click-through: **DONE**
- 7/8 — KIC-authored narrow chronological baseline and synthetic UI: **DONE**; the generic AutoML runtime remains unused. Train-only mean vs future holdout, available-at/revision time gates, date/group controls, actual data NO_TRAIN, no trained ML or prediction. 702 PASS includes these unit/AppTests.
- 8/8 — Exact official PDF reviewed/approved, authorized DAKER submission and receipt: **BLOCKED** (private V6 draft was QA checked offline, but neither user approval nor submission has occurred).

**Verified integration workstream: 7/8 = 87.5% (~88%).** This denominator describes only the eight scoped workstream milestones; it is not KIC production readiness, real SEC authentication, finalist model quality, live deployment or full official contest completion.

Private proposal status: a distinct **V6 owner-review-only** PDF/PPTX was prepared from the organizer-style editable base, 10 pages/10 slides and 258 preserved shape geometries; six historical CI labels were updated from 680 to **702**, to match run 40911940757. Private file bytes and packet remain outside PUBLIC GitHub. Its visual/content and exact-title owner approval, organizer eligibility, authenticated DAKER final upload and receipt are separate unpassed gates. Do not silently change the earlier pinned `scripts/kic_submission_preflight.py` file hash or bypass its refusal of unapproved revisions.

All runs described above are **offline synthetic or manually curated**. SEC filing provenance, lawful live external macro feeds, actual financial ML performance, investment actions, authorized external deployment and user's Windows runtime remain unverified.
