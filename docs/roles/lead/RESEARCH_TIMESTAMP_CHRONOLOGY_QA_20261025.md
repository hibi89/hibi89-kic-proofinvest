# KIC Research — same-day publication/collection instant chronology, 2026-10-25 KST

## Defect and risk
Research source normalization checked that the collected **calendar date** was not before the published calendar date. With offset-aware timestamps, a source published at 18:00 KST but allegedly collected at 17:59:59 KST the same day passed day-only comparison. Such a source may support an offline finding before publication. A cross-offset version had the same weakness.
This is a structural, caller-supplied **synthetic timestamp** defect. No particular live publisher or DART filing is claimed to have been affected.

## Implementation decision
- A (chosen): compare exact UTC instants **only when both supplied metadata fields have an explicit timezone offset**. When both are timestamps, collected before published yields existing `invalid_source_date`, source removed, dependent findings withheld. Existing precise-to-day date records keep established compatibility.
- B (rejected): treat each date as midnight and require all timestamps to be no earlier than midnight; this would discard legitimate mixed date-only/ISO records without a reliable clock.
- C (rejected): online publisher fetch or autonomous inferred timestamps; violates the read-only/offline contract and cannot prove historical availability.
- Implementation: `proofinvest/research.py`, add private `_instant` helper using `datetime.astimezone(timezone.utc)`, and one guard before accepting the source. Existing `as_of`, duplicate-URL, ID, license and independent finding checks unchanged.
- New `tests/test_research_timestamp_chronology.py`: 5 regressions covering same-offset earlier timestamp rejection, cross-offset earlier rejection, same instant with different offsets allowed, date-only compatibility, independent source survival and unchanged inputs.
- Valid `normalize_research(...)` means only metadata structure is consistent. It does **not** authenticate publisher publication date, collected timestamp, PDF original, DART report, licensing or rights.

## Verification
- Code commit: `babc92cfaa360212d6031b23b976a0c4eba7c41f` on `lead/kic`.
- GitHub Actions code workflow: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40110986376 — **completed/success, 249/249 unittest PASS, 0 failures/errors**, canonical 60-day checks, offline CLI and all workflow steps green. The final documentation-commit CI will be checked independently.
- Separate unscheduled quality gate: reproduce and options20, narrow UTC instant consistency fix35, 5 regressions + full CI35, handoff/docs CI10. Award 100/100 **only after** final documentation commit CI is verified; actual elapsed time unmeasured, remaining basic0h+reserve0h after closure.
- Canonical 60-day original schedule unchanged: **29 DONE / 3 BLOCKED / 28 NOT_STARTED**. DAKER 10/25 90% BLOCKED, 11/09 80% BLOCKED, DART 10/30 90% BLOCKED, official 11/10 submit NOT_STARTED.

## Security, scope and handoff
No real OpenDART/production/LLM Agent test, no paid request, no DAKER account change/submission/vote, no frozen 10-page PDF/PPTX or six private Library files read or altered. Rollback through ordinary Git history, no force push.
Next external P0: user authorization for exact frozen proposal PDF and title and actual final DAKER submission; final receipt must be checked before claiming submitted. Official deadline 2026-11-12 10:00 KST.
