# DAKER KIC — participant-only P0 proof checklist (read-only)

**Purpose:** Establish whether the participant's authenticated account can *eventually* make the KIC proposal's final submission. This checklist is not approval to upload, team-convert, save, change an account, or submit.

## Four visible facts to record — no private credentials
1. After the participant opens https://daker.ai/public/hackathons/kic-ai-agent-competition and signs in, record whether the KIC page displays `참가 신청 완료` and whether the entry is `개인` or `팀`. An earlier single-person team `1/1` UI was observed, but does **not** prove a current team-leader role.
2. If the account is in a team, inspect the member/role panel for **team leader identity** and whether the team has been **converted for contest participation**. Do not press any `팀으로 전환` button as a side effect of this inspection; an actual conversion is a separate account action requiring user approval.
3. Inspect `제출` → `예선 기획서 제출` and record: `팀장만 제출`, `먼저 저장`, `저장되지 않은 변경사항`, `동시 편집` or whether the final submit control is visibly available. **Do not upload/replace/synchronize any PDF or click `제출 완료`** in a read-only preflight.
4. Inspect `제출 내역` and distinguish `최종` from `초안`/`임시저장`/no record. A visible final state plus actual submission receipt would be needed for a real submitted claim. Do not conclude final submission from a navigational button.

## Decision tree
- **Not signed in / phone authentication required:** `BLOCKED_EXTERNAL`: user-owned sign-in/phone confirmation. Never request passwords, verification codes, cookies, screen recordings of personal details or identity documents.
- **One-person team shown but role/converted status unclear:** keep both 10/25 and 11/09 at 60/100 BLOCKED; inspect leader/participation conversion separately.
- **Final submit disabled:** use actual tooltip/error to diagnose leader role, unsaved draft, unsaved edits, another editor. Do not guess or modify the submission to make button appear.
- **Final submit enabled:** this only clears an *access-right inspection* criterion; do not change 11/10 `NOT_STARTED` to submitted. User must separately authorize final PDF selection and submission. Check exact frozen 10-page candidate, **513,113 bytes**, pinned SHA256 `0bdbbf04f374a7ccb39cd15e1aa700a006514278b094d32bb05ac7db610e034e` privately; do not upload to public GitHub.
- **Submission already final:** independently verify visible `최종` submission history, receipt and correct PDF. Avoid redundant submission.

## Evidence and timing
- A redacted screenshot of the role/submit area is enough to continue analysis **if user chooses to provide one**; redact names, email, phone, browser session and tokens. Plain text describing visible role/buttons also works.
- Official DAKER contest https://daker.ai/public/hackathons/kic-ai-agent-competition says final `제출 완료` is for the team leader. DAKER's dedicated submission note https://daker.ai/community/kic-ai-agent-preliminary-proposal-final-submission explains why PDF upload does not equal final submission and why `제출 내역` must read `최종`.
- Site community troubleshooting https://daker.ai/community/revert-overwritten-kic-ai-agent-proposal details disabled-button conditions. These are **general possibilities**, not confirmed diagnosis of this account.
- Official cutoff **2026-11-12 10:00 Asia/Seoul**, planned controlled early submission **2026-11-10**. Team/leader access should be checked before the last day.

**As of 2026-10-24:** current browser connector cannot access the originating browser login context, therefore no fresh authenticated account check performed. 10/25+11/09 BLOCKED 60/100, 10/30 DART BLOCKED 90/100, actual 11/10 submission NOT_STARTED. No account/private files modified.
