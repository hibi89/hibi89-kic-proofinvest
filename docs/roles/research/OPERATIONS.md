# 산업·기업 리서치 담당 — 작업지침 (feature/research)

# ProofInvest 작업 규칙 — 각 기능 브랜치별 독립 인수인계

- 저장소: https://github.com/hibi89/hibi89-kic-proofinvest (Public)
- 참가자: 자이언츠파크 1인. 3기능 담당과 KIC 총괄은 **AI 채팅 역할**이지 실제 대회 팀원 4인이 아니다.
- 프로젝트: 기관 투자 검토 지원 **ProofInvest**. ①산업 리서치 → ②공시·재무수치 검증 → ③위험 신호 탐지 → 출처·불확실성을 기재한 보고서.
- 목표: KIC 예선 상위 12팀 본선 진출. 기획서 PDF(공식 양식, 최대 10페이지) 2026-11-12 10:00 KST 마감. 본선은 선발 시 2026-12-22 10:00 KST 데모 URL·코드·발표 PDF.
- 브랜치: `main`은 통합 기준, `lead/kic`는 KIC 총괄, `feature/research`, `feature/verification`, `feature/risk`는 독립 기능.
- 새 채팅 시작: **해당 원격 브랜치 HEAD SHA부터 확인**하고, 그 브랜치의 **`docs/roles/<담당>/HANDOFF.md → STATUS.md → OPERATIONS.md → AGENTS.md → REQUIREMENTS.md → 실제 코드`** 순으로 읽는다. 역할별 `TO_KIC_LEAD.md`의 지난 요청 및 회신 여부도 확인.
- 작업자 책임: 코드 구현 → 테스트 → 본인 브랜치 커밋 → **해당 브랜치 역할별 STATUS/HANDOFF 최신화** → KIC 총괄에게 보고. 문서만 바꾸고 작동 성공을 주장하지 않는다.
- 메시지 전달: 각 기능 브랜치 `docs/roles/<담당>/TO_KIC_LEAD.md`에 요청·질문·결정 필요 사항을 적어 **해당 브랜치에 커밋**. 다른 채팅으로 자동 전달되는 것은 아니며 KIC 총괄이 매 지시 전에 3개 브랜치 메시지를 직접 조회한다.
- 공통 데이터·API 계약 변경, 안전한 라이브 호출, 배포, 공개/삭제, 비용 발생은 사전 승인 필요. Public 저장소에 개인키·토큰·`.env`·민감정보 금지.
- 오프라인 테스트 `python -m unittest discover -s tests -v` ; `python -m proofinvest --claim-revenue-growth-pct 20`. 합성 입력 `SYNTHETIC_FIXTURE`는 실제 기업 데이터가 아니다.
- CI 통과는 코드 수준 확인일 뿐 실제 API·배포 성공은 별도로 검증.


## 이 브랜치의 고유 책임
기관 투자담당자가 입력한 상장기업과 해당 산업에 대해 합법적으로 이용 가능한 자료를 조회하고, 경쟁사·산업 변동·자료의 기준일을 정규화한다.

**내가 구현할 범위:** 기업·산업 대상 식별, 출처 검색·시점 관리, 산업 및 Peer Group 정보의 근거 목록, 요약 후보 생성. 투자 추천, 금융 검산, 위험 신호 판단은 담당 밖.

**예상 작업 경로:** proofinvest/research.py, tests/test_research.py 등 신규 파일로 시작; 기존 proofinvest/engine.py는 공통 데이터 계약에 동의 없이 수정하지 말 것.

## 제안 데이터 입출력 계약 (확정 전, 총괄 승인 필수)
- 입력: `target_name, target_id(optional), country, industry(optional), as_of`
- 출력: `research_status(success|partial|unavailable), findings[{claim,period,source_ids,confidence}], sources[{id,title,url,published_at,accessed_at,license}], warnings[]`
- 다른 기능이 사용할 계약을 임의 변경하지 말고 `TO_KIC_LEAD.md`에 제안한다.

## 현재 구현·완료 기준
- 현재 main에는 Python 합성 검증 스타터와 테스트가 있으며 **각 기능 완제품과 실 API 테스트는 미완료**다.
- 이 브랜치의 완료 기준: 오프라인 fixture 기반 검색·출처 정규화·무근거 거절 테스트를 재현하고, 출처 없는 수치가 보고서로 전달되지 않아야 한다.
- 알려진 위험: 뉴스 저작권, 산업 통계 접근 권한, 자료 기준일 혼용, 출처 오류, 라이브 API 요금·쿼터.

## 지금부터 작업
1. main 기준 테스트 확인 2. 이용 가능한 공개 데이터 후보와 라이선스·쿼터 조사(조회는 읽기 전용) 3. 위 계약에 맞는 최소 구조 제안 4. 합성 데이터로 단위 테스트 작성 5. KIC 총괄에 메시지 남기고 승인 후 구현·PR 준비.

## 종료마다 절대 누락 금지
1. 수정·테스트·검증 근거를 해당 브랜치에 남긴다.
2. **`docs/roles/research/STATUS.md` 및 `HANDOFF.md` 최신화**(코드 변경이 없더라도 의미 있는 결정이 생겼을 때).
3. 결정 요청/차단/총괄 참고 사항이 있으면 **`docs/roles/research/TO_KIC_LEAD.md`에 날짜·브랜치 HEAD·메시지 기록 후 커밋**.
4. PR/커밋 SHA, 통과/실패/미검증, 다음 작업을 최종 보고한다.
