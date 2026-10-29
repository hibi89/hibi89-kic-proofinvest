# KIC preliminary submission gate — verified against public DAKER rules

Official rules: https://daker.ai/public/hackathons/kic-ai-agent-competition
Checked: 2026-10-29. **This is an internal checklist, not a submission or a replacement for the official template.**

## Non-negotiable submission rules
- Due: 2026-11-12 10:00 KST; PDF, at most 10 pages.
- Download the organizer-provided template from the official competition page, author using that template, and convert to PDF.
- Retain all seven required sections (titles can be localized as organizer allows):
  1. summary
  2. 문제 정의
  3. 서비스 제안
  4. AI Agent 구성
  5. 데이터 활용 계획
  6. MVP 개발 계획
  7. 기대 효과
- Submission is through the official competition submission tab. Do not mark as submitted without a receipt.
- Official public rules inspected do **not** state English is mandatory. Verify organizer template and any new board notices before final language decision.
- Public data/model/API/code/assets must have provenance, applicable licenses and actual usage rights. Merely citing a source does not grant redistribution rights.
- No unsupported implementation, benchmark, API, test PASS, SEC authentication or financial trading claims.

## Proposed 10-page internal content mapping
1. summary — ProofInvest Global + Guard-Agent, problem and measurable MVP goal
2. 문제 정의 — evidence provenance, period/unit mismatch, unverifiable financial claims
3. 서비스 제안 — human-reviewed simulated investment evidence workflow
4. AI Agent 구성 — research / verification / risk / deterministic Guard / review boundary
5. AI Agent 구성 — decision precedence, missing data HOLD, conflict REJECT, simulated eligibility
6. 데이터 활용 계획 — SEC-format curated Apple FY2025 offline source, exact Decimal, licenses and limits
7. MVP 개발 계획 — implemented local modules, evidence IDs, SQLite hash-chain limits
8. MVP 개발 계획 — test matrix and reproducible CLI; label runtime status honestly
9. 기대 효과 — auditability, repeatability, reduction of ungrounded numeric claims; proposed metrics only
10. summary / 기대 효과 — concise differentiation, limitations and finalist roadmap

## Evidence and status
- Implementation branch: lead/kic.
- Offline CLI: `python -m proofinvest.guard_demo` (actual execution not independently verified as of 2026-10-29).
- SEC sample is **manually curated**; numeric consistency is not authenticated SEC source provenance.
- Guard APPROVE means *eligible for explicit human simulation review*, never investment execution.
- SQLite SHA-256 application hash-chain is tamper-evident under limited threat model, not immutable.
- Streamlit and CLI tests remain **unverified until a recorded actual run**.
- External data rights and organizer's downloadable template still need final inspection.

## Pre-submission acceptance
- [ ] Confirm organizer template and retain its seven sections.
- [ ] Verify no more than 10 PDF pages and render all pages.
- [ ] Run CLI + unittest; capture exact SHA, environment, PASS/FAIL/SKIP and stdout evidence.
- [ ] Verify every screenshot depicts a real working feature, not a design mockup.
- [ ] Check source attribution, rights, data age, source provenance and no secrets.
- [ ] Owner reviews final PDF and explicitly authorizes official submission.
- [ ] Capture submission receipt before deadline.
