# KIC permanent handoff body restoration QA — 2026-10-24 KST

## Incident and ground truth
- The actual remote `lead/kic:KIC_HANDOFF_CONTRACT.md` blob was **only a canonical notice plus a heading ending in literal `undefined`**. Header-only validator accepted it; therefore earlier CI passing cannot prove the permanent handoff policy was present.
- Read-only Git historical source: `069d1af:KIC_HANDOFF_CONTRACT.md` (original full 7-step handoff and status distinctions). The current notice was preserved and only stable operational body sections were recovered. Expired progress counts, fixed NEXT dates and obsolete 35% DAKER snapshot were not restored.
- Design alternatives: (A) restore stable text from Git history plus body integrity tests, chosen for policy preservation / minimal change / no cost; (B) replace with a shorter newly drafted policy, rejected because omissions are harder to detect.
- Existing normal Git history provides rollback; **no force push**, feature branch change, data/permission change or public submission.

## Changes
1. `KIC_HANDOFF_CONTRACT.md` restored required one-line invocation, remote SHA/CI handoff, daily 100-point/remaining-hours requirements, fail-closed status handling and protected-data rules.
2. `scripts/master_progress.py` validates nonempty substantial body, mandatory section titles, invocation literal, and rejects `undefined` corruption **as well as** the previous canonical notice/header check.
3. `tests/test_root_handoff_contract_body.py`: six regressions: current restored document, lost-body `undefined`, clean truncated body, missing section, stale opening, duplicate title.

## Verification / limits
- Remote write receipts: restore `8ec15b8066b57bf152a264ecf06306d0a071f5a8`, CI guard `6a66b262d961ce8d96ef2b27a5c8bf996dea2f85`, six tests `773b40a72dbbcd0eff523c6429954112041b7c5b`.
- Latest tested remote HEAD **before handoff docs updates** was `773b40a72dbbcd0eff523c6429954112041b7c5b` (commit fetch). GitHub `get_commit_combined_status` returned zero statuses and `fetch_commit_workflow_runs` returned zero runs due connector limitations. **CI execution/result NOT VERIFIED**. These are not six PASS yet.
- Requested reproduction in repository CI: `python -m unittest discover -s tests -v` and `python scripts/master_progress.py --check`. No local checkout/network or authenticated DAKER browser available to run them in this session.
- No assertion of DART/API/LLM Agent/production/DAKER submission verification. Master JSON remains **29 DONE / 3 BLOCKED / 28 NOT_STARTED** with 2026-12-03 future result; 10/25 and 11/09 DAKER gates 60%, DART 10/30 gate 90%; official PDF submission NOT_STARTED.

## Follow-up / approval
- First confirm latest GitHub Actions workflow for final `lead/kic` commit. If it fails, isolate the failing test and correct it once; do not declare success in advance.
- User must inspect authenticated DAKER participant/team lead role, mobile verification and final PDF submission button. No account change, upload, vote or official submission without separate explicit permission.
- Frozen private 10-page PDF/PPTX and Library 6 backups are unchanged. Git rollback is a normal `git revert` of published repair commits if needed.
