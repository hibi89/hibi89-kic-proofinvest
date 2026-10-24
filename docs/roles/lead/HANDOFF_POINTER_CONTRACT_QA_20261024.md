# KIC CI handoff next-task contract repair — 2026-10-24

## Incident / actual root cause
- Previous CI #40094198262 failed at the master-progress handoff-pointer step when cumulative lead notes displaced the full ISO `2026-12-03` date beyond the first 2,500 characters of KIC_RESUME_STATE.md.
- CI #40094275466 was temporarily repaired by adding an ISO date near the beginning. This was a brittle workaround, not a robust fix.

## Chosen design
- A: retain 2500-character substring search: reject; new report prepends trigger recurring failures.
- B: search full file for date: reject; stale historical report mentioning the same date would hide an outdated current pointer.
- C: require exactly one literal `<!-- KIC_CANONICAL_NEXT_TASK_DATE: YYYY-MM-DD -->` declaration anywhere in each of three handoff files, and equality with canonical MASTER_PROGRESS.json next_task_date; chosen.
- Added declaration to KIC_RESUME_STATE.md, CHAT_BOOTSTRAP.md and docs/roles/lead/LEAD_ACTIVE_WORK.md. They must be changed together whenever the canonical next task changes; historical prose remains unchanged.
- New unittest test_handoff_pointer.py: 7 scenarios, including 20k characters of history, stale/malformed/duplicate/unmarked values, and agreement with current three documents.

## P0 external boundaries remain unchanged
- Browser connector in this current mobile-origin chat returned `Browser access requires the originating browser context`, so the authenticated DAKER final-submit page was NOT checked anew.
- Official KIC rules: https://daker.ai/public/hackathons/kic-ai-agent-competition; submission is a single PDF (10 pages max), team leader `제출 완료` followed by a confirmed final submission history state. Team composition shown in a prior read-only observation is not sufficient evidence of final upload authority.
- Official DAKER note: https://daker.ai/community/revert-overwritten-kic-ai-agent-proposal mentions common disabled-button causes: non-leader, no saved draft, unsaved edits, other simultaneous editor. None of those is confirmed in the user's account.
- No account changes, submission action, PDF/PPTX file handling, new API request, secrets, or deployment.
- 60-day canonical total remains 29 DONE / 3 BLOCKED / 28 NOT_STARTED. DAKER 10/25 and 11/09 each 60 BLOCKED; official DART 10/30 at 90 BLOCKED; 11/10 actual submission NOT_STARTED; next 12/03 result awaited in future.

## Test / recovery
- Run `python scripts/master_progress.py --check`, `python render_master_progress.py --check`, and `python -m unittest discover -s tests -v`; CI must pass for completion.
- Rollback via Git revert of this commit if new check proves incompatible; never force-push or change canonical JSON to fake completion.
- This is a separately tracked CI reliability repair, not another 60-day scheduled DONE. Actual time unmeasured.
