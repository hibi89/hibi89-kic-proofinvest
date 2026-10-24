> **영구 종료 게이트:** [KIC_HANDOFF_CONTRACT.md](../../../KIC_HANDOFF_CONTRACT.md). 구현·CI가 끝나도 **모든 작업 종료/부분중단 때마다** 루트 KIC_RESUME_STATE, LEAD_ACTIVE_WORK, DAILY_PROGRESS, STATUS/HANDOFF/TO_HACKATHON_LEAD를 업데이트·커밋하고 원격 확인할 때까지 DONE 선언 금지.

# KIC — Lead-as-Builder execution protocol (CURRENT)
Effective 2026-10-24 KST. Supersedes worker-chat dispatch and earlier role separation language.

## One chat / one owner / one active task
- KIC lead in this conversation designs, implements, tests, reviews, integrates and prepares submission. No separate worker chat or second AI handoff. Three functions Research / Verification / Risk remain logical stages of ONE ProofInvest product, not separate AI actors.
- Every user `ㄱ` means continue one real next action. At the start, read remote `lead/kic` HEAD and `LEAD_ACTIVE_WORK.md`, then check status/source/last tests; do actual work and conclude with remote SHA. No background work.
- Use `lead/kic` as the **sole default active development/refactor and documentation branch**, preserving prior commits. `main` stays stable until independent review/tests and explicit integration action. Existing feature branches are historical input snapshots only. Do not delete, rename, force-push or silently rewrite them. To import completed Research, inspect diffs/content, integrate carefully, run tests; preserve provenance.
- Separate conceptual functions (Research/Verification/Risk) with files/modules/tests, not chat-to-chat messaging or READY queue. `LEAD_ACTIVE_WORK.md` is the sole live work pointer. Prior `NEXT_TASK.md`, `WORKER_ROUTER.md`, `WORKER_CHAT_START_PROMPT.md`, `TASK_BOARD.md` are retained as archival evidence and cannot start work.
- Before modification: confirm code, permission, owner, recoverable HEAD, dependencies, API/expense, duplicate execution, secrets/PII, test path and rollback. Compare lightweight options when an architecture decision is required. No unauthorized scope, money, sharing or real data transfer.
- During work: inspect existing modules; change minimally; run meaningful tests; review changed files/secret exposure; GitHub commit with matched Author/Committer; verify remote SHA and relevant CI. CI success != actual external API/Production success.
- Complete a major task by updating `docs/roles/lead/STATUS.md`, `HANDOFF.md`, `TO_HACKATHON_LEAD.md` and this active task log in the same commit; include success/fail/untested and recovery. Historical feature TO_KIC_LEAD messages are input evidence, not a pending human handoff.
- Final submission remains participant-approved. Verify KIC 11/12 10:00 KST deadline, team conversion and real PDF receipt. Keep sensitive materials off Public GitHub.

## Rationale
**Chosen A** (lead branch, single conversation) vs **legacy B** (same conversation switches three feature branches plus dispatch reports). A removes ref switching, worker queues and round trips while retaining prior branch snapshots, tests and `main` gate. B adds merge/handoff overhead without independent reviewers; it is retired.

## One-line new-chat continuity
- `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]` is the participant's **KIC-specific primary** one-line startup phrase. Generic `[해커톤총괄 깃헙 레포지토리 확인하고 작업하셈]` is a secondary alias. Enter through `lead/kic/CHAT_BOOTSTRAP.md`, then current `LEAD_ACTIVE_WORK.md`, and verify remote HEAD before continuing. Do not restart old worker dispatch.
- Every meaningful task completion and chat transition updates active-work, lead STATUS/HANDOFF, upper lead report and relevant test evidence with a verified remote commit; stable bootstrap changes only for changed routes/policy. Not background automation.

## Mandatory end-of-work daily completion meter (2026-10-24 13:52:13 KST)
- Before each task: current KST day, immutable daily 100-point evidence gates, budget, and current [DAILY_PROGRESS.md](DAILY_PROGRESS.md) snapshot. Never repeat early-completed deliverables.
- **At EVERY actual work-end, partial handoff, block, or user `ㄱ` cycle completion**: update `DAILY_PROGRESS.md` with **earned points/100, percent, independently estimated remaining base hours + contingency hours = conservative remaining hours**, actual time observed or `미계측`, blockers/rollover, SHA/CI. Synchronize `LEAD_ACTIVE_WORK.md`, `STATUS.md`, `HANDOFF.md`, `TO_HACKATHON_LEAD.md` in same work unit. State same numbers in reply; do not assert total project completed.
- Empty progress is not success. Unknown dependency time != zero hours. Only evidence-backed gate completion earns points; prior daily plan 100% is distinct from whole KIC milestone completion. See [DAILY_PROGRESS_PROTOCOL.md](DAILY_PROGRESS_PROTOCOL.md).

## 2026-10-24 14:39:37 KST — 새 채팅 한 줄 인수인계 의무 (CURRENT, 과거 문구에 우선)
- 사용자 입력 `[kic 해커톤 깃헙 레포지토리 확인하고 작업하셈]`은 **재질문 없이 GitHub에서 KIC 총괄 역할을 최신 복원하고 다음 READY *실행 가능한* 코딩 과제를 수행**한다는 뜻.
- 새 채팅의 최초 정본은 반드시 `lead/kic` 루트 `CHAT_BOOTSTRAP.md` 와 `KIC_RESUME_STATE.md`. 기존 `HANDOFF.md`의 긴 순차 덧붙임은 이력이다. 원격 HEAD·코드·CI와 불일치 시 실제 증거를 우선하여 정본 상태를 고친다.
- 매 *실제 작업 종료/중단* 때 같은 커밋으로 `KIC_RESUME_STATE.md`의 완료/차단/다음 작업, `LEAD_ACTIVE_WORK.md`, `DAILY_PROGRESS.md`, `STATUS.md`, `HANDOFF.md`, `TO_HACKATHON_LEAD.md`를 갱신. 오류·미계측 시간·일일 완료율%와 남은 예상시간(기본+예비), SHA와 CI 성공/실패 명시. **공시 시스템만 정비할 때는 과거 일일 작업완료율을 왜곡하지 않는다**.
- 진척률은 60일 전체가 아닌 해당 날짜 100점 게이트. 의존성이 풀린 타 날짜 과제는 선행 가능하며 DAKER/DART 35%/90% 차단점수를 임의 보정하지 않는다.
