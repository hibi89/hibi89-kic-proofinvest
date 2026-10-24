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

## 2026-10-24 13:21:02 KST — 일별 작업시간과 안전예비 공시
- 사용자 경험 4h 예상 → 8~20h 소요를 반영해 docs/roles/lead/DAILY_CAPACITY_PLAN_20261024.md에 **10/24~12/22 날짜별** 한 건의 작은 핵심작업/기본 1~2h/오류·검수 예비 2~3.5h/당일 상한 3~5h/완료 게이트를 분리했다.
- 상한 초과 시 기능 삭제 또는 허위 완료 없이 이월·재산정. 11/08 PDF 동결, 11/10 조기 제출, 11/12 10:00 공식 마감 우선. 11/11 접수 장애 완충일 지정.
- 새 계획은 구현/실 API/DAKER 접수 완료가 아니다. 이전 Research feature/연결된 CI 26 PASS를 확인했으나 lead 수용·main 통합은 미완료. 실측 기반 수정과 상위 보고 동기화 필수.

- 현재 첫 개발 인수 작업은 Research 구 feature 결과의 직접 코드 리뷰/lead/kic 이관이다. 10/25 DAKER 권한/양식 확보는 예선 최상위 선행 게이트. 과거 코드를 처음부터 다시 짜지 않는다.
