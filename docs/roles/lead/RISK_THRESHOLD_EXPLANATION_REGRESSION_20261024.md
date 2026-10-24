# KIC Risk 임계값 설명 일치 QA — 계획 2026-11-24, 선행 2026-10-24

## 실제 결함·선택
- Risk verified-only 계산은 부채총계 / 자본총계 × 100 의 미반올림 Decimal 값이 200% 이상인지로 triggered를 판정한다. 기존 한글 note에 연산자·미반올림 기준이 없어, 표시 200.00%와 triggered=false가 동시에 나오는 경우 오해할 위험을 발견.
- A 대안: 표시 반올림값으로 먼저 비교. 표시와 경고는 맞지만 199.996…%를 200% 도달로 잘못 판정하므로 기각.
- B 채택: 원래 수학 판정 유지. comparison_ratio_pct, threshold_operator(>=), comparison_basis(unrounded_decimal_ratio), display_rounding(ROUND_HALF_UP_2DP) 및 설명 문구 추가. 투자 의사결정 기준 아님.
- 예: 부채 60, 자본 30 => 미반올림 200%, 표시 200.00%, triggered true. 부채 59.999, 자본 30 => 미반올림 199.99666…%, 표시 200.00%, triggered false.
- 모든 분모0·음수 자본 등 계산 보류 경로의 비교 원본 값은 null로 보존. verified-only Risk는 구조적 입력 게이트이며 공식 원본 진위 인증이 아니다. 구형 engine.calculate는 별도 탐색 신호 경로이므로 실서비스 Risk로 사용 금지.

## 코드 및 CI 영수증
- 변경 코드 SHA: 42fc6f46c95bf6ca010ee893e7cb49555f2d88f4; 파일 proofinvest/risk.py, tests/test_risk.py.
- 신규 테스트 2개: 계산/보류 간 임계값 메타데이터 일관성 및 계산 보류 null; 비합성 수동 기록 원본 인증 false 유지. 기존 경계·표시 반올림 3개 회귀 확장.
- [GitHub CI #40081727073](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40081727073) completed/success, GitHub Python unittest 113/113 PASS(FAIL0/ERROR0), 두 60일 진도표 검사, 합성 CLI 및 삼성 수동 기록 기반 오프라인 CLI 모두 통과. 독립 로컬/실 API/브라우저 E2E/Production 미실행.
- 200%는 시연용 탐색 임계값으로 실제 공인 투자/규제 기준이 아니다.

## 진도·남은 장애
- 예정일 2026-11-24, 실제 선행 완료일 2026-10-24 KST. 해당 작업 100/100 DONE, 남은 기본0h+예비0h, 실제 작업시간 미계측.
- 전체 원장 22 DONE / 3 BLOCKED / 35 NOT_STARTED (날짜별 과제 판정, 제품 완성도 수치 아님).
- DAKER 로그인 제출권한 확인 10/25·11/09 각60% BLOCKED; 공식 실제 제출 11/10 NOT_STARTED, DART 공식 원문 뷰어 접수번호 대조 10/30 90% BLOCKED. 11/18~19 상호평가와 11/22 예비일 NOT_STARTED 유지.
- NEXT 2026-11-25 Risk 누락·0분모 반례 테스트, 0/100, 기본1h+예비2h=3h. P0 실제 DAKER 계정 접근 가능해지면 우선.
- 비공개 frozen PDF/PPTX 및 private Library 6개 기존 백업은 이번 작업에서 조회/수정/공개업로드 없음. 직전 SHA 86d5a0b82a85d587aeeeaec2162b3b9e118ab0a5로부터 정상 git revert 가능. Force push/main/feature 변경 없음.
