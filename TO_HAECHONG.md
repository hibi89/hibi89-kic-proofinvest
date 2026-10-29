## 2026-10-29 KST — 해총 확인 요청: KIC GitHub 미통합 구성요소 실사 (최우선 확인사항)

> **형의 직접 지시:** "KIC에 들어가는 GitHub 애들 다 넣은 거 맞나, 어떻게 완성이 되지?" → 아직 최종 통합 완료 아님. 해총은 아래 실제 브랜치·코드·테스트를 교차확인하고, **예선 제출 완료와 본선 제품 완성률을 분리**해서 보고할 것. 이 문서는 미완료 작업의 검수 요청이지 자동 전체 병합 승인, PDF 업로드 승인, 외부 API 실행 승인이 아님.

**실사 기준 저장소:** `hibi89/hibi89-kic-proofinvest` · `lead/kic@6359418dec87c162bc1310ddcccbb0e49d0c1400` · 비교 DL `feature/disclosure-lightning@760ddd3a0e4ad5814e76146c0d536bebc4520f81`. 최신 원격 상태가 바뀌면 SHA와 차이를 다시 검증할 것. [실사 때의 KIC offline-tests](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40884902870) **SUCCESS**: Guard 43개 회귀 테스트 통과, Chromium Guard 클릭 검증 PASS. 이는 **오프라인·수동 정리된 SEC 형식 데이터의 검사**이지 SEC 실제 데이터 인증/본선 앱 완료 증거가 아님.

### A. 현재 들어가 있고 검증된 부분

- `lead/kic/proofinvest/`: Research, Verification, Risk 및 SEC 검토/증빙 처리 모듈, `dl_bridge.py`, `sec_three_source.py`, `sec_bundle_replay.py`, `guard_agent.py`, `guard_workflow.py`, `guard_audit.py`, `guard_review.py` 등 **코드 존재**. 기능마다 검증 범위가 다르므로 존재 자체를 운영 완성으로 계산하지 말 것.
- `streamlit_app.py`: 합성/수동 SEC·Guard 검토 화면과 저장/감사 경로. 최신 Chromium 클릭 검증은 오프라인에서 성공했으나 외부 SEC 원문 인증과 실거래는 아님.
- `lead/kic/disclosure_lightning/`: `core.py`, `originals.py` 등 **부분 사본/브리지 존재**. 따라서 "DL 전혀 없음"도 "DL 최신판 전체 통합"도 아님.
- `feature/research`, `feature/verification`, `feature/risk`, `feature/kic-dl-integrated-mvp` 브랜치가 존재. **브랜치 존재나 과거 이관 기록만으로 최신 변경이 모두 `lead/kic`에 반영되었다고 판단하지 말 것.**

### B. 해총이 비교·검수할 미통합 또는 미검증 항목

| 우선순위 | GitHub 구성요소 / 목표 | 현 실사 결과 | 해총 다음 확인 및 수용 조건 |
| --- | --- | --- | --- |
| **P0** | **Disclosure Lightning 최신 기능** · `feature/disclosure-lightning` → `lead/kic` | DL 측에 있으나 KIC `lead/kic`의 `disclosure_lightning/`에는 없는 경로 **5개**: `companyfacts.py`, `extract.py`, `history.py`, `xbrl.py`, `fixtures/kic_apple_handoff_synthetic.json`. 단, KIC 자체 `proofinvest/sec_companyfacts.py` 등과 기능 중복 가능 | **파일/함수 수준 변경·중복·라이선스·의존성·테스트** 대조 후 KIC에 실제 필요한 어댑터만 선별 통합. 전체 DL 브랜치 일괄 병합 금지; 실제 SEC CIK/접수번호/출처·원문 해시/기간 계약 E2E 검사. DL 작업 브랜치 소유자의 변경 보호 |
| **P0** | **실제 SEC 공식 공시 기반 end-to-end** | 3자료 Submissions·CompanyFacts·원문 연결과 오프라인 ZIP/출처 스팬 코드는 있으나 **실 SEC 요청·원문 진위·권리·동작 호환성 미검증**. 수동 자료/합성 CI를 실증으로 승격 금지 | 사용자 명시 승인, 준수 가능한 SEC 연락처 포함 User-Agent, 적법한 이용조건 검토 **이후에만** 실제 SEC 1개 기업 자료로 검증. 실 호출 없이 가능한 계약검사는 선행 진행 |
| **P1 / 본선** | **SMAX `preprocessing` 전처리기** | KIC 내 직접 연동/완성된 표준 계약 **미검증**; Python KIC가 SMAX의 JS 모듈을 바로 import할 수 없음 | 먼저 외부 브랜치 상태·권리 검증. 필요 시 JSON/CLI 데이터 계약만 연결, 검증·기간/단위/출처 보존. 예선의 필수 의존성 아님 |
| **P1 / 본선** | **AI_AutoML_Analyst** | KIC용 모델/평가 엔진 직접 통합 **미완료**. 기획서에는 **선별 평가/시각화 로직만 재사용** 명시 | 학습 라벨·시간 누출·실제 기업 holdout이 확보되면 필요한 sklearn 로직만 이식·비교. 검증 불가 시 `NO_TRAIN`. 별도 AutoML 서비스 통째로 이식하지 말 것 |
| **P1 / 본선** | **사전학습 DL 공시문서 검색** | MiniLM 등은 설계/후보이며 KIC 실제 학습·추론 성능 수치 및 인용 스팬 품질 미검증 | 라이선스·모델 리비전 확인, SEC 원문 스팬 기반 BM25/키워드 대비 검색 품질과 CPU 성능 측정 후 선택. 숫자 검산을 DL에 맡기지 말 것 |
| **P1 / 본선** | **미국 주가지수 3종 + 인플레이션 4종** | S&P 500, Nasdaq-100, DJIA + 미국·중국·유로지역·일본 CPI/HICP YoY는 **확정 설계**, 실제 시계열 수집/릴리스 시점·시각화 미연동 | 출처 사용권·역사적 발표일·데이터 빈도·ETF와 지수 차이 검증 후 본선 범위로 추진. 예선 제출 전 신규 데이터 API 필수 아님 |
| **P1 / 본선** | **심사위원용 실제 동작 URL·통합보고서** | 오프라인 Python/Streamlit과 CI 증거 존재; **공개 판정 가능한 본선 URL, 실제 기업의 출처 인증형 E2E, 최종 발표자료 미완료** | 실제 SEC→Research→Verification→Risk→Guard→사람 검토→근거 표시 보고서의 한 기업 시나리오를 브라우저로 검증. 검증 범위와 미검증 범위 동시 공시 |
| **제외 / 병합 금지** | DBVORA, SOVIA, Lightning Azent, 전체 Bid Owl, 새 범용 RAG, 전체 AutoML 서비스 | 현재 KIC 범위 문서에서 직접 의존을 배제/보류한 구성요소 | 별도 사용자 범위 변경 없이는 **넣지 말 것**. 전체 GitHub 저장소 개수만큼 합치는 것이 완성 조건이 아님 |

### C. 예선과 본선의 완료 게이트를 혼동하지 말 것

1. **예선 P0 (2026-11-12 10:00 KST):** 주최 측 **공식 7항목·10페이지 이내 PDF**만 필수. 비공개 최종 후보 파일의 정확한 **제목·SHA·페이지·출처·내용**을 형이 승인하고, **별도 명시적 승인 하에** DAKER 제출 및 **접수 영수증** 확인해야 완료. 기존 구버전 해시 핀 검사 우회/비공개 PDF 공개 저장소 업로드 금지. 전체 DL·SMAX·AutoML·DL 모델 통합 **예선 필수 아님**.
2. **본선 P1 (진출할 경우 2026-12-22 10:00 KST):** 위 필요 요소 선별 통합, 실 SEC 1개 기업 기반 E2E, 검증 가능한 데모 URL/코드/발표 PDF. 출처·권리·데이터 미확보 시 구현/성능을 완료라 주장하지 말 것.
3. **완성률 검증:** 기존 KIC 60일 원장의 `29 DONE / 3 BLOCKED / 28 NOT_STARTED`는 2026-10-25 기준 **일정 관리 숫자**이지 "전체 제품 48% 또는 94%" 같은 제품 완성도 아님. 2026-10-29 코드·브라우저 CI 성공도 본선 전체 기능 완료율 산정 근거가 아님. PayPal 프로젝트의 94% 등은 KIC에 적용 금지.

### D. 해총 요청 행동 (순서)

1. 위 **DL 최신 브랜치 누락 5개**와 KIC 대체 구현을 실제 소스 함수/스키마/테스트 단위로 1:1 비교하고, **필수/중복/불필요**를 판정한 **통합 매트릭스**부터 작성.
2. `lead/kic`의 현행 Research·Verification·Risk·Guard 통합 테스트와 Streamlit/E2E 상태를 실제 CI SHA 기준으로 확인. 현행 제품에 필요한 **한 기업 근거 체인**에서 가장 큰 기능 단절점을 지정.
3. **예선 PDF 최종 승인/접수**를 최우선 별도 게이트로 유지하고, 본선 기능 미완료가 예선 제출을 지연시키지 않도록 함.
4. 본선용 SMAX/AutoML/DL/7계열은 **설계 대비 미구현**으로 별도 추적. 자동으로 KIC 저장소에 전체 코드 복제하거나 임의 병합하지 말 것.
5. 보고 시 "**현재 코드에 실제 포함 / 일부 연결 / 기능 중복·확인 필요 / 본선 계획 / 제외**"를 각각 구분하고, 새 코드·CI·실데이터 근거 없는 퍼센트는 추정이라고 명시.

**핵심 한 줄:** **KIC GitHub 관련 기능이 전부 최종 통합된 것이 아니다. 지금 가장 큰 기술 검수는 DL 최신판의 필요한 기능만 선별 통합하는지 여부와 진짜 SEC 출처 기반 E2E이며, 예선 제출은 별도로 공식 PDF 승인·접수부터 마무리한다.**

---

# [해총 확인 요청] KIC 외부 GitHub 구성요소 미통합·미검증 점검 (2026-10-29 KST)

> **사용자 직접 지시:** “그거 깃헙에있는거중에 안된거 해총한테하는말에 남겨놔라 해총이보고확인하게”. 이 섹션은 **해총이 다음 KIC 작업 시작 시 우선 확인할 미완료 통합 체크리스트**다. 아래는 `lead/kic` 실제 파일 트리(HEAD `6359418dec87c162bc1310ddcccbb0e49d0c1400`), 설계 문서, 브랜치 비교 기준이며 기능 존재·실환경 검증·최종 제출을 혼동하지 않는다.

## 1. 확인된 코드/브랜치 차이 — 최우선

- **Disclosure Lightning (DL): 부분 통합, 전체 병합 아님.** `lead/kic`에는 `disclosure_lightning/core.py`, `originals.py`, `proofinvest/dl_bridge.py`, `dl_source_span.py` 등이 있어 오프라인 색인·원문 연결은 가능하다. 그러나 `feature/disclosure-lightning`에 있는 **`disclosure_lightning/companyfacts.py`, `extract.py`, `history.py`, `xbrl.py`는 `lead/kic`에 없다**. 브랜치 비교 결과 **diverged**(DL feature 기준 ahead 239 / behind 198; 단순 병합 불가). **해총 액션:** 네 파일과 테스트/의존성/계약의 실제 최신 코드를 읽고 KIC에 필요한 기능만 선별하여 충돌 없는 통합 계획을 정하라. 무조건 병합·사유 없는 복사·비공개 Bid_Owl 소스 공개 금지. 실제 SEC 인증/실 HTTP 성공은 별도 증거가 필요하다.
- **Research·Verification·Risk feature 브랜치:** `lead/kic`에 `proofinvest/research.py`, `engine.py`, `risk.py` 등 구현이 존재하지만 세 feature 브랜치는 각각 `lead/kic`와 diverged(Research ahead 10 / behind 479; Verification ahead 4 / behind 479; Risk ahead 4 / behind 479). **해총 액션:** feature 쪽에 미반영된 *실제 유효 기능*이 있는지 diff와 테스트를 확인하라. 단순 ahead 숫자만으로 누락을 확정하거나 전량 병합하지 말 것.
- **실행 UI:** `streamlit_app.py`는 DL·Guard·intent router·SEC 관련 코드를 포함하지만 `rag`, `smax`, `azent` 호출은 현재 검색되지 않았다. **해총 액션:** 브라우저에서 데이터→검증→Guard→감사/보고의 한 흐름이 실제 연결되는지 확인하라. 모의 LLM 경로와 실제 Gemini 호출을 구분할 것.

## 2. 외부 프로젝트: 필수·선택 구분 (불필요한 강제 통합 금지)

| 구성요소 | 현재 확인 | 해총 판정/다음 조치 |
| --- | --- | --- |
| ProofInvest Research/Verification/Risk | KIC 브랜치에 코드 있음 | 통합 E2E 및 근거 정확성 검증 |
| Disclosure Lightning | KIC에 오프라인 부분 구현, feature에 추가 모듈 | **필요한 4개 모듈 차이 우선 감사** |
| Guard-Agent | 로컬 판정/사람 검토/SQLite 감사 구현 | 실제 SEC 근거와 묶인 end-to-end 확인 |
| LLM/Gemini | 모의 제안 게이트·실제 연결 함수가 존재하나 실제 API 동작은 별도 미검증 | 승인된 환경에서 실제 호출/거절·실패 처리 검증 |
| Lightning Azent (LA) | KIC 현재 런타임 의존성 아님 | 원 설계에서 명시적으로 **연동 보류**, 필수화 금지 |
| SMAX² | 범용 전처리 `hibi89/SMAX@preprocessing` 준비 여부 미확인 | 검증된 인터페이스가 있을 때만 선택적 연동 |
| RAG_STUDIO | KIC 런타임 미통합 | 현재 필수 아님; 문서검색은 별도 좁은 구현 가능 |
| AI_AutoML_Analyst | 시각화/평가 로직 일부 재사용 후보 | 본선 후 권리·품질 검증 뒤 선별, 전체 런타임 이식 금지 |
| CODE COUNCIL / HAE / REA / DBVORA | 현재 KIC 런타임 통합 근거 없음 | 필수 KIC 제품 구성 아님; 불필요한 통합 금지 |

## 3. 실제 제품 완성까지 남은 검증

1. DL 누락 모듈 **선별 검토** 및 실제 SEC Submissions/CompanyFacts/원문 간 출처 연결. 현재 실 SEC HTTPS/원본 인증/권리 확인을 성공했다고 주장하지 않는다.
2. 실제 LLM 의도 선택 → 허용 도구 → 숫자 검산 → Guard 판정 → 사람 승인/보류 → SQLite 감사 → Streamlit 결과/보고 **한 번의 재현 가능한 E2E**. 모의 모델 응답·합성 공시만으로 실제 API 성공 주장 금지.
3. 실제 SEC 공시 기준 수치·기간·단위·CIK/accession/원문 구간과 위험 판단의 신뢰 경계 검수. 필요 시 접근·연락처 UA·저장권한 등 사용자 승인 선행.
4. 본선용 심사 접근 가능한 URL, 실제 브라우저/배포/보안 검증 및 데모·발표 패키지(본선 진출 조건부).
5. **예선 제출은 별도:** 2026-11-12 10:00 KST까지 주최 측 공식 10슬라이드 PPTX를 정확한 7개 필수 섹션에 맞게 채운 **10페이지 이내 PDF**, 사용자 최종 확인, DAKER 제출/접수증. 공식 원본 PPTX는 GitHub Actions `40884902830`에서 무결성 확인·artifact 확보. 양식 다운로드 성공 ≠ 내용 이식/최종 PDF 승인/제출 완료.

## 4. 완료율 정정 및 해총 의사결정 요청

- 과거 언급한 **96%는 예선 MVP·기획서 작업의 잠정치**이며, KIC 전체 제품 통합률로 사용할 수 없다. **전체 통합률은 실제 E2E·실 SEC·실 LLM·배포 증거가 확보되기 전까지 미산정**.
- CI 성공(예: `lead/kic` 최신 `40884902870`)은 해당 커밋의 오프라인/모의 테스트 증거일 뿐 실제 SEC·Gemini·제출 성공이 아니다.
- **해총에게 요청:** (a) 위 외부 프로젝트별 필요/제외를 확정, (b) DL feature의 네 모듈 중 KIC 필수만 추출, (c) 통합 E2E 우선순위와 검증 게이트 설정, (d) 예선 PDF와 본선 제품을 분리하여 각각 진척·잔여시간 보고. **필요한 통합이 끝나기 전 'KIC 전체 100%' 선언 금지.**

---

## 2026-10-28 KST — 후속 확인 및 미완료 항목 정정

- **후속 개선 확인:** 기존 보고서 §7의 “새 검사 명령 직접검증”은 더 이상 다음 작업이 아니다. 현재 `.github/workflows/ci.yml`에서 `python -B -m scripts.verify_local --full`을 직접 실행하며, 기능 커밋 `175e53027a456afa61ee98c46d7d55d3f01a0d12`의 기록된 Actions 결과는 **486/486 PASS**다. 이 한 명령 검증 경로는 구현·CI 연결 완료로 처리한다. Windows 사용자 PC에서의 실제 실행은 여전히 미검증.
- **이번 오프라인 예선 PDF 재검사:** Library에 있는 V4 clean 후보를 읽기 전용으로 검사했다. 파일 바이트 SHA-256/크기 일치, PDF 10페이지·비암호화, 필수 7영역 문자열, 외부 링크 4개, 10페이지 렌더 확인을 통과했다. 이는 문서 형식 검사이며 주최 측 수락·실제 SEC 자동 연동·사용자 승인 증거가 아니다.
- **제출 게이트 유지:** 기존 pinned PDF 검사기는 옛 동결 파일의 정확한 바이트만 통과시킨다. 새 후보를 위해 해시 고정·검사 우회·DAKER 업로드/최종 제출을 하지 않는다. 참가자의 정확한 후보 파일/제목 승인과 별도 제출 승인은 여전히 필요하다.
- **다음 승인 불필요 작업:** 중복 CI 재조회·문서 복제·합성 전용 기능 확장을 피한다. 다음 실질 작업은 후보의 근거/표현과 현재 제출 동결 범위 간 모순 여부를 점검하고, 발견된 실질 오류만 수정 후보로 제시하는 것이다. 실제 SEC 요청, 사용자 PC 실행, PDF 승인 및 DAKER 제출은 별도 승인/환경 게이트다.

---

# TO_HAECHONG.md — 해총 직접 검수용 KIC 개발 효율 개선 보고서

**기준:** 2026-10-28 KST · 저장소 hibi89/hibi89-kic-proofinvest · 실제 브랜치 lead/kic.  
**비교 SHA:** 개선 전 문서 HEAD 398070567dc0c35f17c17dc8451b8d8c79b88e8d, 개선 후 기능 175e53027a456afa61ee98c46d7d55d3f01a0d12.  
**핵심 질문:** 기존 병목은 과도한 GitHub/문서 절차와 분리된 로컬 검증·재분석 경로였고, 이를 기능 단위 커밋/선별 문서/단일 검증 명령으로 축소하면서 SEC 보존 ZIP의 오프라인 재분석 기능을 실제 추가했다. 작업시간은 계측하지 않아 절감률은 미확인.

## 1. 기존 병목 TOP 3

1. **다수 문서 갱신과 별도 커밋:** 기능 후 STATUS, HANDOFF, KIC_RESUME_STATE, DAILY_PROGRESS, KIC_DL_REVIEW, TO_DL_LEAD 등 6개 문서를 사실상 중복 편집하고 코드·문서를 나눠 커밋했다.
2. **동일 CI/HEAD 반복 조회:** 작업 중 GitHub Actions 진행 상태와 동일 SHA를 여러 차례 폴링했다. API 기반 편집·테스트 흐름의 실제 진행을 막는 절차였다.
3. **실행/데이터 재현 경로 단절:** SEC 3요청의 자료별 해시 기록/ZIP 보관까지만 있었고 원본을 오프라인 분석기로 다시 돌리는 연결점과 Windows 한 명령 실행 경로가 없었다.

*순위는 작업 내역의 정성 분석이다. 단계별 실제 소요시간이나 API 횟수를 계측한 결과가 아니다.*

## 2. 발생 원인

| 항목 | 주된 원인 | 검수할 실제 근거 |
| --- | --- | --- |
| 다중 문서 갱신 | 오래된 매 작업 종료시 전 문서·100점 시간표 갱신 지침, GitHub 파일별 API 호출과 코드/문서 분리 | 개선 전 코드 52be8656037467252744b6d942ef8205290d1cfa 다음 별도 문서 398070567dc0c35f17c17dc8451b8d8c79b88e8d |
| 재조회 | 동일 CI 실행의 진행상태를 반복 확인하는 작업 순서 | 이전 대화·Actions 조회 흔적. 절감량 계측 없음 |
| 재현성 부족 | 기능을 저장, 검증, 분석으로 나눠 독립 구현; Windows 로컬 실행 직접 제어 불가 | 개선 전 sec_capture_bundle ZIP 무결성은 있었지만 sec_bundle_replay 모듈 없었음 |

## 3. 실제 개선 조치(적용과 미검증 분리)

**코드 반영 완료:** AGENTS.md 첫머리에 개발속도 상위 지시 기록, 오래된 매번 문서/100점/시간 갱신을 대체. 기능 구현·테스트·AGENTS·필요한 HANDOFF를 **단일 기능 커밋** 175e53027a45에 포함, 동일내용 6문서 반복 갱신을 이번 변경에서 제거. scripts/verify_local.py와 verify_local.ps1로 quick/full 테스트, 구문, SHA 및 OS 임시폴더 JSON 요약과 tests.log 출력을 구현. 별도 SEC 승인 없이 진행 가능한 **ZIP 오프라인 재분석**을 먼저 개발.

**아직 실제 개선 증거 부족:** 개발시간 절감·도구 호출 수 감소율은 미계측. Windows PowerShell 실행 증거 없음. GitHub CI는 기존 전체 unittest 실행이며 **단일 신규 검증 명령의 CI 직접 실행은 다음 개선 작업**이다. 새로운 규약이 미래의 모든 작업에서 지속 준수되는지는 아직 미확인.

## 4. 개선 이후 신규 실제 기능

- **proofinvest/sec_bundle_replay.py:** 사용자가 보존한 SEC 형식 ZIP을 읽기전용으로 열어 내부 3자료 SHA·수집시각 순서/UTC 날짜를 점검하고, 기존 Disclosure Lightning 인덱싱, 매출 연도별 검산, 원문 인용 바이트와 iXBRL 제한적 구조 분석을 다시 실행. 원문 HTML/식별 UA 미출력, 실패시 unavailable.
- **proofinvest/sec_capture_bundle.py:** 무결성 검증한 ZIP의 동일한 원본 3종을 한 번 읽어 재분석까지 연결할 수 있도록 내부 인터페이스 분리. 기존 공개 해시검증 API는 보존.
- **scripts/verify_local.py + verify_local.ps1:** Windows에서 핵심 또는 전체 검사 명령 한 번 실행하도록 코드 구현. 기존 DB/사용자 파일 삭제나 외부 HTTP/업로드 없음.
- **tests/test_sec_bundle_replay.py:** 성공 재분석, 변조, 잘못된 회계 기간/문구, 자칭 수집시간 오류, CLI 원본 비공개 등 **신규 테스트 6개를 작성했고 전체 CI에서 실행**.

이 기능들은 합성/모의 자료 기준으로만 검증했다. 실제 SEC 응답, 정확한 회계 정보, 권리, 실제 배포·DAKER 제출을 완료했다는 의미가 아니다.

## 5. 검증 증거

| 검증 기준 | 실제 SHA 및 파일 | 실행된 결과 |
| --- | --- | --- |
| 개선 전 | 코드 52be8656037467252744b6d942ef8205290d1cfa (sec_capture_bundle.py, sec_three_source.py, test_sec_capture_bundle.py); 문서 HEAD 398070567dc0c35f17c17dc8451b8d8c79b88e8d | [Actions #40549007869](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40549007869): **480/480 PASS** Python unittest, Linux, HTTP mocked |
| 개선 후 | 기능 SHA **175e53027a456afa61ee98c46d7d55d3f01a0d12**; AGENTS.md, HANDOFF.md, sec_capture_bundle.py, sec_bundle_replay.py, test_sec_bundle_replay.py, scripts/verify_local.py, verify_local.ps1 | [Actions #40551970322](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40551970322): **486/486 PASS**, Linux Python 3.11, 이전 대비 신규 6개 실제 실행 |
| Windows 직접 검증 | verify_local.ps1 제작 | **미실행/미검증.** 코드 존재는 Windows PASS 증거가 아님 |

CI의 녹색은 합성/모의 데이터에 대한 Python 검증이다. 실 SEC/브라우저/사용자 PC/제출 계정 검증과 구분한다.

## 6. 남은 병목

- **AI 직접 해결 가능:** quick/full 로컬 검증 엔진의 실제 CI 실행 연결(전체 테스트 중복 없이 한 번 실행); 소스 성능·안전성 개선; 합성 수치 반례·오프라인 ZIP 재현/로그 개선; 필요 없는 반복 문서/원격 조회 제거 유지.
- **사용자 Windows PC 또는 로컬 Codex 필요:** Windows PowerShell/Python 설치·인코딩/실제 파일 권한과 호환성, Windows 전용 배포 실행. 준비된 검증 명령 한 번이면 되도록 구성, 지금 사용자에게 실행을 요구하지 않음.
- **명시적 승인 필요:** 진짜 식별 연락처 UA로 SEC 3요청, 응답 원본 장기 로컬 저장/권리 검토, 비공개 최종 PDF 정확한 바이트·제목 승인, DAKER 업로드/최종 접수 영수증, 결제 및 고객데이터 처리.
- **외부 조건:** 최종 본선 진출 결과, 실제 Production URL/브라우저/외부 데이터 사용권 검증, 타 총괄의 DL feature/disclosure-lightning 브랜치 임의 병합 금지.

## 7. 즉시 다음 목표·MVP와 최종 잔여

1. **우선 구현(승인 불필요):** GitHub CI 전체 테스트 단계에서 새 scripts.verify_local --full을 **직접 실행하여** 작성만 된 로컬 검증기의 환경/SHA/실패 기록이 작동하는지 확인. 기존 전체 테스트와 중복 실행하지 않는다. 완료조건은 기능 SHA의 Actions SUCCESS, 테스트 횟수와 결과 확인.
2. **예선 최우선 외부 게이트:** **2026-11-12 10:00 KST** 10페이지/7섹션 PDF만 제출. 기존 private v3 검토 후보는 기존 pinned SHA와 다르므로 **소유자가 정확한 최종 PDF와 제출 프로젝트 제목 승인 → 승인된 파일만 프리플라이트 → DAKER 업로드/최종제출 별도 승인 및 접수증 확인** 순서. 사전 승인 없이 수정/재고정/접수하지 않는다.
3. **실제 작동 최종제품(본선 조건부):** SEC 실 HTTPS 3종 연결·거부 응답/약관/재무 원문 실제 검증, 추후 데이터 연구·Verification·Risk 통합, 실 Production 배포·브라우저 QA, 데모 URL/발표자료 및 공식 제출. 본선 진출 전 제품 전체 완료라고 주장하지 않는다.
4. **현재 수치의 정확한 한계:** 원래 60일 일정 장부(2026-10-25 스냅샷) **29 DONE / 3 BLOCKED / 28 NOT_STARTED**, 계획 기본 잔여 22시간 + 예비 82.25시간. 이는 최신 프로그램 최종완성 실측 시간/실제 기능 완성률이 아니므로 임의로 업데이트하지 않음.

**해총 판정용 후보:** KEEP = 단일커밋과 실제 ZIP 재분석/CI; FIX = Windows/새 검사 명령 직접검증·실 SEC 데이터; STOP = 여섯 문서 복제 갱신/중복 HEAD·CI 조회; ACCELERATE = 실제 SEC·최종 PDF 승인 후 실환경 연결과 제출. 최종 판단권은 해총에게 있음.
