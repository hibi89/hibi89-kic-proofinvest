> **KIC 전용 새 채팅 입력 — 이 한 줄만 사용:** `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`
>
> **새 채팅 즉시 수행:** [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md) → [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md) → `lead/kic` 최신 작업·실제 코드·테스트·CI 조회 후 **다음 미완료 작업 직접 실행**. 추가 인수인계 문장 불필요. **현재 개발 브랜치 `lead/kic`**이며 `main`과 과거 작업자 `feature/*`는 별개 이력이다.
>
> **일일 진척·남은 시간:** [DAILY_PROGRESS.md](docs/roles/lead/DAILY_PROGRESS.md). 완료/차단 요약과 차후 재시도: [KIC_RESUME_STATE.md](KIC_RESUME_STATE.md). 처음 발견된 오래된 README/STATUS/HANDOFF 문구보다 최신 정본을 우선한다.

# ProofInvest | KIC AI Agent Competition

> **한 개의 범용 KIC 개발자 채팅으로 순차 작업:** [WORKER_ROUTER.md](docs/roles/lead/WORKER_ROUTER.md) → [유일한 NEXT_TASK.md](docs/roles/lead/NEXT_TASK.md) → [작업자 채팅 시작 프롬프트](docs/roles/lead/WORKER_CHAT_START_PROMPT.md). **현재 READY KIC-R-001**, `feature/research` 한 곳만. KIC 총괄 검수 전 다음 작업 자동 실행 금지.

> **확정 협업정책:** Research·Verification·Risk는 브랜치/역할만 3개이며 **동시 개발하지 않는다**. 기능 작업자는 1명만 활성, Research → Verification → Risk → KIC 총괄 통합. [KIC 확정 일정표](docs/roles/lead/KIC_MASTER_SCHEDULE_20261024.md) 및 [총괄 운영 규칙](docs/roles/lead/OPERATIONS.md) 준수.
> **3개 대회 전체 일정·충돌·제출 마감:** [docs/COMPETITION_SCHEDULE.md](docs/COMPETITION_SCHEDULE.md) (**2026-10-24 KST 공시**). 이 브랜치에서 작업을 시작할 때 마감과 내부 조기 제출 목표를 확인하며 공식 변경 시 대회 총괄에게 보고한다.



> **이 브랜치의 새 채팅 재개 경로:** docs/roles/lead/HANDOFF.md → STATUS.md → OPERATIONS.md → AGENTS.md → REQUIREMENTS.md → 소스. 최신 상태는 기능별 역할 폴더가 기준이며, 공통 루트 HANDOFF.md를 담당자 인수인계로 오해하지 말 것.

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

각 담당자가 새 채팅에서 시작할 때: **해당 브랜치의 `HANDOFF.md → STATUS.md → AGENTS.md → REQUIREMENTS.md → 소스 코드` 순으로 확인**. 다른 브랜치를 자의로 수정하지 않습니다.

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
