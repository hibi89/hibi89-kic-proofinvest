# KIC KUODRA — 새 채팅 인수인계 P285 (2026-11-09 KST)

## 1. 확정 목표·요구사항·기술
글로벌 미국 상장기업의 SEC 공시·원문·재무 숫자·시장 및 비교기업 근거를 검산하고 결론이 불충분하면 Guard HOLD/REJECT와 감사 가능한 근거 기록을 내는 KUODRA. KIC 투자 리서치의 참고·검토 자료용 제안이며 실제 KIC 시스템과 연결한 것은 아니다. Python 3.11, Streamlit, SQLite, Decimal, read-only local AI Qwen opt-in, Playwright, GitHub Actions.

## 2. 최근 완료 결과·결정 근거
- 2026-11-09: V19 한국어 중심 10페이지 KIC 기획서 전면 개편: 기존 V18 영어 장식·정보 과밀·KIC 실제 활용 설명 부족 개선. KIC 리서치/기업 비교/위험 검토의 사용자 흐름, 재사용 OSS와 독자 원본검증·A/B/C·Guard 구분, 사용자가 받는 JSON/HTML·보고서·감사 이력, 현재 오프라인 검증과 미완료 본선 계획 구분.
- V15 Library 원본, 기존 V18 유지. 새 V19 완전 편집형 PPTX 10쪽과 PDF 10쪽, 전체 미리보기 PNG, QA 기록을 한 ZIP으로 묶었다.
- 제품 코드는 P281 이후 미수정: 업로드 4종 SEC 형식 원본의 신원/재무/iXBRL/Guard 7단계 재계산 및 독립 리플레이가 끝나기 전 선택형 로컬 Qwen을 호출하지 않는다. 기존 정상 모드 보존.

## 3. 정확한 테스트·근거 및 범위
- 기능 SHA: 1f89ef7671f158307fbca35e78c621de54264fa1. GitHub Actions https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/42521769506 : 필수 6/6 SUCCESS; Ubuntu unittest 2188/2188 PASS; Windows 2188 실행, 2187 PASS/1 SKIP/0 FAIL; syntax 532 PASS; Chromium 실제 오프라인 클릭, Windows HTTP/SQLite, 격리 컨테이너 PASS.
- 4개 선택형 실제 로컬 모델 CI는 해당 SHA에서 SKIPPED. 실제 Qwen 품질/실 SEC 원본·시장 데이터/Production 검증과 혼동 금지.
- V19 PPTX: 104604 bytes, SHA256 1b30f78e7a8c9f026ec5f9f340a203744b154bb9e0ba103b82857723ebeb8b12.
- V19 PDF: 299185 bytes, SHA256 596d476f145e38aae85ccd241478f15a1df0401f37ef92fd39560fe8598c64ff.
- V19 ZIP: 1085948 bytes, SHA256 4848e09dc30be7edec8758c74f85d85e19ca229d094afdc1db1bdfb2c2237443. ZIP integrity checked; PPTX/PDF SHA checked, 10-page landscape PDF, seven required official sections, four source links, 10-page rendering/visual check and PDF text bounds PASS.

## 4. 상태/중단 지점
- 제품 공식 완성률 **76/100, RELEASE HOLD**. 오프라인 7단계·Guard 및 제출용 문서 시안은 확인됨.
- 제출물: V19는 비공개 검토용이며 DAKER 공식 제출 **아직 안 함**; 사용자 최종 검토/제출 승인 및 실제 팀장 계정 조작 필요.
- KIC 예선 PDF 10쪽 이내 마감 **2026-11-12 10:00 KST**. ELO 기간 **2026-11-12 12:00 ~ 2026-11-19 10:00 KST**; 별도 참여 요건 확인.

## 5. 차단 근거·시도 및 재시도 금지
- SEC 공식 NVDA FY2026 10-K INDEX를 통해 CIK 0001045810, accession 0001045810-26-000021, filed 2026-02-25, fiscal end 2026-01-25 확인. 하지만 4종 진짜 원본(ticker_map/submissions/companyfacts/original_10k)은 취득/독립 인증하지 못함.
- 기존 SEC 403/429 STOP 및 허용된 1회 공식 submissions 다운로드 실패를 보존. 동일 GET 무한 재시도, 프록시·우회·무허가 외부 원본취득 금지.
- 실제 Nasdaq100 및 미국 주가 AI/전시/대회 이용권 미확보. 개인용 FRED/Massive 데이터를 본선 라이선스로 승격하지 말 것. 실원본 A/B/C, 안전한 Production 및 공개 서비스 검증 미완료.

## 6. 저장소·브랜치·SHA·경로
- Repo hibi89/hibi89-kic-proofinvest, branch lead/kic; 문서 P284 확인 SHA 83da7ac383c0701beb7f2bd2e4284928be9d7f97; 기능 SHA 1f89ef76. 새 채팅에서 최신 HEAD 다시 확인 후 HANDOFF.md → STATUS.md → AGENTS.md → REQUIREMENTS.md → 실제 소스 순으로 읽기.
- 검증 문서 docs/KIC_PRELIM_V19_REDESIGN_QA_20261109.md; 이전 V18 docs/KIC_PRELIM_V18_CONTENT_QA_20261109.md.

## 7. 배포·실행환경
- Windows Python 3.11.9 사용자 환경; Ubuntu/Windows Actions 오프라인 검증. Streamlit은 로컬용. Vercel Production 프로젝트/URL/기능 검증 없음, Production SHA 매핑 미적용; 제출일 전에 무단 공개배포하지 말 것.

## 8. 원본·Library 백업·보안
- V19 ZIP의 **실제 Library 백업 확인됨**: `/KIC/KUODRA_V19_REDESIGN_REVIEW_PACK_20261109.zip` (size 1085948 B, library_file_id libfile_d73fa19a10208191a44a66be8462ac22). 포함: KUODRA_KIC_V19_REDESIGN_PRIVATE_REVIEW.pdf / .pptx, KUODRA_V19_QA_AND_SCOPE.md, KUODRA_V19_10PAGE_PREVIEW.png. 이전 채팅 임시 sandbox 링크만 의존하지 말고 이 Library 파일을 찾고 필요하면 materialize. Library 파일은 GitHub에 업로드하지 않음.
- Library의 V15 편집 원본은 보존. 토큰, .env, 사용자 원본 SEC/NDX, 비공개 PDF/PPTX를 공개 GitHub에 올리거나 허가 없이 배포하지 말 것. 추가 보안/권한/결제 변경 없음.

## 9. 새 채팅 다음 작업 우선순위·승인
1) 우선 V19 시안 시각적·문구 최종 검토. 사용자 의견이 있으면 수정 후 다시 10쪽·링크·렌더 QA, 같은 V15/V18 원본 보존. 장식성 수정이나 중복 CI는 불필요.
2) 날짜 때문에 예선 PDF DAKER 최종 업로드가 최우선 외부 작업. 이용자/팀장 계정에서 PDF 업로드 → '제출 완료' → 상태 '최종'의 실제 증거 확인. 문서 제작만으로 제출 성공 주장 금지. Owner 최종 공개/제출 승인 구분. 가능한 사용자 작업은 한 번에 모으기.
3) 본선 제품 100%는 진짜 SEC 4원본과 발행처 독립 검증, 적법한 주가/진짜 NDX 데이터 권리, 실데이터 A/B/C·Guard·보고서·Production browser/API 검증 순서. 허가 없는 API GET·데이터 재배포·금전 지출 금지. 이미 통과한 코드검증 무의미한 반복 금지.

## 10. 시각·확인 범위·기준
- 2026-11-09 KST 채팅 전환 전 확인: GitHub 83da7ac3 P284 HEAD, V19 세 파일의 로컬 byte/SHA, ZIP CRC, Library 업로드 결과 및 `/KIC` 목록에서 1085948 B 확인. 제출/Production/실원본은 별도 미검증.
- 이 문서를 추가한 docs-only SHA는 커밋 후 확인하며 [skip ci]; P281 기능 CI와 구분할 것.

## 새 채팅 시작 문구
"KIC 총괄 복귀. hibi89/hibi89-kic-proofinvest lead/kic 최신 HANDOFF.md → STATUS.md → AGENTS.md → REQUIREMENTS.md 순서로 읽어. P285 새 채팅 인수인계와 Library /KIC/KUODRA_V19_REDESIGN_REVIEW_PACK_20261109.zip 기준으로 V19 한국어 중심 10페이지 기획서 최종 검토/수정부터 이어가자. 제품 76%, 기능 SHA 1f89ef76, CI 6/6. DAKER 미제출·마감 11/12 10:00 KST. 사용자 개입 최소화하고 ㄱ이면 다음 필수 작업 계속해."
