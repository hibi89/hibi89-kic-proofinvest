> **SUPERSEDED / ARCHIVED — 2026-10-24 KST:** This file is retained for historical task scope and worker-chat handoff evidence. It NO LONGER authorizes a separate worker, READY dispatch or feature-branch write. Only the KIC lead in the same chat continues work on `lead/kic`, following `LEAD_ACTIVE_WORK.md` and `LEAD_FULLSTACK_PROTOCOL.md`. Do not start a worker chat or repeat KIC-R-001.

# KIC ProofInvest — 단일 작업자 채팅 실행 프로토콜 (필독)

> **최종 사용자 결정**: **KIC 총괄 채팅 1개 + KIC 범용 작업자 채팅 1개**만 필요. Research/Verification/Risk는 **담당 기능과 GitHub 브랜치**일 뿐 사용자에게 3개의 작업자 채팅방을 요구하지 않는다.
> **총괄 전용 브랜치**: `lead/kic` · **기능 작업 브랜치**: `feature/research`, `feature/verification`, `feature/risk`
> **운영 시점**: 2026-10-24 12:35:40 KST; **현행 지시권한**: 오직 [NEXT_TASK.md](NEXT_TASK.md)의 단일 활성 작업 + 해당 [tasks/<ID>.md](tasks/KIC-R-001.md) 명세
> **현실적 한계**: GitHub는 메시지 보관소이며 **다른 AI 채팅을 자동 실행/전환/통지하지 않는다**. 사용자 한 번의 "KIC 작업자야, GitHub 확인하고 다음 지시 실행해"가 실행 트리거다.

## 1. 한 장짜리 경로 안내

```text
사용자 ──> KIC 총괄(이 채팅)
              └─ lead/kic/NEXT_TASK.md에 단 한 건의 READY
                   ↓ 사용자가 범용 작업자 채팅에서 "진행" 요청
         KIC 범용 작업자 채팅(단 하나, 역할 고정 금지)
                   ├─ 먼저 lead/kic/NEXT_TASK.md 확인
                   ├─ 해당 task ID 원문·준수조건 확인
                   ├─ 정확히 지정된 feature 브랜치로 이동
                   ├─ 소스/테스트/커밋 + 담당 STATUS/HANDOFF
                   └─ 담당 브랜치 TO_KIC_LEAD.md에 결과 기록
                                 ↓
                   사용자 ──> KIC 총괄 "검수해"
                                 ↓
         총괄: 모든 메시지함 재검토/CI/코드 검수 → 
               NEXT_TASK.md의 기존 작업 CLOSE 또는 BLOCKED 판정
               다음 한 건만 READY로 교체
```

- 범용 작업자 채팅에서 "나는 항상 Research 담당"처럼 영구적으로 역할을 고정하지 않는다. 현재 작업 ID가 가리키는 담당/브랜치를 **매 작업 시작마다 새로 판독**한다.
- 같은 채팅방에서 `feature/research` 작업이 종료되고 검수·승인 후, **총괄이 발행한 새 작업**이 `feature/verification`을 지정하면 같은 작업자가 해당 브랜치로 전환한다. Risk도 동일.
- **ACTIVE 작업은 한 건**, 기능 개발에 실제로 참여하는 채팅도 **KIC에서 하나**. 타 기능 브랜치는 WAITING. 다른 해커톤은 독립적인 총괄/작업자 채팅에서 동시에 진행 가능.

## 2. 단일 작업자 채팅의 매 호출 첫 행동 (기계적으로 수행)

1. GitHub 원격 `hibi89/hibi89-kic-proofinvest`의 **`lead/kic` 브랜치 HEAD**를 조회한다(기억 속 SHA 사용 금지).
2. [NEXT_TASK.md](NEXT_TASK.md)와 그곳에 적힌 **정확한 task markdown 경로**를 **`lead/kic` ref 지정**하여 직접 읽는다.
3. `NEXT_TASK.md`가 `READY`이고 `task_id`와 지정 브랜치/대상 경로가 유효한지 확인한다. `AWAITING_REVIEW`, `BLOCKED`, `DONE`, `PAUSED`, `NONE`이면 **새 개발을 시작하지 않고** 현재 상태만 보고한다.
4. 해당 task의 `required_approvals`를 확인한다. 승인되지 않은 공통 스키마 변경·라이브 API 호출·돈/권한/보안 변경은 수행 금지. 작업이 이 승인에 의존한다면 **해당 구간만 보류**하고 허용되는 오프라인 부분만 수행한다.
5. 지정 feature 브랜치의 **원격 HEAD**와 전용 `docs/roles/<role>/HANDOFF.md`, `STATUS.md`, `OPERATIONS.md`, `TO_KIC_LEAD.md`, 루트 `AGENTS.md`, `REQUIREMENTS.md`, 실제 코드를 확인한다.
6. 이미 같은 `task_id`의 `[IN_PROGRESS]`, `[DONE]`, `[BLOCKED]` 보고가 feature 브랜치에 존재하면 무작정 다시 시작하거나 중복 커밋하지 않는다. **동일 채팅의 자기 작업을 계속하는 경우에만** 해당 기록과 SHA에 맞춰 재개. 불명확하면 총괄 검수를 요청한다.
7. 시작 시 feature 브랜치의 `docs/roles/<role>/TO_KIC_LEAD.md`에 **`[IN_PROGRESS]` 수신·착수 메시지(task ID, branch, 원격 SHA, 범위)**를 먼저 커밋하여 수신 영수증을 남긴다. 이 시점은 실제 사용자 요청으로 작업자가 동작할 때만 발생한다.
8. 맡은 변경만 안전하게 구현·테스트·feature 브랜치에 커밋한다. `main`, `lead/kic`, 다른 feature 브랜치를 수정하지 않는다. 다른 브랜치 코드는 참조만 가능. 불필요한 force push·재초기화·비밀값 공개 금지.
9. 종료 시 해당 담당의 `STATUS.md`, `HANDOFF.md`, `TO_KIC_LEAD.md`에 **`[DONE]` 또는 `[BLOCKED]`** 및 task ID, 코드 SHA, 테스트 수/실행법/CI 링크(없으면 미확인), 완료/미완료, 다음 승인 사항을 적고 커밋한다.
10. 사용자에게 **완료 상태·변경 브랜치·commit SHA·검증 증거·총괄이 해야 할 검수**를 보고하고 멈춘다. 다른 담당 브랜치에 자동으로 넘어가지 않는다.

## 3. 총괄의 지시 발행·완료 판정

1. 매 지시/변경 전 **세 feature 브랜치 HEAD와 `TO_KIC_LEAD.md`를 전수 읽고**, `MESSAGE_REVIEW.md`에 시각/판단/차단 여부를 기록한다.
2. `NEXT_TASK.md`를 **한 건의 명확한 작업 지시로** 갱신: ID, 대상 브랜치/역할, 상세 명세 경로, READY 여부, 선행조건, 납품물, 완료 기준, 금지사항, 예상 내부 마감.
3. 현재 다른 작업이 `READY`거나 기능 브랜치에 `IN_PROGRESS` 보고가 있다면 **두 번째 READY 발행 금지**. 교체 시 기존 과제를 `DONE` 또는 `PAUSED/BLOCKED`로 처리하고 검수 근거/이관 사유 기록.
4. 담당 `[DONE]` 보고는 **자동 승인 아님**. 실제 feature 코드/SHA/테스트 및 CI를 확인한 뒤에만 기존 작업을 `DONE` 처리하고 다음 과제 발행. 시험하지 못한 부분은 `미검증`으로 남긴다.
5. `TASK_BOARD.md`에 완료/보류/다음 과제 로그를 유지. `STATUS`·`HANDOFF`·`TO_HACKATHON_LEAD`와 가능한 한 같은 커밋에서 동기화.
6. GitHub 문서가 충돌하거나 파일 접근에 실패하면 **fail closed**: 새 기능 구현 지시를 내리지 않고 지시문을 복구한다.
7. 총괄이 자동으로 다른 채팅을 호출하거나 타 브랜치에 쓰지 않는다. 범용 작업자는 사용자에게 요청받았을 때만 해당 브랜치에서 실행한다.

## 4. 상태와 우선순위 규약

- `READY` = 총괄이 발행한 **유일한 실행 가능 지시**. 사용자 호출 전은 착수 아님.
- `IN_PROGRESS` = 작업자의 **feature 브랜치에 남긴 시작 영수증**. 총괄 작업 문서는 그 사이 자동 변경되지 않음.
- `AWAITING_REVIEW` = 작업자가 완료·차단을 보고하여 총괄 검수가 필요한 상태. 총괄이 확인한 뒤 지시서에 반영.
- `DONE` = 총괄이 근거로 승인한 작업. 다음 작업 열기 전에 닫힘.
- `BLOCKED` / `PAUSED` = 권한/기술/결정 차단 또는 일시 중지. 이유·최종 안전 상태가 있어야 다음 작업 이관 가능.
- **우선순위**: `NEXT_TASK.md` (실행 지정) → 해당 task 파일 (구체 스코프) → feature 브랜치 상태/소스 (실제 완료 근거) → `KIC_MASTER_SCHEDULE_20261024.md` (목표 날짜) → 과거 제안 이력.
- 날짜가 지났어도 작업자는 스스로 차례를 바꾸지 않는다. 반드시 **총괄 지시가 지정한 branch**에서만 수행한다.

## 5. 사용자가 보낼 메시지

**범용 작업자 채팅방 처음 시작할 때** [WORKER_CHAT_START_PROMPT.md](WORKER_CHAT_START_PROMPT.md)를 전송한다.

그다음부터는 작업자 채팅에 **"KIC GitHub 최신 NEXT_TASK 확인하고 지시된 작업 진행해. 끝나면 네 브랜치에 보고하고 멈춰."**라고 말하면 된다.

작업자가 결과를 보고하면 KIC 총괄 채팅에 **"KIC 작업자 보고 검수하고 다음 작업 등록해."**라고 말한다.

**현재 첫 실행 과제**는 [NEXT_TASK.md](NEXT_TASK.md)의 `KIC-R-001`이다. Research 단독으로 시작하며, 다른 두 역할은 대기한다.
