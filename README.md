> **2026-10-24 UI 신규 시연:** 전체 `lead/kic` 저장소의 `python -m streamlit run streamlit_app.py`에서 **자료 유형**으로 기존 합성 결과 또는 삼성전자 과거 수동검산(16.20% 일치 / 30% conflict / 주장 없음 보류)을 선택할 수 있습니다. 원문·API 인증은 아니며 Risk는 근거 부족 시 보류합니다. 공개 합성 복원 ZIP은 의도대로 합성 모드만 표시합니다. [QA](docs/roles/lead/MANUAL_ISSUER_STREAMLIT_UI_QA_20261024.md). [196/196 CI](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40099102467).

> **기존 수동 공시 검산 한 명령 실행:** `python -m proofinvest.manual_case_demo` / 거짓 주장 확인 `python -m proofinvest.manual_case_demo --claim 30`. 삼성전자 2024/2023 연결매출 **+16.20%**를 과거 육안 확인된 PDF 메타데이터와 수동 기록으로 검산. 위험 계산 자료 없으면 Risk 보류. **새 PDF 원문 실시간 조회, OpenDART 인증, 실제 AI Agent, DAKER 제출 아님.** [실행/검수 근거](docs/roles/lead/MANUAL_ISSUER_DEMO_CLI_QA_20261024.md).

> **LIVE 2026-10-24 KST — 삼성전자 수동검산 출처연결 오프라인 CLI 완료:** `python -m proofinvest.manual_case_demo`로 기존 2024/2023 연결매출 16.20% 수동검산 근거를 Research→Verification→Risk에 연결, `--claim 30`은 conflict. 공식 발행사 게시일 2025-02-18 확인. Risk 부채·자본 미확보 → 계산 보류, DART 직접원문/실 API/Agent/Production/최종제출 모두 미검증. 코드 `a630451473eb`, GitHub Actions #40096891638 **189/189 PASS**, 신규7. 추가 독립 단위 100/100, 잔여 기본0h+예비0h, 실제 시간 미계측. 정본 60일 **29 DONE/3 BLOCKED/28 NOT_STARTED**, NEXT **2026-12-03**(미래), DAKER 10/25·11/09 각60% BLOCKED, DART 10/30 90% BLOCKED, 11/10 제출 NOT_STARTED. 개인 비공개 PDF/PPTX·Library6 파일 변경 없음. [QA](docs/roles/lead/MANUAL_ISSUER_DEMO_CLI_QA_20261024.md).

> **LIVE 2026-10-24 21:23 KST — P0 추가 안전 도구: 제출 전 동결 PDF 바이트 지문 검사 (SHA256+크기+헤더), 실제 파일·경로 업로드 없음. 코드 1be86030bccc5e6a5a71597788adae058e8c9c8a; 신규8 포함 GitHub Actions #40093484806 163/163 PASS. 비공개 후보 PDF 신규 CLI 직접 검사/DAKER 실제 업로드권한·접수·DART 공식 원문은 미검증. 60일 정본 29 DONE/3 BLOCKED/28 NOT_STARTED 유지, NEXT 12/03 공식 결과 미래 대기. 외부 차단: DAKER 10/25·11/09 각60%, DART10/30 90%; 11/10 제출 미착수. 이 부가 작업 100/100·잔여 기본0h+예비0h, 실제 시간 미계측.** [실행·복구 가이드](docs/KIC_FROZEN_PDF_SUBMISSION_PREFLIGHT_20261024.md). 원본 PDF/PPTX와 기존 정본 숫자 수정 없음.

> **[USER REQUEST / 대회 규정·순위·포트폴리오 공시 2026-10-24]** [KIC 공식 대회 정보·순위·인증서·포트폴리오 근거](docs/COMPETITION_RANKING_CERTIFICATES_PORTFOLIO_20261024.md) 필독. **공식 KIC 공고:** 본선 상위12팀·최종 6수상팀·12/03/2027-01-11 예정 발표. **사용자 제공 일반 DACON 동의사항:** 최종 순위표/인증서 조항은 있으나 KIC에서 참가자 전원 등수 공개·인증서 적용 여부는 **UNVERIFIED**, 실제 발표 후 원문/영수증만 포트폴리오 실적화. DAKER 개인/팀장 최종 제출권한 BLOCKED, 제출·진출·수상 없음. 이 공시는 비정기 정보기록이며 60일 진도를 추가 완료 처리하지 않음.

> **현행 진도·다음 작업 정본:** [60일 JSON](docs/roles/lead/MASTER_PROGRESS.json) → [자동 생성 전체 표](docs/roles/lead/MASTER_PROGRESS.md) → [현재 KIC 단일 작업](docs/roles/lead/LEAD_ACTIVE_WORK.md). README에는 완료 숫자·다음 날짜를 중복 기록하지 않습니다. 제출권한/실 API/Production 상태는 반드시 최신 인계와 실제 실행 증거로 확인합니다.

> **상시 강제 규칙 (2026-10-24 14:44:22 KST)**: [KIC_HANDOFF_CONTRACT.md](KIC_HANDOFF_CONTRACT.md) — **모든 작업 종료·부분중단마다 GitHub 최신화+복원 상태+일일 100점 진도+남은 시간+다음 작업 갱신·원격 확인이 끝나야만 종료 가능**. 사용자 시작 명령은 오직 `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`; 추가 인수인계 프롬프트 요청 금지. 이 문구보다 오래된 종료 규칙은 본 강제 규약으로 대체.

> **KIC 전용 새 채팅 입력 — 이 한 줄만 사용:** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`
>
> **새 채팅 즉시 수행:** [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md) → [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md) → `lead/kic` 최신 작업·실제 코드·테스트·CI 조회 후 **다음 미완료 작업 직접 실행**. 추가 인수인계 문장 불필요. **현재 개발 브랜치 `lead/kic`**이며 `main`과 과거 작업자 `feature/*`는 별개 이력이다.
>
> **일일 진척·남은 시간:** [DAILY_PROGRESS.md](docs/roles/lead/DAILY_PROGRESS.md). 완료/차단 요약과 차후 재시도: [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md). 처음 발견된 오래된 README/STATUS/HANDOFF 문구보다 최신 정본을 우선한다.

# ProofInvest | KIC AI Agent Competition

> **현재 운영:** KIC 총괄 한 채팅에서 설계·개발·검수하고 `lead/kic` 한 브랜치에서 다음 실제 과제를 수행합니다. 구 [WORKER_ROUTER.md](docs/roles/lead/WORKER_ROUTER.md)와 [NEXT_TASK.md](docs/roles/lead/NEXT_TASK.md)의 `KIC-R-001` 지시는 **폐기된 이력**으로, 새로운 작업을 발행하지 않습니다. [현행 직접 개발 규약](docs/roles/lead/LEAD_FULLSTACK_PROTOCOL.md)과 [단일 활성 작업](docs/roles/lead/LEAD_ACTIVE_WORK.md)을 우선합니다.

> **제품 구조:** Research → Verification → Risk는 별도 채팅 작업자가 아니라 하나의 ProofInvest 제품에 속한 모듈입니다. `main` 및 기존 `feature/*`는 변경 이력을 보존하며 `lead/kic` 작업과 자동 동기화되지 않습니다.
> **3개 대회 전체 일정·충돌·제출 마감:** [docs/COMPETITION_SCHEDULE.md](docs/COMPETITION_SCHEDULE.md) (**2026-10-24 KST 공시**). 이 브랜치에서 작업을 시작할 때 마감과 내부 조기 제출 목표를 확인하며 공식 변경 시 대회 총괄에게 보고한다.



> **이 브랜치의 새 채팅 재개 경로:** 최신 `lead/kic` HEAD → [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md) → [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md) → [LEAD_ACTIVE_WORK.md](docs/roles/lead/LEAD_ACTIVE_WORK.md) → [단일 JSON](docs/roles/lead/MASTER_PROGRESS.json) → 실제 소스·CI. 오래된 역할별 문서는 참고 기록일 뿐 현재 지시권이 없습니다.

기관 투자 검토에 필요한 산업·기업 리서치, 공시 수치 검증, 재무 위험 신호 탐지를 하나의 근거 중심 워크플로로 연결하는 **개발 중인 MVP**.

> 현 단계: 실제 서비스·AI Agent가 아니라 **합성 데이터 기반 오프라인 Python 스타터**입니다. 투자 권고가 아닙니다.

## 13개 AI 역할 중 KIC 4개 작업 브랜치

| 구분 | GitHub 브랜치 | 담당 |
|---|---|---|
| 통합 코드 기준 | `main` | 검증된 코드·CI·공통 계약 |
| KIC 총괄 | `lead/kic` | 최상위 KIC 감독, 통합 검수, 제출물, 인수인계 |
| 담당 1 | `feature/research` | 산업·기업 리서치 |
| 담당 2 | `feature/verification` | 공시·재무 수치 교차검증 |
| 담당 3 | `feature/risk` | 설명 가능한 위험 신호 탐지 |

위 feature 브랜치는 이력·원본 비교용으로 보존합니다. **새 작업은 `lead/kic`에서 총괄이 직접 수행하며**, 사용자 승인 없이 `main` 통합·브랜치 삭제·강제 push를 진행하지 않습니다.

## 로컬 Streamlit 합성 조회 화면 (선택 설치)

Python **3.11+** 환경에서만 설치·실행합니다. 기본 Python CLI(3.10+)에는 Streamlit 설치가 필요하지 않습니다. 현재 앱은 `fixtures/synthetic_annual.json`의 직접 계산 및 **명시적으로 저장된 합성 스냅샷 재조회** 중에서 선택합니다. 로그인, 파일 업로드, API 호출, 계정/제출 버튼이 없습니다.

```bash
python -m pip install -r requirements-ui.txt
python -m streamlit run streamlit_app.py
```

화면에는 CFS/OFS별 가상 재무 행, 합성 산술 검사 상태, 시연용 부채/자본 탐색 신호, **실제 원문 미인증** 경고를 표시합니다. 임계값 200%는 공인 투자 기준이 아닙니다. 실제 기업 데이터 처리, OpenDART 호출, 웹 배포 또는 DAKER 제출이 아니며 `streamlit.testing.v1.AppTest` 헤드리스 검증은 브라우저 육안 테스트와 다릅니다.

## 합성 계산 결과 저장·재조회 (선택, 완전 로컬)

Streamlit UI의 ‘저장된 결과 재조회’ 모드와 연결하며 실 OpenDART 호출은 하지 않습니다. **오프라인 합성 fixture 계산 결과만** 사용자 홈의 `.proofinvest-synthetic-cache`에 명시적 명령으로 저장합니다. `--read`는 **재계산하지 않고** 저장 기록을 검증 후 재조회합니다.

```bash
python -m proofinvest.snapshot_store --save
python -m proofinvest.snapshot_store --read
```

첫 `--save`는 계산 후 파일을 최초 1회만 생성하고, 반복 `--save`는 기존 결과를 검증하여 그대로 재사용합니다. 무결성 체크섬 또는 bundled fixture가 바뀌면 **임의 덮어쓰기·자동 재계산 없이 오류로 중지**합니다. 안전하게 재생성이 필요하면 별도 백업 후 해당 로컬 합성 캐시 파일을 사용자가 삭제하고 `--save`를 명시적으로 재실행합니다. SHA-256은 파일 손상 검사이지 재무 사실/출처 진위 인증이 아닙니다. 저장 결과는 실제 기업/개인정보/키를 수집하지 않습니다. UI ‘저장된 결과 재조회 (재계산 없음)’를 선택하면 저장된 결과와 로컬 합성 출처 경로·fixture SHA-256을 표시합니다. 저장 파일이 없거나 손상되면 자동 재계산하지 않고 중단합니다. SHA-256은 공시 원문 진위 인증이 아닙니다.

## 오프라인 검증

```bash
python -m unittest discover -s tests -v
python -m proofinvest --claim-revenue-growth-pct 20
```

Python 3.10+; 추가 라이브러리 없이 실행. 결과 `SYNTHETIC_FIXTURE`는 실제 공시가 아닙니다.

## 보안·대회

- 현재 저장소는 **Public**. 토큰, `.env`, 개인정보, 비공개 자료 및 제출 전 비공개 기획서 원본은 게시하지 않습니다.
- 실제 OpenDART API 요청은 API 조건·쿼터·비용 확인 및 사용자 승인 후 진행합니다.
- 2026-11-12 10:00 KST 예선: 공식 양식에 맞는 10페이지 이내 PDF. 본선 선발 후 2026-12-22 10:00 KST MVP 제출.
- Source: https://daker.ai/public/hackathons/kic-ai-agent-competition

문서 기준 `docs/BRANCH_WORKFLOW.md`, `REQUIREMENTS.md`, `STATUS.md`, `HANDOFF.md`.
