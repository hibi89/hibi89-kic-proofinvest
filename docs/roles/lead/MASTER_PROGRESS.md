# KIC ProofInvest — 전체 60일 진도표 (MASTER_PROGRESS)

> **진도 단일 정본:** [MASTER_PROGRESS.json](MASTER_PROGRESS.json). 아래 표는 해당 JSON에서 생성된 뷰입니다. 원래 배정 일정은 [DAILY_CAPACITY_PLAN_20261024.md](DAILY_CAPACITY_PLAN_20261024.md)에 보존. 
> **재생성:** `python scripts/master_progress.py --write` / **CI 검증:** `python scripts/master_progress.py --check`.
> 스냅샷 2026-10-24 KST · DONE **21** / BLOCKED **3** / NOT_STARTED **36** / PARTIAL **0**. 전체 개발 완성률이 아닌 **날짜별 작업 판정**입니다.

**다음 READY: 2026-11-24** Risk 임계값과 코드 설명 일치 점검 0%, 기본 1h + 예비 2h = 3h. 미완료 초기 41일 일정 잔여 계획 합계 기본 **13h** + 예비 **42.5h** = **55.5h**(외부 접근대기 불명). 본선 19일은 결과에 따라 조건부이며 포함하지 않았습니다.

**차단:** 10/25 DAKER 제출권한 **60%**(접근 후 기본0.5h+예비1.5h), 10/30 DART 공식원문 **90%**(접근 후 기본0.5h+예비1h), 11/09 팀 제출권한·PDF 단일 최종본 대조 **60%**(접근 후 기본0.5h+예비1.5h). 완료 처리 금지.

**비공개 산출물:** USER_PRIVATE_LIBRARY / KIC ProofInvest / Private Drafts / 6개 저장 성공. 공개 GitHub 비게시. 공식 DAKER 제출 완료 아님.

## 예선 전 · 20일

| 원래 날짜 | 작업 | 상태 | 완료율 | 실제 완료일 | 기본·예비 계획 | 남은 기본·예비 | 실제 소요 | 검증 링크 |
|---|---|---|---:|---|---|---|---|---|
| 2026-10-24 | 일별 시간표와 실제 측정 기준 등록 | **DONE** | 100% | 2026-10-24 | 0.5h+1.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/DAILY_CAPACITY_PLAN_20261024.md) · `4b285a2` |
| 2026-10-25 | DAKER 팀 전환·공식 PDF 양식·기존 원본 확인 | **BLOCKED** | 60% | — | 1h+3h | 0.5h+1.5h | 미계측 | [근거](../../../docs/roles/lead/DAKER_PREFLIGHT_20261024.md) · `32a0c1ae03` · 차단 |
| 2026-10-26 | Research 기존 소스와 신규 17개 테스트 코드 검수 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RESEARCH_REVIEW_20261024.md) · `4578b8034b` · [CI 40063701327](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40063701327) |
| 2026-10-27 | Research 검수된 부분만 lead 브랜치로 이관 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RESEARCH_REVIEW_20261024.md) · `4578b8034b` · [CI 40063701327](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40063701327) |
| 2026-10-28 | Verification 중복 계정 한 종류 차단·테스트 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_DUPLICATE_REVIEW_20261024.md) · `5c4aed4d46` · [CI 40064628185](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40064628185) |
| 2026-10-29 | Verification 기간·CFS/OFS 혼재 1종 차단 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_PERIOD_REVIEW_20261024.md) · `1200a0f` · [CI 40065103938](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40065103938) |
| 2026-10-30 | **실제 기업 사업보고서 한 곳의 매출 2개년 원문 직접 대조** (API 키 없이 공개 열람) | **BLOCKED** | 90% | — | 1.5h+3.5h | 0.5h+1h | 미계측 | [근거](../../../docs/roles/lead/REAL_FILING_VERIFICATION_20261024.md) · `4006543689` · [CI 40065436892](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40065436892) · 차단 |
| 2026-10-31 | Risk 검증 완료 수치만 쓰는 게이트 1종 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RISK_VERIFIED_INPUT_GATE_20261024.md) · `5f05a0bb23` · [CI 40066575713](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40066575713) |
| 2026-11-01 | Risk 결측·0분모·음수자본 사례 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../KIC_RESUME_STATE.md) · `5710a53462` · [CI 40068833504](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40068833504) |
| 2026-11-02 | **10/30 실제 공시 검산 근거를 Agent 결과에 연결**, 거짓 성장률 conflict·근거 없음 unavailable 반례 증빙 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/REAL_EVIDENCE_SCENARIOS_20261024.md) · `4006575947` · [CI 40065759471](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40065759471) |
| 2026-11-03 | 공식 기획서 1~4쪽 작성 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_PAGES_1_4_QA_20261024.md) · `32a0c1ae03` · [CI 40070509483](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40070509483) |
| 2026-11-04 | 기획서 5~7쪽 작성 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_PAGES_5_7_QA_20261024.md) · `d57adcaba7` · [CI 40071181513](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40071181513) |
| 2026-11-05 | 기획서 8~10쪽 + PDF v1 출력 | **DONE** | 100% | 2026-10-24 | 2h+3h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_PAGES_8_10_QA_20261024.md) · `0378b81aa9` · [CI 40072620601](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40072620601) |
| 2026-11-06 | PDF 팩트·출처·실증/미실증 구분 1차 검수 | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_FACT_CHECK_20261024.md) · `e0df218f73` · [CI 40074125319](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40074125319) |
| 2026-11-07 | PDF 글자·이미지·링크·페이지 최종 QA | **DONE** | 100% | 2026-10-24 | 1.5h+3.5h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_VISUAL_FINAL_QA_20261024.md) · `9405668844` · [CI 40074861044](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40074861044) |
| 2026-11-08 | 기획서 최종 동결 | **DONE** | 100% | 2026-10-24 | 1h+3h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/PDF_FREEZE_20261024.md) · `ebf2c0cfef` · [CI 40076057576](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40076057576) |
| 2026-11-09 | 팀 제출권한·PDF 단일 최종본 대조 | **BLOCKED** | 60% | — | 1h+3h | 0.5h+1.5h | 미계측 | [근거](../../../docs/roles/lead/DAKER_SUBMISSION_PREFLIGHT_20261024.md) · `8e2af4f133` · 차단 |
| 2026-11-10 | DAKER 사용자 최종 제출·접수 영수증 확인 | **NOT_STARTED** | 0% | — | 1h+4h | 1h+4h | 미계측 | — |
| 2026-11-11 | 예비일: 접수 오류 대응 전용(정상 제출 시 휴식) | **NOT_STARTED** | 0% | — | 0h+4h | 0h+4h | 미계측 | — |
| 2026-11-12 | 10:00 공식 마감 상태 확인·12:00 상호평가 규칙 | **NOT_STARTED** | 0% | — | 0.5h+1.5h | 0.5h+1.5h | 미계측 | — |

## 결과 대기 · 21일

| 원래 날짜 | 작업 | 상태 | 완료율 | 실제 완료일 | 기본·예비 계획 | 남은 기본·예비 | 실제 소요 | 검증 링크 |
|---|---|---|---:|---|---|---|---|---|
| 2026-11-13 | 상호평가 가능 여부·잔여 투표 수 점검 | **NOT_STARTED** | 0% | — | 0.5h+1.5h | 0.5h+1.5h | 미계측 | — |
| 2026-11-14 | Verification 예외 1건 회귀 개선 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_YEAR_END_REGRESSION_20261024.md) · `8aac6bfd0b` · [CI 40078163825](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40078163825) |
| 2026-11-15 | CFS/OFS·단위 예외 1건 보완 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_AMOUNT_UNITS_REGRESSION_20261024.md) · `95589dabd5` · [CI 40078759840](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40078759840) |
| 2026-11-16 | Verification 누락·불확실성 표현 1건 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_MISSING_SOURCE_REGRESSION_20261024.md) · `cf5552c840` · [CI 40079239630](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40079239630) |
| 2026-11-17 | 검증 테스트/CI 및 잔여 장애 목록 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/VERIFICATION_CI_BLOCKER_AUDIT_20261024.md) · `53cdecdc57` · [CI 40079648079](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40079648079) |
| 2026-11-18 | 상호평가 최소 의무 이행 마감 전 재확인 | **NOT_STARTED** | 0% | — | 0.5h+1.5h | 0.5h+1.5h | 미계측 | — |
| 2026-11-19 | 10:00 상호평가 종료 검수 | **NOT_STARTED** | 0% | — | 0.5h+1.5h | 0.5h+1.5h | 미계측 | — |
| 2026-11-20 | Research 출처·라이선스 근거 한 가지 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RESEARCH_OPENDART_RIGHTS_REVIEW_20261024.md) · `417402f50c` · [CI 40080277200](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40080277200) |
| 2026-11-21 | Research 동종기업 선정 설명 한 가지 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RESEARCH_PEER_SELECTION_20261024.md) · `1b1b4c05f2` · [CI 40080754184](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40080754184) |
| 2026-11-22 | 전체 예비일: 지연된 테스트 보완만 | **NOT_STARTED** | 0% | — | 0h+3h | 0h+3h | 미계측 | — |
| 2026-11-23 | Research 회귀·중복 근거 테스트 | **DONE** | 100% | 2026-10-24 | 1h+2h | 0h+0h | 미계측 | [근거](../../../docs/roles/lead/RESEARCH_DUPLICATE_CITATIONS_REGRESSION_20261024.md) · `164d810855` · [CI 40081231968](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40081231968) |
| 2026-11-24 | Risk 임계값과 코드 설명 일치 점검 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-11-25 | Risk 누락·0분모 반례 테스트 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-11-26 | Risk 음수자본 설명/오류 사례 하나 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-11-27 | Risk 통합 테스트·CI 검수 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-11-28 | Streamlit 오프라인 조회용 화면 최소 골격 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-11-29 | 전체 예비일: 지연·배포 장애 대안 | **NOT_STARTED** | 0% | — | 0h+3h | 0h+3h | 미계측 | — |
| 2026-11-30 | 저장/재조회 분리 최소 1경로 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-12-01 | 합성 결과→화면→출처 1경로 점검 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-12-02 | 선발 결과 대비 코드·데모 점검 및 백업 | **NOT_STARTED** | 0% | — | 1h+2h | 1h+2h | 미계측 | — |
| 2026-12-03 | 10:00 본선 결과 확인 및 일정 전면 재산정 | **NOT_STARTED** | 0% | — | 0.5h+2.5h | 0.5h+2.5h | 미계측 | — |

## 본선 진출 시에만 · 19일

| 원래 날짜 | 작업 | 상태 | 완료율 | 실제 완료일 | 기본·예비 계획 | 남은 기본·예비 | 실제 소요 | 검증 링크 |
|---|---|---|---:|---|---|---|---|---|
| 2026-12-04 | 조건부: 본선 필수 제출물과 현실 재산정 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-05 | Research 실제 공개자료 사용권·인증 조건 확인 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-06 | Research 기업 1건 근거 연결(승인된 범위) | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-07 | 실 OpenDART 호출 승인 시 최소 확인 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-08 | 실 재무계정 1종 기간·단위 검증 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-09 | 재무 수치 conflict 사례 하나 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-10 | Verification 회귀·CI·복구점 확인 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-11 | Risk verified-only 흐름 실제 검증 연계 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-12 | Risk 0분모·음수·누락 엣지 테스트 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-13 | Risk CI 결과·설명 텍스트 QA | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-14 | 3기능 통합·SQLite 조회/캐시 1경로 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-15 | Streamlit 웹 시연 최소 입력/결과 구현 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-16 | 무료 배포·시크릿 분리·권한 검사 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-17 | 브라우저 end-to-end 회귀 테스트 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-18 | 발표 PDF 1차·GitHub 재현 가이드 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-19 | 시연 Q&A·오류/근거 수정 | **NOT_STARTED** | 0% | — | 1h+3h | 1h+3h | 미계측 | — |
| 2026-12-20 | 동결/전일 예비일: 심각 결함만 | **NOT_STARTED** | 0% | — | 0h+4h | 0h+4h | 미계측 | — |
| 2026-12-21 | 본선 산출물 조기 접수(최종 승인 시) | **NOT_STARTED** | 0% | — | 1h+4h | 1h+4h | 미계측 | — |
| 2026-12-22 | 10:00 공식 마감 확인 | **NOT_STARTED** | 0% | — | 0.5h+1.5h | 0.5h+1.5h | 미계측 | — |

## 운영 규칙

- 날짜별 작업을 마칠 때마다 해당 날짜 JSON 행 상태·달성률·실제완료일·잔여 기본/예비·증거 SHA 및 CI를 갱신하며, 원본 일정 60개와 분모를 변경하지 않습니다.
- `python scripts/master_progress.py --write`로 Markdown을 재생성하고 `--check` 및 Actions CI까지 통과시킨 뒤에만 완료로 보고합니다.
- `KIC_RESUME_STATE.md`, `CHAT_BOOTSTRAP.md`, `LEAD_ACTIVE_WORK.md` 상단과 JSON의 `next_task_date`가 동일해야 합니다.
- 공개 저장소에 기획서 바이너리/개인정보 업로드 금지. 민감 산출물은 개인 비공개 Library 백업을 확인합니다.
- 별도 일일 로그는 시점별 이력이므로 옛 `READY`/35% 기록을 현행 상태로 읽지 않습니다.
