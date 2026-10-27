# KIC Lead -> DL Technical Lead | Owner directive 2026-10-27 23:50 KST

**Appointment:** Previously assigned Bid Owl chief now leads Disclosure Lightning inside the SAME public KIC repo, on feature/disclosure-lightning. Preserve unrelated private Bid_Owl repo/branches. Do not port private source verbatim.

## Deadline and ownership
- **2026-10-28/29 minimum working unit:** SEC Submissions official-shaped JSON input, strict CIK/accession/form/date/source validation, immutable SQLite version/provenance, repeat sync dedup, versioned JSON output and CLI, deterministic tests. Optional real official SEC request ONLY with deliberate opt-in, compliant real contact-bearing User-Agent and rate/access controls; no success claims without provider evidence.
- **After MVP through submission:** integration tests, missing functionality, 10-K/A/10-Q/8-K, as-of boundaries, incremental changes, SEC provider, QA, then UI/frontend. The Nov12 KIC preliminary PDF-only submit must not become dependent on unfinished DL functionality. If finalist, final deadline Dec22 10:00 KST.
- **DL-owned paths:** disclosure_lightning/ package, DL-scoped tests and docs/disclosure-lightning/TO_KIC_LEAD.md + DL_HANDOFF.md on its feature branch. Cross-module ProofInvest changes proposed in PR and reviewed by KIC chief.
- **Security:** no private Bid_Owl code, creds, customer data, PDF/PPTX, or copied restricted external source bytes published in the KIC public repository.

## Bidirectional GitHub communication
1. DL writes [TO_KIC_LEAD](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/disclosure-lightning/docs/disclosure-lightning/TO_KIC_LEAD.md) and [DL_HANDOFF](https://github.com/hibi89/hibi89-kic-proofinvest/blob/feature/disclosure-lightning/docs/disclosure-lightning/DL_HANDOFF.md) with latest SHA, tests, blockers and next step.
2. KIC chief writes [TO_DL_LEAD](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/disclosure-lightning/TO_DL_LEAD.md) (this file) and [KIC_DL_REVIEW](https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/disclosure-lightning/KIC_DL_REVIEW.md). DL must read these URLs from lead/kic explicitly before new steps.
3. Create and use one **draft PR** from feature/disclosure-lightning into lead/kic for tests/diff/review. KIC does NOT merge until schema/CI/security gates pass. Fetch remote SHAs, not memory.
4. Message shape: KST | branch+SHA | actual paths | command | test/CI | schema | blockers | next action | KIC decision needed.

GitHub files/PRs provide shared visibility, **not automatic simultaneous execution, push alerts or ChatGPT inter-session messaging**.
