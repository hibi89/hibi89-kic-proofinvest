# P301 — KUODRA predeclared FDR family + late-period ML drift checks (2026-11-09 KST)

## Why this is on the product critical path
- Prior cross-sectional BH-FDR was calculated only on statistically computable pairs. Missing/constant predeclared comparisons were excluded from the correction denominator, risking an overstated exploratory q-value.
- The issuer- and time-disjoint holdout previously reported one aggregate MAE, obscuring late-period degradation and variation across unseen issuers.

## Changes applied (source preserved outside these focused edits)
1. `proofinvest/kuodra_stats.py`: allocate a full family of all predeclared metric pairs, assign p=1.0 for untestable pairs, run BH-FDR over the entire family and retain only analyzable pairs in at-most-three result entries. Add `fdr_denominator=ALL_PREDECLARED_PAIRS_UNTESTABLE_AS_P_ONE`.
2. `proofinvest/kuodra_group_time_ml.py`: add holdout-only, no-model-selection diagnostics: unseen-issuer count of Ridge-vs-Dummy better/worse/ties; earlier/later holdout timestamp group MAE; late/early error ratio; `ELEVATED_LATE_ERROR` flag for at least doubled error. Missing/zero early error is explicitly unquantifiable. Preserve `Guard=HOLD`, `production_ready=False`, no probability or training refit from holdout.
3. `proofinvest/kuodra_review_report.py`: allowlist `holdout_beats_dummy` and `holdout_stability` in locally restricted source-linked review; names, IDs and raw observations are not exported.
4. Two existing targeted tests extended with three regression cases (predeclared BH family and synthetic stable/drifted later-period holdouts). No live provider GET, paywall, institution records, secret or public deployment.

## Executed verification
- Linux local Python 3.13.5: `cd /mnt/data/kic_patch && python -m unittest discover -s tests -p 'test_kuodra*.py' -q` -> **88/88 PASS** (P300 85 + P301 3).
- `python -m compileall -q proofinvest tests` -> PASS.
- `python -m proofinvest.kuodra_synthetic_demo --output-dir <fresh-temp-dir>` then `--verify-dir <same-temp-dir>` -> both exit 0; manifest verification status `SYNTHETIC_ONLY_RECEIPT_VERIFIED`, `guard=HOLD`. Local JSON/HTML contained late error diagnostic with no raw rows. Temporary output deleted.
- GitHub connector readback confirms five updated source/test blobs on `lead/kic`:
  - `kuodra_stats.py`: `3ce1cd371b4a285121b7eb91312bc03a0aa547ff`
  - `test_kuodra_stats.py`: `f9482a4be5e9713f0114f7f1e769328e78b3babb`
  - `kuodra_group_time_ml.py`: `5e33c27370bdc755b1c1008002c22dc467b6adca`
  - `test_kuodra_group_time_ml.py`: `d71e0ca70c87f385ad759ca789d4da28dc5236ab`
  - `kuodra_review_report.py`: `303b63083dbceb92e7aa2a1278ae1f3b33620549`
- GitHub writes executed via authenticated connector. Branch parent before P301 was `19afe992c2a7783ca51c152e7a3d94b376335dd9`; no force push.

## Honest limits, fallback and future work
- Local test harness holds only KUODRA modules (9 source files), not the full KIC repository. GitHub Actions full Python 3.11 / Windows build and institution production are NOT VERIFIED; remote Python bytes differ marginally in comments/formatting from the local test copy for some files. A Git blob readback proves code upload, not executed remote tests.
- Neither cross-sectional Pearson/FDR nor holdout-drift ratio establishes independent-issuer sampling, causal inference, calibrated probabilities or real-market profit. A drift warning is descriptive only and does not validate a model.
- `VerifiedPrincipal(authenticated_by_host=True)` is not real host IAM; Python-socket mocking is not OS-enforced deny-egress. Real confidential source, authentication, licensed index/SEC, hostile parser sandbox and secured host deployments remain RELEASE HOLD.
- Backups: original code at pre-P301 SHA above; revert via ordinary reviewable commits if necessary (never force push). Original KIC A/B/C, Guard, and private PDF/PPTX untouched. Offline P301 patch ZIP available in the conversation artifacts, not automatically persisted to Library.
- Next: whole-repo exact-SHA Python 3.11 CI and isolated execution host interface; no user action except genuinely necessary host credentials/official DAKER filing.
- Estimated scope score (not a release certificate): P300 55/100 -> **P301 56/100** by analytics evidence +1; SEC16/canonical9/public4/private7/analytics12/security3/report5/realE2E0. PDF revision deferred to Nov 11, DAKER filing by Nov 12 10:00 KST, not submitted.
