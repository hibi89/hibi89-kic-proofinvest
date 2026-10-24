# KIC 2026-11-27 Risk 통합 테스트·CI 검수 — 선행 2026-10-24

## 실제 결함 및 범위
- 예정보다 선행 수행: 2026-10-24 KST. 원래 계획일 2026-11-27. 원격 `hibi89/hibi89-kic-proofinvest` `lead/kic`.
- **코드 교차검증으로 발견한 실제 불일치**: 최신 `proofinvest/risk.py`의 verified-only 경로는 자본총계 음수/0과 음수 부채를 반드시 `unavailable`로 보류했으나, 실제 CLI `python -m proofinvest`가 호출하는 `proofinvest/engine.py:calculate`에서는 부채80·자본-10 입력으로 **-800.00%/triggered=false**를 출력할 수 있었다. 사용자에게 위험 없다는 인상을 주는 결함이다.
- 또 기존 레거시 `calculate`는 비합성 `is_demo=False`에서 부채·자본 각 공시 참조가 누락되거나 서로 다른 경우에도 Risk 신호를 계산할 수 있었다. 단순 14자리 `rcept_no` 형식은 **공식 DART 접수 인증이 아님**.

## 실제 변경 및 대안
- 수정 `proofinvest/engine.py`, 신규 `tests/test_risk_engine_integration.py`. 코드 SHA `52504948599c61193bdc0bf45f5a56db7845d5a1`.
- **선택 A**: 오래된 CLI 경로를 보존하되 주석에 '데모 전용' 표기만 추가 → 실제 오해 가능 출력 지속되어 기각.
- **선택 B**: CLI 레거시 입력 경로에도 safe arithmetic guard 적용 (**채택**). 음수 자본·0/-0 분모·음수 부채·필수 수치 누락·지원 외 통화는 `value=null, triggered=null`, `withheld_reason_code`로 계산 보류. 수학과 정보 출처가 정상인 합성 시연의 80/30=266.67% 경로는 보존.
- 비합성 Risk 신호는 부채·자본 **둘 다 HTTPS 출처 링크가 있고 동일한 공시 문자열 참조**인 경우에만 오프라인 탐색 비율 산출. 그러나 외부 조회/암호학적 원문 인증은 없으며, `source_kind=OPENDART` 표시만으로 믿을 수 있는 공식 사실이나 투자 권고라는 뜻이 아니다.
- 레거시와 신규 verified-only Risk는 **여전히 별도 계산 경로**. 이번 검수는 상태/안전 신호 회귀 정합성이지 production 통합이나 단일 데이터 계약 최종 동결이 아니다.
- 다중 입력 불일치 시 계산 자체를 보류하고, 거짓 안전 경고 방지. `engine.calculate`의 반환 객체, revenue claim 계산, synthetic/demo status, CLI 플래그는 기존대로 유지.

## 테스트 영수증
- 신규 **9개** 교차경로 테스트: 정상 합성 80/30 양 경로 수치/신호 일치, 자본-10의 -800% false 차단, 자본0/-0 중단, 부채 음수 중단, 결측 입력 중단, 비합성 출처 누락·서로 다른 접수번호 중단, 유효 형식14자리 출처도 실제 인증이 아님 명시, 통화 USD 일괄 입력 중단.
- [GitHub Actions #40084712270](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40084712270) **completed/success**: Python `unittest discover -s tests -v` **129/129 PASS**, 60일 JSON·Markdown 동기화 검사 2개 PASS, 합성 CLI 및 수동 기록 실기업 근거의 **오프라인** CLI PASS. 별도 로컬·실 OpenDART API·실 DAKER 업로드·웹/Agent Production E2E는 미실행.
- **신규 코드가 검증된 데이터 진실성을 보장하지 않음**: `risk.py`의 `verified` 라벨은 여전히 상위 제공자가 입력한 주장에 의존. 금융 원문 및 접수번호 실확인, 원문 재사용 허가는 추가 증거 필요.
- 레거시 계산에서 음수 자본을 표시/위험없음으로 오해하던 문제와 입력 출처 불일치 문제는 수정 완료. 동종 보고서 리디렉션/원문 출처의 실제 진위까지 해결한 것은 아님.

## 완료·장애·다음
- **11/27 계획 작업 100/100 DONE**, 코드 감사25점, fail-closed 교차경로 수정35점, 9 회귀 및 최종 CI30점, 인수인계10점. 남은 기본0h+예비0h, 실제 작업시간 미계측.
- 60일 **25 DONE/3 BLOCKED/32 NOT_STARTED** (일별 작업 상태이지 실사용 제품 완성률 41.7%는 아님).
- 최상위 외부 P0 **DAKER 참가자 개인/팀장 최종 제출 버튼 권한 10/25·11/09 각각60% BLOCKED**, 실제 최종 접수 11/10 NOT_STARTED. P1 **DART 10/30 원문 뷰어 접수번호 확인 90% BLOCKED**. 11/18·19 평가·11/22 및 11/29 예비일은 조건부/미래 사건으로 미착수.
- **다음 독립 READY 2026-11-28 Streamlit 오프라인 조회 화면 최소 골격**, 0/100, 기본1h+예비2h=3h. 실계정 DAKER 권한 확인 가능해지면 P0부터 회수.
- Frozen 비공개 10쪽 PDF·편집 PPTX·Private Library 6개 백업 기록은 조회·수정·공개업로드하지 않음. 이전 SHA `d3e199c981ede9d9cf5fb41daee9b38719444a2c`로 revert 가능, force-push/main/feature 무작업.
