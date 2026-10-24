# KIC — LEAD_ACTIVE_WORK (sole execution queue)
2026-10-24 KST. **OWNER: KIC lead, same chat as implementer.** No worker chat. This document supersedes NEXT_TASK as execution authority.

## Current checkpoint: KIC-R-001 take-over / lead independent verification
- Status: **REPORTED_DONE_BY_FORMER_WORKER / LEAD_REVIEW_REQUIRED**. This is NOT independently accepted nor merged.
- Former task: KIC-R-001 — offline evidence normalizer Research.
- Origin: `feature/research@3fb60204d153b5c791c18961ae790f9f7e94de38`; record `docs/roles/research/TO_KIC_LEAD.md` there; initial tests claimed 26 local PASS, CI unverified.
- Action 1: read source + all 17 new tests from actual feature HEAD and compare with requirements / existing `lead/kic` & `main`; check reported Git history, blockers and CI.
- Action 2: integrate only reviewed safe source/tests onto **`lead/kic`** (not wholesale branch overwrite); run `python -m unittest discover -s tests -v` and `python -m proofinvest --claim-revenue-growth-pct 20` locally if environment available; otherwise mark NOT_RUN and do not claim acceptance.
- Action 3: resolve public proof for data contract and dates/licenses, record accepted/rework, commit evidence; only then move to next Verification implementation and Risk one by one. Avoid any new OpenDART/live API or paid model invocation without approval.
- Parallel participant gate: KIC 'team conversion' and preliminary PDF validity/submission need real evidence. **Not yet verified**.
- Primary deadline: 2026-11-12 10:00 KST; internal PDF target 11/10.
- DONE criteria: reviewed code & recorded test/CI evidence, lead branch remote SHA, STATUS/HANDOFF/TO_HACKATHON_LEAD consistent; main integration separately verified. No claim this checkpoint is currently DONE.
## Next (not automatically complete)
1. Verification source/logic and tests integrated & reviewed.
2. Risk module with source traceability & deterministic risk labels.
3. Prepare/finalize <=10 page PDF and record actual submission receipt.
