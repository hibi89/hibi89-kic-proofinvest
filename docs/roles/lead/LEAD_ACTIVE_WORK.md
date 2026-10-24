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
## 2026-10-24 13:43:28 KST — 본선 이전 실제 기업 공시 검증을 예선 일정에 반영
- 사용자가 '본선진출하기전에는 실제공시 기업자료 안쓰나'라고 확인 요청: **예선 전에 쓴다**. 10/30 실제 기업 1곳 사업보고서 등 공개 재무정보를 검산(회사·보고서 접수번호·연도·CFS/OFS·단위·URL·2개년 매출·Decimal 성장률), 11/02 출처 있는 실제 주장/잘못된 주장 conflict/근거 없는 주장 unavailable 사례 준비.
- 구형 12월 '실자료 첫 연결'처럼 보이는 일정과 구별: 12월은 진출 시 실 API 자동화·기업 수 확대·MVP 배포 단계이고, **10월 말 예선은 공개 자료의 수동/결정론적 검증 1건 이상** 단계다.
- **기본 1.5h + 예비 3.5h = 5h 한도(10/30, 11/02) 유지**. 원본 접근/기간/연결 정보 부족 시 BLOCKED/이월·재산정, 합성 테스트로 실기업 실증 성공을 꾸미지 않음. 11/03~05 기획서, 11/08 동결, 11/10 내부 조기 제출 유지.
- OpenDART 공식 웹 공개 공시 열람 가능([공식 소개](https://opendart.fss.or.kr/intro/main.do)). API 인증키 자동 수집/대외 LLM 자료 전송·유료 사용은 별도 승인 게이트이며 이번 수정으로 허가된 것이 아니다.
- 이번 변경 **일정·검증 계약 수정만**, 실제 특정 기업 숫자 확보·실수치 계산·API 호출·PDF 제출을 실행하지 않았음. 실증은 해당 날짜에 실제 원문과 계산 증거를 저장하고 평가한다.

- 당일 실제 실행포인터와 별도로 10/30 원문 검산 및 11/02 예선 실증 게이트를 반드시 우선순위에 포함한다. 이월 중에도 공식 제출 권한/PDF 준비를 우선한다.
