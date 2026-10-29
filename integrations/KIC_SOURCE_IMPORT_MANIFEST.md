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

## Remaining ordered gates

1. Link offline vendor DL candidate output into the existing ProofInvest review/report path without treating text as verified numeric facts.
2. Validate DL source-to-Guard-to-SQLite audit in a single tested end-to-end flow, with explicit human review only.
3. Complete reporting/UI presentation and runnable local demo on the intended target machine.
4. Selectively integrate AutoML only after chronological evaluation, leakage controls, and baseline tests.
5. Produce and independently check the official 10-page preliminary PDF; final submission is a separate owner approval gate.

**Completion measurement (integration workstream only):** 4 of 8 explicitly scoped milestones complete (branch/source, compatibility isolation, offline Guard bridge, full CI/regression verification) = **50%**. This is not a claim that the entire KIC hackathon product is 50% done. Previous **84%** on lead/kic was a provisional estimate for the main implementation only, not final E2E or submission readiness.
