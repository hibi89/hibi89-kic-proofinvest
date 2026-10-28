## P5 — Explicit charset handling in archived HTML (2026-10-28 KST)

`disclosure_lightning.extract.extract_bytes` now reads a bounded first-4096-byte `<meta charset>` or `<meta http-equiv=... charset=...>` declaration **only** for `text/html`. It permits UTF-8, Windows-1252 and the HTML-specific `ISO-8859-1`→Windows-1252 mapping, with strict decoder failures. UTF-8 BOM conflicting with legacy declaration, unknown charset, or undecodable bytes are rejected. XHTML/XML/plain text retain strict UTF-8 (no HTML charset assumption). Parsed receipts expose `decoded_encoding`, `html_meta_declared_charset`, `charset_claim_verified=false`. A declaration contained in untrusted original HTML is NOT an independently verified header or a financial fact; do not infer authenticated issuer/file rights.

New tests: `tests/test_disclosure_lightning_extract.py` (+3 methods; declaration forms, rejection scenarios, false-attestation gates); local independently transcribed charset-helper smoke **8/8 pass**, NOT full repo suite. GitHub code SHA `8cd8e12d50dc1a9243e167a93d048786965efc8c`; exact-source GitHub Actions state unverified at handoff. No SEC HTTP used.

---

# Disclosure Lightning — Original Filing Bytes (P2)

## Actual stage

New `disclosure_lightning/originals.py` provides a **separate** source-preserving read/write path for one SEC primary filing from a previously indexed `filings` row. No source URL is accepted from the CLI; it must come from the existing, validated CIK+accession metadata row in the canonical DL SQLite DB. This is deliberately not yet a financial data extractor or KIC numeric verdict.

### Offline deterministic test (safe synthetic input only)

First prepare a disposable index (example for a Unix-style temp directory; Windows use local paths):

```bash
python -m disclosure_lightning --cik 0000320193 --as-of 2026-10-27 --collected-at 2026-10-27T00:00:00Z --db ./dl-local.sqlite3 --input-json disclosure_lightning/fixtures/sec_submissions_synthetic.json
```

Then explicitly supply a locally-created **synthetic** HTML file; this file is only for development and must NEVER be labelled as an SEC-fetched original:

```bash
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --input-file ./synthetic-filing.html
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --list
python -m unittest tests.test_disclosure_lightning_originals -v
```

The first import returns `SAVED`, an identical second import returns `REUSED`. Both keep raw bytes, `filing_sha256` and the acquisition origin `OFFLINE_FILE_UNVERIFIED`. Different bytes under the same filing ID append another receipt; previous ones remain unchanged. The original SEC submissions response and its separate `index_raw_sha256` remain intact.

### Real SEC primary HTTP (opt-in, not yet provider-verified)

1. Use `python -m disclosure_lightning --allow-network` to fetch official `submissions/CIK##########.json` metadata **first**, with a true contact-bearing SEC `DL_SEC_USER_AGENT`. Synthetic/offline metadata is NOT accepted for live original retrieval.
2. For a CIK/accession already indexed as `INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED`, run:

```bash
python -m disclosure_lightning.originals --db ./dl-real.sqlite3 --cik 0000320193 --accession YOUR_VERIFIED_SEC_ACCESSION --allow-network
```

The same `DL_SEC_USER_AGENT` environment variable is required in both commands. `YOUR_VERIFIED_SEC_ACCESSION` is a placeholder, not a valid accession. The original GET is limited to its official `https://www.sec.gov/Archives/edgar/data/...` primary file, with a bounded size (25MB), 15-second timeout, no external proxies, redirects, background crawling or invisible follow-on links. Transient failures receive at most three bounded attempts. If a saved archive response has a valid ETag, the CLI sends `If-None-Match`; a 304 reuses only the cached BLOB whose SHA-256, source URL and content type match the validator record. The original BLOB remains append-only by digest, and the HTTP check records whether the body was newly returned or reused. A 304 without a verified cache fails closed. This behavior is tested with mocked responses; live SEC archive ETag support remains unverified. It accepts HTML/XML/plain text response types only; do not interpret 200/HTML as independent attestation or content-based SEC authentication. Follow SEC fair-access rules: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data .

A successful authorized HTTPS transfer is labelled `SEC_HTTPS_RESPONSE_UNVERIFIED`, `authenticated_external_source=false`. No live SEC request or actual original filing body has been validated in this development session. A `source_uri` found in a synthetic fixture is only a constructed link and cannot authorize live network mode.

### KIC / security boundary

- Import: `from disclosure_lightning.originals import read_original_bytes`; call `read_original_bytes(db_path=..., cik=..., accession=..., sha256=...)`. The SQLite database is opened read-only; content is returned only after recalculating SHA-256 and matching the selected digest. The caller must sanitize untrusted HTML and separately validate financial facts.
- The `original_filing_receipts` schema is **additive** to the canonical DL store. The already existing `proofinvest/dl_bridge.py` is metadata-only. Never automatically promote `raw_sha256` to official verification, or silently fuse original bytes into the KIC numeric verifier.
- A single per-file original response and bounded single-company submissions response are tested with synthetic/mock HTTP. No live SEC access, original-content claim certification, EDGAR pagination, 429 backoff, bulk synchronization, full KIC document extraction, or production/frontend release is proven. These are separate next acceptance gates.
- No customer data, SEC keys or private `hibi89/Bid_Owl` code is committed. The KIC public repo, Nov12 PDF-only preliminary requirements and the KIC lead's `lead/kic` approval gate remain unchanged.

## P3 — 근거 텍스트 추출·검토 후보 (2026-10-28)

새 `disclosure_lightning/extract.py`는 로컬 원본 바이트를 SHA-256으로 다시 확인하고, **완전 오프라인**으로 텍스트 조각을 추출합니다. 외부 링크, 임의 HTML/스크립트 실행, 숫자 해석, AI 및 자동 투자 판단은 하지 않습니다.

실제 SEC 원문 없이도 합성 HTML 파일로 전체 경로를 실행할 수 있습니다:

```bash
# 1) 이미 SEC 모양의 합성 index를 저장한 경우, 테스트 HTML을 로컬에 직접 준비
# 2) 그 파일을 'OFFLINE_FILE_UNVERIFIED'로 저장 (선언한 MIME은 인증 근거 아님)
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --input-file ./synthetic-filing.html --content-type text/html
# 3) Read-only receipt listing can be restricted to an as-of date
python -m disclosure_lightning.originals --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --list --as-of 2026-10-28
# 4) 위 결과의 filing_sha256에 실제 출력된 64자리 값을 넣어 근거 추출
python -m disclosure_lightning.extract --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --sha256 YOUR_ACTUAL_FILING_SHA256 --as-of 2026-10-28 --summary-only
python -m disclosure_lightning.extract --db ./dl-local.sqlite3 --cik 0000320193 --accession 0000320193-25-000901 --sha256 YOUR_ACTUAL_FILING_SHA256 --as-of 2026-10-28 --find Revenue
```

- `originals --list --as-of` filters the indexed filing and byte receipt to the UTC end of that date. The low-level `locate_original()` and `read_original_bytes()` APIs also accept optional `as_of` for read-only consumer integration.
- `extract` requires `--as-of`; it filters the filing's indexed `filed_at`/`collected_at` and original byte receipt's `retrieved_at` to the UTC end of that date. A later-added original cannot appear in a historical evidence result.
- `--find`는 정규식이 아니라 단순 리터럴 대소문자 무시 검색입니다. UTF-8 HTML에서 원문 문자와 byte sequence가 정확히 일치하는 텍스트 노드만 원본 바이트 시작/끝과 span SHA-256을 제공합니다. 엔티티 변환 등에서 일치하지 않는 조각은 `HTML_PARSER_LINE_HINT`로 남습니다. 두 유형 모두 사람이 검토해야 하며, span은 출처 진위나 금융 주장을 인증하지 않습니다.
- 텍스트가 250,000자/1,200블록 등 제한을 초과하거나 HTML의 숨김 태그가 닫히지 않으면 `truncated=true`가 되며 CLI는 종료코드 2로 비완료임을 알립니다. 출력한 일부 문장을 전체 공시의 완전한 내용으로 주장하면 안 됩니다.
- UTF-8 이외 인코딩·비지원 형식(PDF 등)은 명시적으로 거부합니다. 실제 SEC 제출 HTML의 복잡한 렌더링, Inline XBRL 문맥, 재무 주석, 표 구조·의미 분석, 출처 독립 인증은 여전히 **미구현/인간 검토 필수**입니다. HTMLParser는 스크립트·style·head를 추출에서 제외하며 별도 브라우저 렌더링이 없습니다.
- KIC의 `proofinvest/dl_bridge.py`는 **현시점 메타데이터 검산용**입니다. 근거 추출 반환물을 실제 금융 사실 검증·RAG에 연결하려면 KIC 총괄이 `source_span` 계약을 승인하고 교차 브랜치 테스트를 수행해야 합니다. `financial_claim_verified=false`, `source_authenticity_verified=false`를 유지해야 합니다.
