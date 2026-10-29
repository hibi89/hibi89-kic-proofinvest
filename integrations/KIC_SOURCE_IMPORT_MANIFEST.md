# KIC integration staging (2026-10-30 KST)

Base: lead/kic @ 2394d18e0ae3e7e17f5e77f30b0b62e5e3694ca0.
Working branch: feature/kic-integrated-components. No changes to lead/kic, main or source branches.

## Imported from feature/disclosure-lightning @ 760ddd3a0e4ad5814e76146c0d536bebc4520f81
- disclosure_lightning/companyfacts.py
- disclosure_lightning/extract.py
- disclosure_lightning/history.py
- disclosure_lightning/xbrl.py
- tests/test_disclosure_lightning_companyfacts.py
- tests/test_disclosure_lightning_extract.py
- tests/test_disclosure_lightning_xbrl.py

Existing DL core.py, originals.py, KIC bridge and SEC integration remain from lead/kic; these are NOT replaced. Imported tests are not yet executed against the merged tree.

## Imported from hibi89/AI_AutoML_Analyst (main at time of fetch; source commit not pinned)
- integrations/automl_source/evaluator.py
- integrations/automl_source/model_selector.py

These are reference-only, NOT wired into KIC runtime. They require pandas/sklearn and are not a leak-safe time-series evaluator by themselves. Before enabling ML, implement chronological train/validation/test split, baselines, feature availability cutoffs and independent tests. Do not copy the whole AutoML application or add heavyweight dependencies to KIC prematurely.

## Next gates
1. Run existing KIC and newly imported DL tests in this branch; fix only confirmed regressions.
2. Inspect imported DL APIs and extend proofinvest/dl_bridge.py using explicit bounded input/output contracts.
3. Validate offline SEC evidence -> verification -> Risk -> Guard -> audit -> report end-to-end, no external SEC requests without approval.
4. Final preliminary PDF remains a separate approval and submission gate; no deployment, live SEC authentication or submission is claimed.

This is a source staging branch, NOT completed integration or production verification.
