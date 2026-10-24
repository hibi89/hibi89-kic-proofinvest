> **2026-10-24 새 채팅 한 줄 재개:** `[해커톤총괄 깃헙 레포지토리 확인하고 작업하셈]`  
> `KIC ProofInvest`의 현행 총괄 겸 직접 개발자 업무는 [lead/kic 브랜치의 CHAT_BOOTSTRAP.md](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/CHAT_BOOTSTRAP.md)에서 복원한다. **현재 작업은 `main`이 아닌 `lead/kic`의 `docs/roles/lead/LEAD_ACTIVE_WORK.md`가 기준**이다. 통합 상황실: [CHAT_BOOTSTRAP.md](https://github.com/hibi89/hackathon-command-center-2026/blob/main/CHAT_BOOTSTRAP.md). 별도 작업자 채팅/옛 디스패처는 이력만 보존.

# ProofInvest | KIC AI Agent Competition
> **3개 대회 전체 일정·충돌·제출 마감:** [docs/COMPETITION_SCHEDULE.md](docs/COMPETITION_SCHEDULE.md) (**2026-10-24 KST 공시**). 이 브랜치에서 작업을 시작할 때 마감과 내부 조기 제출 목표를 확인하며 공식 변경 시 대회 총괄에게 보고한다.



> **이 브랜치의 새 채팅 재개 경로:** docs/ROLE_COORDINATION.md → 통합 HANDOFF.md → STATUS.md → AGENTS.md → 소스. 최신 상태는 기능별 역할 폴더가 기준이며, 공통 루트 HANDOFF.md를 담당자 인수인계로 오해하지 말 것.

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

각 담당자가 새 채팅에서 시작할 때: **자기 브랜치의 `docs/roles/<role>/HANDOFF.md` → 같은 폴더 `STATUS.md`·`OPERATIONS.md` → 루트 `AGENTS.md`·`REQUIREMENTS.md` → 소스 코드 순으로 확인**. `main`의 루트 HANDOFF는 공통 통합 문서이며 개인 담당 인수인계가 아니다. 다른 브랜치를 자의로 수정하지 않습니다.

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

역할별 직접 링크: [AI 역할·브랜치 진입점](docs/ROLE_COORDINATION.md). 문서 기준 `docs/BRANCH_WORKFLOW.md`, `REQUIREMENTS.md`, `STATUS.md`, `HANDOFF.md`.
