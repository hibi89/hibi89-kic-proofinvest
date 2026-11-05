# P250 — FRED `NASDAQ100` 로컬 지수 CSV 대체 경로 (2026-11-06 KST)

**목적:** Massive 실제 `I:NDX` 일봉 주말 이상행 문제를 반복 조회하거나 잘못된 원본 날짜로 재배정하지 않고, **별도 원천인 FRED `NASDAQ100`의 사용자가 직접 취득한 일별 종가 CSV**를 개인 연구에 한하여 기존 Decimal Engine A와 연결한다.

## 검증된 사실·권리 제한

- 공식 지수: [FRED Nasdaq-100 NASDAQ100](https://fred.stlouisfed.org/series/NASDAQ100), **Nasdaq, Inc.** 출처, **Daily, Close**, Nasdaq-100 지수 자체이며 QQQ/ETF 프록시가 아니다.
- [FRED API Terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html): Nasdaq 원본은 제3자 **저작권 데이터**이며 개인용을 넘는 **상업·심사 공개·AI 처리·재배포는 별도 권한 검토가 필요**하다. FRED의 공개 페이지/CSV가 이를 자동 허가하지 않는다.
- 이 코드가 확인하는 것은 **로컬 파일의 표면 형식·일자·숫자·기간·해시**뿐이다. 다운로드 출처, 실제 공급자 서명, 수정/변조 여부, 사용자 이용권을 인증하지 않는다.
- 사용자가 CSV를 전달/첨부하거나 API를 실행할 의무가 없다. **GitHub에 실원본·API 키·개인 파일 절대 업로드 금지.** 서버/외부 GET은 이 경로에서 **0회**.

## P251 — KUODRA 로컬 종목 검색 UI 직접 사용 (외부 요청 0회)

실제 로컬 127.0.0.1 Streamlit 페이지를 활성화한 경우, 기존 첫 **SEC 자동 조회** 버튼 아래에 **「실제 Nasdaq-100 FRED CSV · 개인 로컬 Engine A」** 패널이 추가된다. 화면은 `KUODRA_ENABLE_LOCAL_SOURCE_UI=1`와 로컬 바인딩 조건을 모두 확인하고, 공용 바인딩/권한 누락 시 표시하지 않는다.

1. 상단에 단일 종목 티커 `AAPL` 같은 정확한 값을 입력하고, FRED CSV 원본의 마지막 관측치 이상이면서 현재 날짜 이하인 **조회 기준일**을 선택한다.
2. `FRED NASDAQ100 일봉 CSV`에 공식 시계열 형식의 파일을 업로드한다. 다운로드는 코드가 수행하지 않는다.
3. **베타 계산이 필요할 때만** 별도의 적법하게 구한 `date,close` 종목 CSV, 기업 CIK 10자리, 실제 공시일과 원천 HTTPS 표기 주소를 입력한다. 원천 주소를 입력해도 인증으로 승격되지는 않는다.
4. 개인 연구 동의 체크박스를 체크하고 **「FRED 공식 Nasdaq-100 CSV 오프라인 확인·Engine A 계산」** 버튼을 클릭한다.
5. 지수만 제출하면 관측치 수·기간·SHA256을 `미인증`으로 확인한다. 주식까지 제출한 경우 공시 후 **31개 이상 공통 유효 세션, 각 원천 80% 이상 중첩, 7일 신선도**와 실제 Decimal 베타/회귀 결과만 로컬 화면에 출력한다. 부적합·연결 권리 미확보 상태는 차단한다.

원본 업로드 바이트·주가/지수 종가행을 보고서나 채팅에 출력/저장하지 않는다. **실제 사용자의 원본 파일, FRED 공식 수집/출처 인증, Nasdaq 제3자 상업·심사 공개·AI 사용권은 이 코드에 포함되지 않는다.** 기존 Massive 실패 응답을 임의로 보정하지 않는다. 코드/단위 테스트는 합성 입력으로만 검증되었으며 사용자의 실제 파일을 받아 검증한 것이 아니다.

## 로컬 개인 연구용 사용법 (0 HTTP)

1. 사용자가 FRED 공식 NASDAQ100 페이지에서 **자신의 이용 조건을 확인**하고 필요하다면 일봉 CSV를 직접 저장한다. UTF-8 CSV 헤더는 `observation_date,NASDAQ100` (일부 옛 형식 `DATE,NASDAQ100`도 허용). FRED 미발표 `.`/빈 값은 건너뛰며 보간하지 않는다.
2. KIC 폴더에서 원본 파일 **읽기 전용** 검사:

   `python -m scripts.p250_fred_offline_check --fred-csv "C:\\data\\NASDAQ100.csv" --as-of 2026-11-03`

3. `LOCAL_FRED_CSV_PARSED_ORIGIN_UNVERIFIED` 결과는 **CSV 구조/31개 이상 유효 일봉 확인** 의미만 있다. `market_data_rights_verified=false`와 `network_requests=0`은 정상이다. 실패 시 원시 데이터 공유/반복 요청 대신 JSON의 고정 오류 코드만 확인한다.
4. 별도의 실제 종목 `date,close` CSV를 **적법한 원천에서 사용자 직접 취득**했다면, 아래처럼 동일 기준일·공시일을 지정해 **오프라인 실제 Decimal Engine A 설명용 계산**이 가능하다. `--stock-source-url`은 출처 **표시용 메타데이터**이며 URL만으로 증명되지 않는다:

   `python -m scripts.p250_fred_offline_check --fred-csv "C:\\data\\NASDAQ100.csv" --stock-csv "C:\\data\\AAPL.csv" --ticker AAPL --issuer-cik 0000320193 --filing-date 2026-07-31 --stock-source-url https://example.org/source --as-of 2026-11-03`

   위 명령은 **형식 예시**이다. 예시 공시일·출처 URL은 실제 사실을 의미하지 않는다. 파일의 `as_of` 이후 날짜는 거부한다. 31개 이상의 공시 후 **동일 거래일**, 양쪽 관측치 교집합 80% 이상, 최근 7일 이내 데이터 및 최대 7일 공백 등의 검증을 유지한다.

## 설계 선택·중단/전환 기준

| 경로 | 비용·성능 | 권리·위험 |
|---|---|---|
| Massive `I:NDX` 공식 문의 및 검증된 원본 재수신 | 기존 파서 재사용, 요청 제한 준수 | 이미 개인 실요청에서 토요일 ET 0시 행으로 반복 차단. 증거 없이 주말 행을 삭제·금요일로 변경 금지. 지원 요청은 사용자 별도 승인 필요 |
| FRED `NASDAQ100` 로컬 CSV (P250) | **실 API 요청 0회**, 동기식·경량 로컬 계산 | Nasdaq 제3자 저작권/사용권 미확보. CSV 원본 진위·FRED 조회 당시 시점·권리·공개 배포는 미인증 |

**P250 완료 기준:** 합성 CSV 파서·실제 기존 Engine A 연결·권리 HOLD 검사를 CI로 검증. **실 Nasdaq 출처 인증·상업 사용권·Production·공식 제출 점수는 추가 증거 확보 전 0점**. P249 76/100 기본 승인 점수는 임의로 상향하지 않는다.
