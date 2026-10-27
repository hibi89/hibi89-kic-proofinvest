## P10 — SEC point-in-time 보수적 처리 (2026-10-28 KST)

같은 UTC 날짜의 공시를 조회하면서 원본 SEC-style 인덱스의 `acceptanceDateTime`이 누락되거나 timezone 없는 문자열인 경우, **그날 특정 관측 시각보다 먼저 접수됐는지 증명할 수 없어 해당 행을 제외**합니다. 이 규칙을 최근 `index_submissions`와 과거 `history.index_history_page`에 함께 반영했습니다. 유효한 timezone-aware 접수 시각은 P9부터 관측 UTC 시각과 정확히 비교합니다. 관측일 이전 날짜의 공시는 기존 일자 범위 기준으로 유지하며, SEC 독립 인증 여부는 계속 거짓입니다. 이는 로컬 관측 시각을 주장하는 데이터의 look-ahead 위험을 줄이는 것이지 원본의 실제 입수·게시 시각을 인증하는 것은 아닙니다.

회귀 테스트 두 개가 `tests/test_disclosure_lightning.py`에 추가됐습니다. **현재 검증 근거는 이전 P6 로컬 호환 shim 9/9 PASS + P10 동등한 판단식의 독립 경계 검사 6/6 PASS뿐**이며, 최신 GitHub 브랜치 전체 `unittest`/Actions는 조회되지 않아 **미검증**입니다. 별도 공식 제출물/데모/KIC 코드/실 SEC 통신은 변경하지 않았습니다.

---

## P9 — 관측 이전 접수 시각 검증 (2026-10-28 KST)

최근 공시와 과거 `filings.files`의 **알려진 timezone-aware `acceptanceDateTime`**이 로컬 `collected_at` 관측 시각보다 늦으면 그 행은 제외합니다. 종전 구현은 `filingDate` 날짜만 비교하여 **같은 날짜 내 미래 접수**를 잠재적으로 포함할 수 있었습니다. 이번 수정은 `2026-10-28T12:00:00+09:00` (03:00 UTC) 행이 02:59:59 UTC 관측에서는 제외되고 03:00 UTC 관측에서 포함되는 경계를 명시합니다.

소스 파일: `disclosure_lightning/core.py` (최근), `disclosure_lightning/history.py` (과거); 회귀 테스트 2개 추가: `tests/test_disclosure_lightning.py`. 인식 불가능한/시간대 없는 `acceptanceDateTime`은 기존과 같이 `accepted_at=null`로 처리하며, 명시적 정밀 시간 근거가 없다고 보아 오프라인 공시 출처가 인증되었다고 주장하지 않습니다. **인덱스 JSON에 기재된 자체 시각은 독립적으로 인증되지 않은 값**입니다. 기존 원본 해시·SQLite 스키마와 미병합 KIC 경계는 변경하지 않았습니다.

로컬에서 기존 P6 shim을 확보했지만 현재 전체 저장소의 checkout이 아니므로 **P9 전체 CI/테스트 PASS는 미검증**입니다. GitHub Actions push run을 반환하지 않는 connector 도구를 통해 0 status를 관찰했으며, 0건은 통과가 아닙니다.

---

## P8 — 수정공시 후보 확인 (오프라인·읽기 전용)

SEC Submissions 인덱스를 로컬 SQLite에 저장한 뒤 다음 명령으로 수정공시(10-K/A, 10-Q/A, 8-K/A)의 **검토용** 후보만 조회합니다.

```bash
python -m disclosure_lightning.history --db ./dl.sqlite3 --cik 0000320193 --as-of 2026-10-28 --review-amendments
```

이 모드는 `--manifest-sha256`, `--name`, `--collected-at`, `--input-json`, `--batch-dir`와 함께 사용할 수 없으며 어떤 새 관측 또는 공시도 저장하지 않습니다. 기존 `filings.filing_json.amends_accession`을 변경하지 않습니다.

판정은 해당 공시의 저장된 인덱스 원본 JSON(`index_raw_sha256`)을 해시 검증하고, SEC 메타데이터의 `reportDate`, 원래 유형(10-K/10-Q/8-K), **더 이른 filingDate**, CIK이 모두 일치하는 과거 원본 후보만 고려합니다. **정확히 한 개**이면 `UNVERIFIED_PERIOD_MATCH_CANDIDATE`, 여러 개면 `AMBIGUOUS_MULTIPLE_BASE_MATCHES`, 원래 `reportDate`가 없으면 `REPORT_PERIOD_MISSING_NO_INFERENCE`, 일치 원본이 없으면 `NO_UNIQUE_BASE_MATCH`. `authoritative_amends_accession=null`과 `authenticated_amendment_relation=false`는 항상 유지합니다. 원본이 실제 수정 대상이라는 뜻은 아닙니다. 보고기간·인덱스 출처가 의심되거나 원본 해시가 불일치하면 안전하게 오류 처리합니다. 관측 시점이 조회 마감일보다 늦은 자료는 제외합니다. 기본 검사 500건, 최대 2,000건이며 미완전 구간은 오류로 표시하고 출처 응답 스캔에는 최대 128건/128MB 예산을 설정했습니다.

**검증 상태:** 회귀 테스트 5개 코드로 추가 완료. 이 브랜치의 *실제 전체 GitHub Actions 또는 전체 unittest 결과는 아직 확인되지 않았습니다*. 모든 로컬 기록은 `OFFLINE_UNVERIFIED` 경계를 유지합니다. <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>

---

## P7 — 과거 SEC 공시 JSON 다중 페이지 오프라인 처리 (2026-10-28 KST)

기존 `python -m disclosure_lightning.history`를 확장했습니다. **실제 SEC 자동 다운로드는 하지 않습니다.** 먼저 저장된 메인 Submissions 응답의 고정 SHA-256을 기반으로 공식 `filings.files[]`에 기재된 페이지명/건수/날짜를 조회합니다.

```bash
# 기존 원본 index를 저장한 뒤, 해당 저장 결과의 raw_index_sha256을 사용
python -m disclosure_lightning.history --db ./dl.sqlite3 --cik 0000320193 --manifest-sha256 YOUR_64_CHARACTER_HASH --as-of 2026-10-28 --list-manifest

# --batch-dir에 저장된 정확히 일치하는 페이지명만 로컬에서 읽음
python -m disclosure_lightning.history --db ./dl.sqlite3 --cik 0000320193 --manifest-sha256 YOUR_64_CHARACTER_HASH --as-of 2026-10-28 --collected-at 2026-10-28T01:05:00Z --batch-dir ./downloaded-sec-history --max-pages 4
```

한 번에 기본 4페이지·최대 8페이지, 각 파일 최대 8MB·총 32MB. 읽기 전 경로/심볼릭 링크/일반 파일을 검사하고 보관 모듈의 `O_NOFOLLOW` 로컬 파일 리더를 재사용합니다. 저장 전에 **모든 선택 페이지**의 manifest 등록 여부·관측 시각·페이지 크기·날짜 범위·배열 구조·accession 중복·원본 digest를 검증합니다. 불일치 시 해당 배치를 전부 거부하고 새 저장을 시작하지 않습니다.

**저장은 여러 페이지를 하나의 SQLite 트랜잭션으로 묶지 않습니다.** 각 페이지를 기존의 idempotent `core.save_index`에 순차 적용합니다. 저장 도중 장애가 나면 `HISTORY_BATCH_PARTIAL_WRITE:x/y:completed=...` 오류로 성공적으로 저장된 페이지 목록을 표시하고, 동일 입력을 다시 실행해 나머지를 처리합니다. 원본 byte SHA는 `index_raw_sha256`로 저장하고 실제 SEC 원본 공시의 `raw_sha256`는 계속 null입니다. 출력 `OFFLINE_UNVERIFIED`는 인증이 아닙니다.

검증: 새 테스트 5개를 `tests/test_disclosure_lightning.py`에 추가(중복/사전검증/폴더/CLI/중간 장애 재개). **GitHub 정확한 HEAD의 전체 CI 결과는 아직 확보하지 못했으므로 PASS로 주장하지 않습니다.** KIC `lead/kic` 통합/UI/제출 파일은 변경하지 않았습니다.

---

## P6 — SEC 과거 공시 continuation 오프라인 인덱싱 (2026-10-28)

공식 SEC Submissions의 `filings.files[]`는 이전 연도 `CIK##########-submissions-###.json` 페이지를 가리킵니다. DL은 **새로운 네트워크 자동 요청을 추가하지 않고** 사전에 저장된 메인 submissions 응답의 `source_sha256`를 고정해, 명시적으로 제공받은 로컬 history JSON만 수집할 수 있습니다.

1. 기존 `python -m disclosure_lightning`으로 실제/합성 main submissions JSON을 SQLite에 먼저 저장합니다. 파일에는 `filings.files`와 페이지명·날짜 범위·건수가 있어야 합니다.
2. 첫 실행 결과의 `raw_index_sha256`를 다음 명령의 `--manifest-sha256`에 사용합니다. 예시 이름은 실제 저장된 manifest 파일명과 일치해야 합니다.

```bash
python -m disclosure_lightning.history --db ./dl.sqlite3 --cik 0000320193 --manifest-sha256 YOUR_EXISTING_64_CHAR_MANIFEST_HASH --name CIK0000320193-submissions-001.json --input-json ./saved-history.json --as-of 2026-10-28 --collected-at 2026-10-28T00:05:00Z
```

**검증 경계:** 역사 페이지 자체는 상위 JSON의 `filings.recent` wrapper 없이 나열된 병렬 배열이어야 합니다. 고정 메인 원본 SHA·CIK·SEC page basename·filingCount·날짜 범위·accession 중복·배열 정렬·관측 시간 순서·8MB 제한을 확인합니다. 동일 페이지 재수집은 기존 `observations`/filing 상태를 재사용합니다. `index_raw_sha256`는 **페이지 JSON 바이트의 해시**, `raw_sha256`는 여전히 수집되지 않은 공시 원문이라 null입니다. 입력 provenance는 언제나 `OFFLINE_SOURCE_UNVERIFIED`이며, 사용자가 선언한 과거 시각은 실제 SEC 관측 인증이 아닙니다. 대량 다운로드/페이지 자동 추적/429 백오프/실 SEC HTTP는 **미구현**입니다. 공식 SEC API 개요: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

새 모듈 `disclosure_lightning/history.py`, 테스트 `tests/test_disclosure_lightning.py::test_history_continuation_pinned_offline_dedup`. 추가 로컬 9개 시나리오 통과는 *코어 호환 테스트용 shim 환경*의 결과로 실제 저장소 전체 CI와 다릅니다. GitHub Actions 최신 결과는 별도 확인해야 합니다.

---

# Disclosure Lightning (DL) — 최소작동단위

**KIC 저장소 `feature/disclosure-lightning` 전용.** SEC EDGAR 공시 **목록/메타데이터**를 수집해 SQLite에 원본 HTTP JSON과 해시를 불변 저장하고, 재실행 중복을 제거하며, 원본 공시 페이지 주소를 출력합니다. Python 3.11+ 표준 라이브러리만 필요합니다. 크몽 Bid_Owl 사업·입찰 CSV와 별개의 제품입니다.

## 지금 가능한 동작 (offline / synthetic)

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --collected-at 2026-10-27T00:00:00Z --db /tmp/dl-demo.sqlite3 --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json
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

## 2026-10-28 검증 게이트 (KIC 합의)

- 표준 모듈은 **`disclosure_lightning/core.py`** 단일 구현입니다. 중복 실험 버전 `mvp.py` / `cli.py`는 제거됐습니다. 다른 SQLite 저장 형식을 혼용하지 마세요.
- `--collected-at`은 오프라인 파일의 **실제 확인 가능한 최초 수집 시각**(타임존 필수)을 명시할 때만 사용합니다. 이를 증빙할 수 없으면 과거 시점의 수집증거라고 주장하지 마세요. 인덱스는 UTC로 정규화되며 수집시각이 `--as-of` 다음 날이면 실패합니다. 수집 날짜보다 뒤의 공시도 제외합니다. SEC 실제 요청의 경우 `--collected-at`을 넘길 수 없고 시스템 수집시간을 사용합니다.
- `DL_SEC_USER_AGENT`는 실존하는 사용자/조직의 연락 이메일이어야 합니다. `example.com`, `placeholder`, `your-real-domain.tld` 등 예시를 통한 요청은 거부합니다. 원문 공시 HTML 다운로드는 아직 **미구현**이며 SEC JSON 해시와 혼동하지 마세요.
- KIC 검산과 대응하는 합성 단일 공시 테스트 fixture: `disclosure_lightning/fixtures/kic_apple_handoff_synthetic.json`. 이것은 실제 SEC 응답이 아니라 KIC 측 `proofinvest/dl_bridge.py`와 연동할 때 사용할 **정합성 테스트 입력**입니다.
