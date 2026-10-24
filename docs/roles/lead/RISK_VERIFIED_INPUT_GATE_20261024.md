# 10/31 선행개발 — Risk verified-only financial input gate

기록: 2026-10-24 14:29:41 KST, `lead/kic`, *실 금융자료/API 사용 없는* 오프라인 단위.

## 범위
- `proofinvest/risk.py`에 **`gate_verified_risk_inputs`** 신설. 1개 Risk 계산의 입력 `liabilities`·`equity` 각 1건이 **state=verified**인지 확인.
- **같은 연도(2024 등), 재무제표(CFS/OFS), 연간보고서 코드(11011), 기말일, KRW 단위, 동일 기업·동일 공시 참조·URL·출처 종류**를 확인. 필드 누락·충돌·잘못된 값·중복 계정·인증된 것처럼 주장하는 가짜 입력은 **unavailable**로 보류. 기존 Verification의 산술/회계 검증 결과와 별개로 동작하며 거짓 수치 진위 자체를 검증하는 모듈은 아님.
- **데모 모드**에서만 `SYNTHETIC_FIXTURE` 수용. 일반 모드는 주장상 `MANUAL_PRIMARY_SOURCE_VERIFICATION` 기록만 받지만 외부 인증 여부를 **false**로 유지. 수동으로 제공된 `verified` 문자열 자체가 위조 불가능한 증명은 아니므로 이 메타데이터/입력 계약은 **내부 Risk 게이트의 첫 방어선**이며 최종 서비스 API 인증·출처 검증 완성이라고 주장하지 않음.
- `eligible`은 '두 재무 수치가 **다음 계산 단계의 입력조건을 통과**했다'는 뜻. **부채비율 산출/판정 자체는 하지 않음(`risk_calculated=false`)**. 11/01 결측/분모0/음수자본/정형 계산 테스트 이후 연동 대상. 구형 `engine.calculate`의 합성 진단용 리스크 후보 계산은 **아직 Risk 새 게이트를 거치지 않으므로 실서비스 최종경로로 사용 금지**.

## 검사 시나리오
- 정상 verified 2건/동일 공시/데모 기준 성공
- conflict/unavailable 수치 차단
- 미제공·중복·잘못된 계정 차단
- 단순 매출성장률 verified가 부채·자본의 대체 근거가 되는 오류 차단
- 연도·CFS/OFS·분기보고서·기간 혼합 차단
- 기업·공시ID·출처 URL 혼합 차단
- 통화·NaN·결측·비HTTPS 출처 차단
- 실제 데이터 인증 성공 거짓 주장 방지
- 입력값 비변경·순서독립 검증

신규 테스트 `tests/test_risk.py` **13개** 및 기존 **54개** → [CI **67/67 PASS**](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40066575713). GitHub CI 실행 후 실제 66/66 판정을 검증한다. 외부 API 키/네트워크/원본 회사 실자료 추가 호출 없음.

## 10/31 계획 100점 게이트
| 증거 | 점수 |
|---|---:|
| 위험신호 기존 코드 및 인증/출처 경계 분석 | 20 |
| Risk 입력 게이트 검증·차단 코드 | 40 |
| 신규 12개 및 기존 54개 GitHub Actions CI 재검증 | 30 |
| GitHub 원격 SHA/인수인계·상위 총괄 동기화 | 10 |
| **합계** | **100** |

최종 **100/100=100%**, 남은 순작업 0h + 예비 0h = 0h (10/31 단일 작업). 실제 소요시간 미계측. 60%는 중간 잠정 기록.

## 2026-10-24 14:33:21 KST — 10/31 Risk verified-only 입력 게이트 ACCEPTED_ON_LEAD
- 소스 `proofinvest/risk.py`, `tests/test_risk.py` 구현 커밋 `7a4c753`, 강화 커밋 **`5f05a0bb237ebfbe4837a21c2aaa37fb276a82b9`**. [GitHub CI 40066575713](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40066575713) job `120790987943` **67/67 PASS**, 기존 합성 CLI + 공개기업 수동기록 CLI 2건 모두 PASS.
- 최초 Risk 신규 12건으로 66 PASS. 검수 중 `source_kind`가 해시 불가능한 목록·객체인 경우 예외 발생 가능성을 확인해 차단 패치 + 반례 1개 보강. **신규 Risk 테스트 13개**, 기존 54개 포함 **67/67**.
- **10/31 과제 100/100=100%**: 기존 코드·신뢰 경계 검토 20/20, verified-only 입력 차단 구현 40/40, 67 테스트·CLI 성공 30/30, 원격 증거·인계 공시 10/10. **잔여 기본 0h + 검수 예비 0h = 0h** (이 과제만). 실제 수행시간 미계측.
- `eligible`=두 위험 입력의 verified 표시·동일 재무제표/연도/기업/자료 메타데이터 조건 충족이지 **실제 원본 진위 인증 아님**. `authenticated_external_source=false`, `risk_calculated=false` 반환. **구형 `engine.calculate` 탐색성 부채비율은 이 게이트 미경유**. 실서비스 E2E나 리스크 계산 전체 완성으로 주장 금지.
- 최신 사용자 승인 [선행 순서 유연화](../../WORK_ORDER_FLEX_POLICY_20261024.md) 존중. 다음 독립 개발은 **11/01 Risk 0분모·결측·음수자본 안전 계산/반례**. DAKER 10/25 계획 35%/접근 후 3h, DART 10/30 계획 90%/접근 후 1.5h 별도 BLOCKED 유지, [복구 일정](BLOCKED_WORK_RECOVERY_20261024.md)은 변경 없음.
