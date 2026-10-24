# KIC 2026-11-25 계획 Risk 결측·0분모 회귀 및 명시적 보류 코드

## 목표 / 실행
- 원래 예정일: 2026-11-25. 실제 선행일: 2026-10-24 KST. 저장소 hibi89/hibi89-kic-proofinvest, 브랜치 lead/kic.
- 수정 전 구조적 Risk 게이트는 결측, 형식오류를 공통 영어 reason으로만 전달했고, 계산 단의 equity=0 보류도 기계로 구분 가능한 코드가 없어 연결된 UI/Agent가 임의 문자열 비교에 의존해야 했다.
- 정책: Risk 값·신호가 계산되지 않은 경우 반드시 status=unavailable, ratio_pct=null, comparison_ratio_pct=null, triggered=null, risk_calculated=false. 독립 출처 인증 여부 역시 false; 보류 원인만 추가하여 오판정 금지.

## 선택한 방안
- A: note/reason 한국어 문구만 수정해 외부에서 문자열 비교 (문구 변경 시 깨짐) → 기각.
- B: 내부 Risk 게이트와 결과에 withheld_reason_code 추가 (채택, 기존 상태·수치·출력 이름 보존).
- 필수 두 재무 계정/입력 형식 부족: REQUIRED_FACTS_MISSING_OR_INVALID.
- 원재무 금액 null, 공백, -, N/A: MISSING_FINANCIAL_AMOUNT.
- NaN, 비숫자 문자열, 지수표기 등 amount()에서 거부한 값: MALFORMED_FINANCIAL_AMOUNT.
- 구조적 기타 검증 부적합: INPUT_GATE_REJECTED (기존 입력 차단 유지).
- 실제 계산에서 equity=0 및 -0: ZERO_EQUITY_DENOMINATOR, equity<0: NEGATIVE_EQUITY, liabilities<0: NEGATIVE_LIABILITIES. 산술/표시 불가: ARITHMETIC_UNREPRESENTABLE. 계산 완료: withheld_reason_code=null.
- 결측·형식오류는 구조적 게이트에서 숫자 facts={}인 상태로 정지하며, 0분모는 구조적으로 적격한 입력이어도 산술·탐색 신호만 보류한다.

## 코드 / 실측 CI
- 코드 SHA 0c82f6577e3f8e317131cb9d824b4e1cbf27deaa, 변경 proofinvest/risk.py, tests/test_risk.py.
- 새 테스트 4개: 부채/자본 각각의 결측5변형, 단일/빈 fact 행, NaN/문자/지수 오류, 음의 0 분모에 대해 null 위험신호와 정확한 사유코드 확인. 기존 정상이 계산되면 reason_code=null, 0분모와 200% 경계 정확성 테스트 보존.
- [GitHub CI #40082329914](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40082329914) completed/success: Python unittest **117/117 PASS**, 60일 JSON/표 sync 검사 및 합성 CLI/삼성 수동기록 기반 오프라인 CLI 전부 통과. 별도 로컬/브라우저, 외부 OpenDART API/Agent E2E/Production 실행 없음.
- 주의: 이 코드는 공식 공시 원본·원가/라이선스·규제상 투자 위험기준을 검증하는 게 아닌 구조적으로 제한된 오프라인 계산기다. 오래된 engine.calculate 레거시 Risk 경로는 verified-only Risk 게이트를 경유하지 않아 운영 사용 금지.

## 점수 / 종속 차단 / 다음
- 11/25 업무 **100/100 DONE**: 결측/0분모 현재 코드·대안20, 사유코드 및 보류계약35, 신규 4 회귀와 CI35, QA·60일 정본·인계10. 해당 업무 잔여 기본0h + 예비0h, 실제 투입시간 미계측.
- 60일 원장 **23 DONE / 3 BLOCKED / 34 NOT_STARTED** (날짜별 계획 판정, 전체 제품 완성률 아님).
- P0 DAKER 참가자 인증된 개인/팀장 최종 제출권한: 10/25·11/09 각각 60/100 BLOCKED. 실제 DAKER 11/10 제출/최종 영수증 NOT_STARTED. P1 DART 공식원문 접수번호 대조: 10/30 90/100 BLOCKED.
- 11/18·11/19 상호평가 확인은 미래 인증 결과 필요하여 NOT_STARTED. 11/22 예비일 미사용 NOT_STARTED.
- **NEXT 2026-11-26 READY 0/100** Risk 음수자본 설명/오류 사례 하나, 기본1h+예비2h=3h. 접근 가능한 DAKER 사용자 인증이 생기면 P0 회수를 우선한다.
- 변경 전 HEAD a6aec576f07bd064ba1ef8f97aa249ea25f9c775. force-push, main/feature 변경, 비공개 10쪽 PDF/PPTX·Library 백업 수정 및 공개 업로드 없음.
