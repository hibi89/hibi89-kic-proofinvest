# KIC integrated-components provenance and verification

Updated 2026-10-30 KST. Working branch: `feature/kic-integrated-components`.
Base: `lead/kic@2394d18e0ae3e7e17f5e77f30b0b62e5e3694ca0`.
No mutation to `lead/kic`, `feature/disclosure-lightning` or the AutoML source repository.

## Source boundaries

- **Original KIC engine unchanged**: `disclosure_lightning/core.py` and `originals.py` were restored byte-for-byte from `lead/kic` after the first direct overlay caused CI regressions. Existing `proofinvest/dl_bridge.py`, Guard and SEC pipeline remain in place.
- **Complete newer DL source**: `integrations/dl_vendor/` contains the pinned `feature/disclosure-lightning@760ddd3a0e4ad5814e76146c0d536bebc4520f81` package (core, originals, companyfacts, extract, history, xbrl, fixtures and CLI) under an isolated Python namespace.
- **DL regression suites**: original reference tests preserved under `integrations/dl_vendor/reference_tests/`; ported, runnable tests under `tests/test_kic_dl_vendor_{companyfacts,extract,xbrl}.py`.
- **Optional AutoML reference only**: `integrations/automl_source/evaluator.py` and `model_selector.py` came from `hibi89/AI_AutoML_Analyst` main at fetch time; commit was not pinned. Not wired into runtime. Time-series chronology and leakage validation are outstanding.
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

1. Independently validate the new UI on the owner's intended Windows machine (CI Chromium completed; Windows remains unverified).
2. Integrate only needed AutoML capability after chronological evaluation, leakage controls, baselines, and evidence-scope checks.
3. Produce and independently check the official <=10-page preliminary PDF before 2026-11-12 10:00 KST; final submission requires separate owner approval.

**Completion measurement (integration workstream only):** **5 of 8 = 62.5%**; main branch's previous **84%** implementation estimate is separate and preliminary. No current evidence for a measured total KIC product completion percentage.
