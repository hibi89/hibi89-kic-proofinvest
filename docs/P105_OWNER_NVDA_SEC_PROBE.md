# P105 — NVDA SEC 단일 조회 (소유자 승인 2026-11-02, 미실행)

승인 범위: NVDA 하나, SEC 공식 도메인에 **최대 4회 GET**, 읽기 전용.
로그인/결제/주식 거래/원본 파일 영구 저장/프록시/재요청 없음.
이 문서는 실제 SEC GET 성공 증거가 아닙니다.

## Windows 로컬에서 1회 실행

저장소 `lead/kic` 최신 코드를 받은 뒤 루트에서 `RUN_P105_NVDA_SEC_PROBE.cmd`를 실행합니다. Python 3.11이 필요합니다. 터미널에서 `READ SEC NVDA`를 그대로 입력합니다. 그다음 표시되는 **실제 연락 가능한 이메일**을 로컬 콘솔에만 입력합니다(화면에 보이지 않고 코드/파일/로그로 저장되지 않음). **이메일을 채팅이나 GitHub에 게시하지 않습니다.** 이 값은 SEC User-Agent에 포함되어 SEC 서버에 전송됩니다. 승인하지 않거나 연락처 검증이 실패하면 요청 0회입니다.

필요 시 `python -B -m scripts.p105_authorized_nvda_sec_probe --as-of 2026-11-02`와 같이 기준일을 지정할 수 있습니다. 실행 결과 JSON은 원본이 아닌 상태/요청 횟수/출처 URL/바이트 해시/부분 재무 지표만 포함합니다. 출력 JSON을 채팅에 공유해도 연락처는 포함되지 않도록 설계했으나, 개인 신원을 드러낼 수 있는 내용이 없는지 검토하고 공유하십시오.

## 차단 / 완료 판정

- `SEC_ACCESS_DENIED_403` 또는 `SEC_RATE_LIMITED_429`: 즉시 중단, **반복 호출·우회 금지**. SEC webmaster/공식 지원 경로의 접근 정책 확인 후 별도 승인.
- 최대 4회 요청 중 실패: 부분 원본은 버리고 `UNAVAILABLE` 출력, 저장하지 않음.
- `SEC_RESPONSES_RECEIVED_UNVERIFIED`: 공식 SEC URL에서 4개 응답을 받았다는 로컬 실행 주장. 발행사/문서 진위·권리·회계값 보증이 아니며, CompanyFacts 연간 매출/iXBRL 확인과 Guard 미리보기는 별도 상태로 기록.
- Engine A/C: 가격·지수·산업 공급자 미연결이므로 `UNAVAILABLE`. 전체 A/B/C/Guard 완료나 투자 가능 결론 아님.
- Windows 환경/연락처/네트워크에 종속되므로 GitHub Actions는 **모의 HTTP만** 테스트. 실사용 검증에는 로컬 실행 결과와 정확한 코드 SHA가 필요.

SEC 공식 규칙: https://www.sec.gov/about/privacy-information
공식 API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
접근 장애 문의: https://www.sec.gov/about/webmaster-frequently-asked-questions
