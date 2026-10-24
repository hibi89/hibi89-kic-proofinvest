# KIC manual primary evidence numeric bounds — QA 2026-10-25 KST

## Confirmed defect
- proofinvest/evidence_scenarios.py::_evidence_amounts used Decimal.quantize(0.01) on caller-provided revenue amounts with no arithmetic-exception guard.
- Python's default Decimal context accepts an **80-digit integer string**, yet quantizing the resulting YoY growth raises decimal.InvalidOperation. Reproduced with a synthetic extreme 80-digit amount. This is NOT a confirmed official DART filing incident.
- The existing proofinvest/engine.py extreme input guard did NOT protect this distinct manual primary-source path. A thrown exception could interrupt verify_growth_claim, three_scenarios, and evaluate_offline_chain.

## Options / minimal implementation
- A (selected): Catch InvalidOperation/arithmetic representation errors at the stored-computation gate, convert to ValueError("unrepresentable revenue growth in supplied evidence") handled by verify_growth_claim as unavailable. Guard downstream formatting as defense in depth, returning null computed percentage and source if unrepresentable.
- B (not selected): Cap amount() digit length globally; could reject valid figures.
- C (not selected): Inflate global Decimal context precision; does not guarantee arbitrary input representation and changes unrelated math.
- proofinvest/evidence_scenarios.py: bounded exception handling only; no I/O, no schema change, no API, no file mutation.
- tests/test_manual_evidence_numeric_bounds.py: 3 regressions: (1) extreme manual evidence unavailable instead of crash; (2) all 3 offline scenarios unavailable; (3) full Research→Verification→Risk chain withholds Risk, no external authentication. Original reviewed issuer JSON/Git pin is untouched.
- Normal reviewed Samsung evidence and verified/conflict/unavailable demos retain their behavior.

## Actual test evidence
- Code commit [786da6ec0509ea307d91cfd5e02b0888b54ff2ee](https://github.com/hibi89/hibi89-kic-proofinvest/commit/786da6ec0509ea307d91cfd5e02b0888b54ff2ee) on lead/kic.
- [GitHub Actions 40108977183](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40108977183) completed/success: **239/239 tests PASS**, zero failures/errors, 60-day schedule consistency PASS and offline demos PASS.
- No local user-computer tests. This is only offline code integration proof, NOT DART source authentication, LLM autonomous agent, production app, DAKER receipt, or actual peer vote.
- Separate additional quality unit 100/100 only after final documentation commit CI; remaining base0h+reserve0h after final CI; actual elapsed work hours unmeasured.
- Canonical 60-day progress **29 DONE / 3 BLOCKED / 28 NOT_STARTED**, next 2026-12-03 future result; DAKER 10/25 90% BLOCKED, 11/09 80% BLOCKED, DART 10/30 90% BLOCKED; 11/10 final submission NOT_STARTED.
- No frozen 10-page PDF/PPTX or six private Library backups read/changed, no credentials, costs, external account actions. Prior code baseline 52f232d retained in Git history; normal revert, no force-push.

## Next
- Final submission needs separately authorized final PDF/title and actual DAKER submit; final submitted proof requires submission history state 최종 and a receipt.
- Do not repeat completed 11/14–17 Verification scheduled rows.
