# Risk 음수자본 설명 및 오류 반례 (2026-11-26 예정 과제)

## 실행과 사실
- 실제 작업일: 2026-10-24 KST; 예정일: 2026-11-26. 저장소 `hibi89/hibi89-kic-proofinvest`, 브랜치 `lead/kic`.
- 계산 예시 (모두 **SYNTHETIC_FIXTURE**, 실제 공시 아님): 부채 80 KRW, 자본 -10 KRW → 단순 부호 포함 나눗셈은 -800%. 임의 시연 임계값 200%보다 낮다는 이유로 `triggered=false`를 출력하면 위험이 없다는 잘못된 인상을 줄 수 있음.
- 올바른 제한: **자본총계 음수**인 경우 보통의 부채/자본 비율을 해석 가능한 단일 양수 위험지표로 비교할 수 없으므로 `status=unavailable`, `withheld_reason_code=NEGATIVE_EQUITY`, `risk_calculated=false`, `ratio_pct=null`, `comparison_ratio_pct=null`, `triggered=null`. 자본잠식 판정·원인/규모는 별도 자료 검증 필요.
- 이 과제는 투자 권고도 '음수 자본은 실제 위험 없음' 또는 '법정 자본잠식 확정'도 아니다. `authenticated_external_source=false` 보존.

## 실제 변경과 대안
- 코드 `18f3b81740b074ac3fcdb9ec1a0090a8ed12d2c8`, 변경 `proofinvest/risk.py`·`tests/test_risk.py`.
- 한국어 `withheld_explanation_ko` 필드 추가. 계산 성공 시 null, 영(0) 자본은 '분모 0으로 정의되지 않음'을, 음수자본은 '음수 비율을 안전으로 해석할 수 없으므로 보류/추가 공시 확인 필요'를 명시. 기존 영문 reason, reason code, 임계값, 정상 계산 수학은 그대로 유지.
- 설계안 A: 음수 -800%를 그대로 노출하고 200% 미만이므로 false 판정 → **기각**(안전 오판정 위험).
- 설계안 B: 음수자본 조건의 비율/판정 null 유지, 기계적 코드 + 한국어 보류 사유 제시 → **채택**.
- 실제 계산경로 `calculate_verified_debt_to_equity`에 한정; 구형 `engine.calculate`는 이 verified-only 게이트를 경유하지 않으므로 실서비스 사용 금지.

## 검증
- 신규 3개 회귀: 부채80/음수자본-10의 미흡한 -800% 안전 오판정 차단, 부채0/자본-1도 계산보류, 계산성공/분모0/음수자본/금액결측 간 설명 필드 계약 유지.
- 기존 `test_negative_equity_safely_withheld`에 reason code·미반올림/표시 비율 null 등 강화.
- [GitHub Actions #40082667314](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40082667314) 최종 **120/120 PASS**, 60일 JSON/표 무결성 검증, 합성·수동 기록 오프라인 CLI SUCCESS. 독립 로컬/실 OpenDART/브라우저/Production 검증 실행하지 않음.
- 여전히 실제 재무제표 진위/라이선스/산업별 적절한 임계값은 검증되지 않음.

## 진도와 차단
- 해당 11/26 계획과제 **100/100 DONE**, 남은 기본0h+예비0h=0h. 실제 작업시간 미계측.
- 전체 60일 계획 24 DONE/3 BLOCKED/33 NOT_STARTED. 날짜 슬롯 완료율을 제품 완성률로 오해하지 않음.
- P0 DAKER 10/25와 11/09 팀장/개인 최종 제출 권한 각 60% BLOCKED, 공식 11/10 접수 미착수. P1 DART 10/30 원문 뷰어 접수번호 대조 90% BLOCKED. 11/18·11/19 상호평가와 11/22 예비일은 NOT_STARTED 유지.
- **다음 독립 READY 2026-11-27 Risk 통합 테스트·CI 검수**, 0/100 기본1h+예비2h=3h. 사용자 인증 DAKER 접근 열리면 P0 우선.
- 비공개 동결 10쪽 PDF/편집 PPTX 및 Private Library 백업 6개 기존 보존 기록을 변경하거나 외부 게시하지 않음. 되돌리기 기준 이전 SHA `a7663b57935f99e20e463528dde356dbf4e1d61e`, 강제 push/main/feature 미수정.
