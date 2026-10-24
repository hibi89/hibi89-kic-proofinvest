# KIC Verification — 보고연도·기간 종료연도 불일치 차단 회귀
> 원래 일정 2026-11-14, 실제 2026-10-24 선행 완료. 단일 작업 `KIC-VERIFICATION-REGRESSION-20261114`. 작업 브랜치 `lead/kic`.

## 문제 재현 및 선택
- 기존 `proofinvest/engine.py::_consistent_annual_period`는 연간 코드 `11011`, `bsns_year=2024`와 서로 비교 가능한 **일관된** 종료일 쌍만 확인했지만, 종료일이 **2023/2022**로 한 해씩 뒤처진 입력도 `bsns_year=2024` 라벨을 믿고 수용할 수 있었다.
- 위험: 사용자의 2024년 회계 수치 요청에 2023/2022년 값을 2024/2023년 값처럼 간주해 YoY 성장률을 검증했다고 판정할 수 있음. 데이터 출처 인증과 별도로 결정론적 입력 정합성 검증에서 보수적으로 차단해야 함.
- 대안 A(채택): 선택한 동일 CFS/OFS 재무제표의 current period 종료연도는 명시된 `year`, previous 종료연도는 `year-1`인지 추가 검사. 기존 `previous < current`와 모든 행 기간 일치 조건은 유지.
- 대안 B(배제): 무조건 `12-31`로 결산일 강제 — 3월 결산 회사의 유효한 연차보고를 잘못 거부하므로 불채택. 대안 C(배제): 기간 불일치를 무시하고 마지막 행 날짜 기준 집계 — 잘못된 증명 가능성 증가.
- 이 규칙은 **날짜 메타데이터가 있는 행에 적용**됨. 과거 레거시 합성 fixture의 **날짜 메타데이터 전체 누락** 허용은 유지하되 실제 공시 진본 인증으로 오해하지 않음.

## 실제 변경
- `proofinvest/engine.py`: `_consistent_annual_period`에 `current.year != year or previous.year != year-1`이면 fail-closed `return False` 추가.
- `tests/test_engine.py` 오프라인 회귀 3건 추가:
  1. 2024 annual 코드 + `current=2023, previous=2022` stale pair를 `parse_accounts={}`, 계산 `unavailable`로 차단.
  2. 2024 annual 코드 + `current=2024, previous=2022` 건너뛴 전년을 차단하고 Risk 신호를 비활성.
  3. 합법적인 3월 결산 예시 `current ending=2024-03-31, previous ending=2023-03-31`은 정상 `verified` 유지.
- 코드 커밋 `d7852d75804450ff387a9920e090f55210efaa8a`, 테스트 커밋 `2839a3eaef578fd347375285e120fa77d2ad69d4`.
- [GitHub Actions 40078163825](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40078163825) **SUCCESS**, `Ran 85 tests in 0.040s`, `OK`; Python 85/85, 마스터 60일 정본 및 인수인계 검증, 합성 CLI, 수동 원문증빙 시나리오 CLI 모두 PASS.
- 외부/유료 API 호출·OpenDART 실제 인증·실사업 보고서 진본 대조·DAKER 사이트 계정/제출·배포 **실행하지 않음**.

## 원래 11/14의 100점
| 게이트 | 배점 | 획득 |
|---|---:|---:|
| 재무제표 보고연도 불일치 예외와 사용 범위 확인 | 20 | 20 |
| 비교 종료연도 fail-closed 수정·정상 비12월 결산 보존 | 35 | 35 |
| 최소 3회귀 포함 전체 85/85 CI 통과 | 35 | 35 |
| 원격 기록·60일 상태·상위 인계·CI 정합성 | 10 | 10 |
| **완료** | **100** | **100/100** |

- 원래 일정 **2026-11-14**, 실제 선행 **2026-10-24**. 이 과제 잔여 기본 **0h+오류/검수 예비0h=0h**, 실투입시간 **미계측**. 원래 기본1h+예비2h=3h는 계획 수치이며 실제 측정값 아님.
- 기존 10/25 DAKER 계정검증 **60% BLOCKED**, 10/30 DART 원문 **90% BLOCKED**, 11/09 DAKER 재점검 **60% BLOCKED** 그대로. 11/10 최종 대회 제출은 **NOT_STARTED**, 권한·사용자 승인·영수증 없음.
- 다음 단일 독립 READY **2026-11-15: CFS/OFS·단위 예외 1건 보완**, 시작 **0/100**, 기본1h+예비2h=3h. 계정 로그인 가능해지면 제출 전 권한 점검을 우선 재평가.
