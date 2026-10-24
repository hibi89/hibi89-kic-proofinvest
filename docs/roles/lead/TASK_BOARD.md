> **SUPERSEDED / ARCHIVED — 2026-10-24 KST:** This file is retained for historical task scope and worker-chat handoff evidence. It NO LONGER authorizes a separate worker, READY dispatch or feature-branch write. Only the KIC lead in the same chat continues work on `lead/kic`, following `LEAD_ACTIVE_WORK.md` and `LEAD_FULLSTACK_PROTOCOL.md`. Do not start a worker chat or repeat KIC-R-001.

# KIC ProofInvest — 단일 작업자 작업 큐·이력

> **진짜 실행 지시 원본**: [NEXT_TASK.md](NEXT_TASK.md). 이 파일은 **진행 순서/검수 이력**이며 작업자가 스스로 다음 행을 실행할 권한이 없다.
> **동시 실행**: KIC 작업자 채팅 **단 하나**. 다른 해커톤과는 독립 운영.
> **작성일**: 2026-10-24 12:35:40 KST · 상태는 GitHub 원격 확인 시점을 따른다. 자동 업데이트·백그라운드 실행 없음.

| 순서 | Task ID | 담당 역할 | 대상 브랜치 | 큐 상태 | 현재 의미 | 총괄 게이트 |
|---|---|---|---|---|---|---|
| 1 | **KIC-R-001** | Research | `feature/research` | **READY** | 단일 범용 작업자 채팅이 시작하면 이 작업만 수행 | 오프라인 근거 정규화+테스트+인수인계 검수 |
| 2 | KIC-V-001 *(예정 식별자)* | Verification | `feature/verification` | **WAITING / NOT ISSUED** | 지금 실행 금지, 세부 지시 미발행 | Research의 완료·보류 수용 후 총괄 작성 |
| 3 | KIC-K-001 *(예정 식별자)* | Risk | `feature/risk` | **WAITING / NOT ISSUED** | 지금 실행 금지, 세부 지시 미발행 | Verification의 완료·보류 수용 후 총괄 작성 |
| 4 | KIC-L-001 *(예정 식별자)* | Lead Integration | `lead/kic`/검수 후 `main` | **WAITING / NOT ISSUED** | 작업자 임의 통합 금지 | 3개 기능의 테스트·PR/CI, 사용자 승인 검토 |

## 작업자가 기다리거나 중단해야 하는 경우

- `NEXT_TASK`가 `READY`가 아니거나 해당 task와 브랜치가 다름.
- 이전 동일 `task_id`의 완료 보고가 feature 브랜치에 이미 존재함.
- 다른 사용자/AI 채팅에서 `[IN_PROGRESS]` 수신 보고가 있고, 현재 작업자 자신이 그 실행 흐름을 확실히 이어받는 것이 아님.
- 사용자 승인이 필요한 API·공통 스키마·유료 지출/권한 변경이 선행 조건인데 해당 승인이 없음.
- Feature 원격 HEAD가 작업자의 예상과 다른 경우, 재조회 후 변경 사항에 맞춰 재조정하고 불명확하면 총괄 검수 요청.

## 총괄이 후속 작업을 발행할 때 갱신할 것

1. 담당 메시지 3개와 SHA·CI 확인 후 Review 결과를 [MESSAGE_REVIEW.md](MESSAGE_REVIEW.md)에 기록.
2. 완료 기준 충족 시 현재 Task의 상태를 DONE으로 본 이력에 기록, 미흡한 경우 BLOCKED/PAUSED와 사유.
3. **하나의 다음 Task 상세 파일** `tasks/<새ID>.md`를 작성하고 [NEXT_TASK.md](NEXT_TASK.md)를 정확히 하나의 새 READY로 교체.
4. `STATUS.md`, `HANDOFF.md`, `TO_HACKATHON_LEAD.md`, 필요시 공식 일정과 동기화하여 커밋.
5. 사용자에게 새 Task 링크/브랜치/완료 기준만 전달. 사용자는 **동일 범용 작업자 채팅**에서 "GitHub 다음 작업 실행"이라고 하면 됨.

**주의:** 본 TODO/큐 문서는 실제 기능 코드 구현 증거가 아니다. READY와 DONE을 혼동하지 말 것.
