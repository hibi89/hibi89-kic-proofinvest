# Disclosure Lightning (DL) — 최소작동단위

**KIC 저장소 `feature/disclosure-lightning` 전용.** SEC EDGAR 공시 **목록/메타데이터**를 수집해 SQLite에 원본 HTTP JSON과 해시를 불변 저장하고, 재실행 중복을 제거하며, 원본 공시 페이지 주소를 출력합니다. Python 3.11+ 표준 라이브러리만 필요합니다. 크몽 Bid_Owl 사업·입찰 CSV와 별개의 제품입니다.

## 지금 가능한 동작 (offline / synthetic)

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db /tmp/dl-demo.sqlite3 --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db /tmp/dl-demo.sqlite3 --list
python -m unittest tests.test_disclosure_lightning -v
```

Windows에서는 `/tmp/dl-demo.sqlite3` 대신 본인이 선택한 작업용 로컬 DB 파일 경로를 사용하세요. 모든 fixture 레코드는 **합성 자료**입니다. 첫 실행은 `SAVED`, 같은 파일을 다시 넣으면 `REUSED`와 `new_filings=0`이어야 합니다. SEC JSON의 **최근 공시(recent) 배열**에서 날짜와 폼 필터를 적용하며, SEC 원문이 아니라 API 메타데이터만 수집합니다. 수정공시는 독립 accession으로 보존합니다. 그 공시가 어떤 과거 공시를 수정했는지는 현재 자동 판별하지 않습니다.

## 실제 SEC 데이터 1회 조회 (explicit opt-in)

```bash
export DL_SEC_USER_AGENT="DisclosureLightning YourOrganization contact@your-real-domain.tld"
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --db /tmp/dl-real.sqlite3 --allow-network
```

PowerShell의 경우 `$env:DL_SEC_USER_AGENT = "DisclosureLightning YourOrganization contact@your-real-domain.tld"`를 사용합니다. **가짜 이메일(example.com 등)을 넣거나 허락 없는 연락처를 사용하지 마세요.** 위 문자열은 자리표시자이며 실제 식별 가능한 조직·연락처로 바꿔야 합니다. 정상적인 공식 SEC GET 1회만 시도합니다. 자동 반복/크롤링, 유료 API, 인증정보 저장, 숨은 프록시·리다이렉트는 없습니다. SEC 서버가 실패하면 실패로 종료하고 다시 요청하지 않습니다. SEC 허용 정책을 준수해야 합니다. 공식 규정: https://www.sec.gov/about/developer-resources

SEC 응답의 `INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED`는 **정상적인 SEC HTTPS 메타데이터를 받은 사실**만 의미합니다. 실제 10-K/10-Q 문서 바이트·본문 해시 `raw_sha256`는 **아직 수집하지 않으며 null**입니다. `index_raw_sha256`는 JSON 응답 자체의 해시입니다. 별도의 실제 응답/네트워크/공식 발행사 확인 없이 LIVE 검증이나 공시내용 인증을 주장하지 않습니다.

## KIC와 DL의 독립 경계

`RawFilingEnvelopeV1` 항목은 응답 `indexed.filings[]`에 있고, 이 JSON을 KIC ProofInvest의 별도 리더에 전달할 수 있습니다. `issuer_cik`, `accession`, `form`, `filed_at`, `collected_at`, `source_uri`, `index_raw_sha256`, `evidence_status`를 보존하세요. DL은 금융 지표 정규화·재무 판단·투자 권고나 자동매매를 담당하지 않습니다.

**이번 MVP의 명시적 부족 기능:** 원본 HTML/XBRL 원문 수집, 실제 SEC 라이브 호출 실측, SEC recent 이외의 과거 continuation 페이지, 회사명/티커 검색·CIK 매핑, 수정 관계 분석, ETag/429 재시도/스케줄러, 공급기관별 어댑터, API/GUI, 압축·용량정책, 보안·성능·윈도우 상용 검수. KIC 11월 12일 예선 PDF는 기존 대회장 양식만 제출하며, DL 코드의 완료 여부는 선행 조건이 아닙니다. `lead/kic`와 `main`에는 자동 병합하지 않습니다.
