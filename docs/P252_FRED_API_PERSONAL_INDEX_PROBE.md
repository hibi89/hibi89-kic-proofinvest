# P252 — 무료 FRED 공식 API 실제 NASDAQ100 1회 조회

기능: `fred/series/observations`, `series_id=NASDAQ100`, `file_type=json`, `units=lin` 일별 종가를 로컬 사용자 키로 **명시적 개인 연구 승인 시에만 최대 1회** 조회. 벤치마크는 **실제 Nasdaq-100**이며 QQQ/ETF 대용 아님.

## 선택 근거 (2026-11-06 KST)

- **Alpha Vantage**: 기존 `market_provider_alpha_vantage.py`는 주식 일봉으로 동작 가능하지만 진짜 NDX `INDEX_DATA&symbol=NDX&interval=daily`는 [공식 문서](https://www.alphavantage.co/documentation/)상 **Premium**. 무료 키/권리 미확인 상태에서 자동 호출/구독/결제 금지.
- **Twelve Data**: 개인 Basic은 일반 미국 주식 중심이며 [지수 API](https://twelvedata.com/indices) 제공 표기는 있지만 **NDX의 무료 Basic 개인 실사용 entitlement 미검증**. 결제/권한 변경 금지.
- **FRED**: 공식 [NASDAQ100](https://fred.stlouisfed.org/series/NASDAQ100)는 Nasdaq 출처 실제 지수 종가. [FRED v1 series observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)는 개인 등록 API 키로 일자 범위·기준 vintage 지정이 가능한 JSON 정식 API. [무료 FRED 계정](https://fred.stlouisfed.org/help/account/fred-account-features/register/)으로 별도 키 발급 가능. 코드/제출자는 키를 받거나 저장하지 않는다.

## 실행 방법: 사용자 Windows에서만 키 입력

```cmd
git pull origin lead/kic
python -m scripts.p252_fred_ndx_api_probe
```

기본 출력은 `DRY_RUN_NO_REQUEST`로 **외부 요청 0회**.

실제로 FRED 계정을 만들고 API 키를 발급받은 소유자가 **FRED API 약관과 개인용 권한을 확인하여 새 단발 조회에 동의했을 때만**:

```cmd
python -m scripts.p252_fred_ndx_api_probe --live
```

`REQUEST FRED NASDAQ100 PERSONAL` 입력 후 32자리 소문자·숫자 FRED API 키를 로컬 숨김 입력. **정확히 한 번의 직접 HTTPS GET**, 리디렉션·프록시·재시도 금지, 8초/256 KiB 제한, 최근 안전하게 마감된 2개 평일 전까지 시계열. `--as-of YYYY-MM-DD`는 추가 히스토리 고정 검사이며 미래·미완료 거래일 차단.

정상 응답도 `FRED_API_DAILY_PARSED_ORIGIN_AND_RIGHTS_UNVERIFIED`만 출력한다. 거래일·관측치 수·기간·원본 JSON SHA256 해시만 출력, **원본 종가·API 키·전체 응답·URL·HTTP 오류 본문·접수 쿠키는 저장·출력 안 함**. 주말/미래 일봉, 오래된 시계열, 중복·누락·변조 응답을 자동 복구하지 않는다. 실패 때 **추가 실행 없이 결과 JSON만 확인**. 다회 실제 요청은 새 승인 필요.

## 권리·기술 한계

- [FRED API 약관](https://fred.stlouisfed.org/docs/api/terms_of_use.html) 준수 및 사용자 개인 키 등록 필수. 앱에 **“This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.”** 고지. FRED 공개 조회 권한은 원본 **Nasdaq 저작권 데이터의 상업적 이용·공개 심사·AI 모델 처리·재배포 권한을 자동 제공하지 않음**.
- FRED v1 일봉 응답 JSON에는 강제적 `series_id` 인증 서명이 없어 요청 URL에 `NASDAQ100`을 지정했더라도 **공급자 원문 인증/데이터 사용권 false** 유지. 응답을 재배열해 출처를 인증하지 않는다.
- P250 개인용 로컬 CSV 경로·P251 로컬 UI와 병행한다. P252 CLI는 데이터 원본을 디스크에 저장하지 않으며 Engine A/B/C 공개 사용을 자동 활성화하지 않는다. 실제 조회·소유자 이용권·Production·공식 제출은 미검증. 최종 점수는 별도 증거 확보 전 76/100, RELEASE HOLD.
