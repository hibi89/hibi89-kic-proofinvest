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
