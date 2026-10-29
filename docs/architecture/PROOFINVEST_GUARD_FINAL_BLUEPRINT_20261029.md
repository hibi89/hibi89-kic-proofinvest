# ProofInvest Global + Guard-Agent — Final implementation blueprint (2026-10-29 KST)

**Status:** OWNER-APPROVED DESIGN, NOT IMPLEMENTED. Repository: hibi89/hibi89-kic-proofinvest, branch lead/kic. This document records the 2026-10-29 direction, superseding the earlier *no Guard-Agent* design limitation, but does not erase the 2026-10-27 fixed issuer/SEC + three US benchmarks + four CPI/HICP series finalist scope. The seven external series remain **finalist roadmap only**, not four-day MVP dependencies. Official preliminary remains organizer PDF <=10 pages with seven prescribed sections by 2026-11-12 10:00 KST. Existing private originals and official submission gates remain unchanged.

## Decision and product
A: extend existing ProofInvest Python application with an isolated deterministic Guard module. Do not require Lightning Azent, RAG_STUDIO, SMAX² or a new service. Existing Research -> Verification -> Risk -> Report stays intact; Guard sits **after evidence verification/risk**, before a **simulated investment-review authorization**, not a trade/payment. No KIC internal-policy claim, real KIC connection, brokerage, capital call, transfer or investment recommendation.

B: external Lightning Azent orchestration is deferred: more integration boundaries, credentials, deployment and failure modes, with no proven four-day benefit. Do not claim numeric reuse percentages or exact engineering hours as facts.

## End-to-end sequence
1. User selects issuer, CIK, filing accession, as-of date and a declared claim.
2. Research yields bounded structured claim(s), retaining source, accounting context, currency, unit, period, consolidation, accession, publication/collection times. No new LLM required for MVP; synthetic or manually supplied claims must be conspicuously labeled.
3. Existing Disclosure Lightning / ProofInvest SEC pipeline resolves permitted evidence, retains original SHA-256, and marks provenance as **unverified** unless independently established. Network disabled by default; real SEC requires separate explicit approval and compliant contact User-Agent. A local ZIP hash alone is NOT SEC authentication.
4. Existing Decimal verification recalculates with exact integer/decimal strings (never binary float). Verdict VERIFIED/CONFLICT/UNAVAILABLE, source and formula. Verification is immutable from Guard perspective.
5. Risk module emits evidence-grounded indicators or UNKNOWN. Guard evaluates verification + risk + versioned **demonstration policy**; conflict and hard policy breaches dominate; unknown/unavailable HOLD; only all verified and within policy may be eligible for APPROVE.
6. Human explicit approval is a separate authorization record; never rewrite verification verdict or silently turn REJECT into APPROVE. A manual exception may create an exception-request record requiring review, **not an automatic override**. Guard APPROVE means *eligible for human review*, not an executed order.
7. Append audit event and show reason, rule/version, input/evidence hashes, run ID and timestamp in UI/report.

## Minimal domain contracts
Claim: claim_id, issuer_cik, ticker, accession, form_type, metric, period_start/end, fiscal_period, consolidation_basis, unit, currency, claimed_decimal_string, source_ref, as_of, evidence_provenance.
Verification: verification_id, claim_id, observed_decimal_string|null, computed_decimal_string|null, formula, verdict, reason_code, evidence_hash, verified_at, provenance_state.
Policy: policy_id, version, rules, applicability, thresholds as decimal strings, effective_at, DEMO_POLICY marker.
GuardDecision: decision_id, run_id, verification_ids[], policy_id/version, decision(APPROVE|HOLD|REJECT), rule_hits[], reason_codes[], input_hash, decided_at.
HumanReview: event_id, decision_id, reviewer_label (local non-sensitive), action(ACKNOWLEDGE|REQUEST_EXCEPTION|AUTHORIZE_SIMULATION), rationale, timestamp; no real external execution.
AuditEvent: event_id, run_id, sequence, type, canonical_payload_hash, prev_event_hash, event_hash, timestamp; event_hash=SHA256(domain_separator || prev_hash || canonical_json). A local SQLite hash chain is tamper-*evident*, not immutable against privileged rewrite. Use append-only application API, SQLite transaction, foreign_keys=ON, unique(run_id,sequence), no implicit replacement. Audit read independently recomputes chain and flags corruption. Never place secrets or raw sensitive documents in logs.

## Decision precedence and safety
- Malformed input, untrusted/unavailable source, missing periods/units, stale or unsupported policy, insufficient risk inputs => HOLD (fail closed).
- VERIFIED is necessary but not sufficient for APPROVE; hard demonstrative limit breach => REJECT.
- CONFLICT => REJECT for the simulated review, without asserting fraud or hallucination as fact.
- Multiple claims: any REJECT => REJECT; else any HOLD => HOLD; else APPROVE-ELIGIBLE.
- Audit write failure => no successful decision acknowledgement; idempotency key/run_id prevents duplicate approvals/events.
- Replay from pinned local synthetic fixtures must label SYNTHETIC_FIXTURE. SEC local captures are not authenticated by digest alone.
- No binary floats in financial calculations, no SQL policy expression execution, no dynamic eval, no uncontrolled network retry.

## Storage and API boundary
Prefer new tables guard_policies, guard_decisions, human_reviews, audit_events with immutable IDs and references to **existing** verification/evidence tables; inspect actual schema first and migrate additively. Avoid replacing existing tables or changing source formats. Pydantic or dataclasses may validate boundary; prefer current dependency stack. Decimal values serialized as canonical strings. Existing UI should be extended with a single Guard decision + audit panel, not rewritten. Read path never recomputes or changes decisions.

## Acceptance matrix (offline first)
A VERIFIED claim under policy => eligible APPROVE, no human authorization inferred.
B VERIFIED but policy breach => REJECT.
C CONFLICT => REJECT, no exception approval.
D UNAVAILABLE/ambiguous source => HOLD.
E multiple claims mixed => highest severity.
F policy missing/stale => HOLD.
G changed input/policy invalidates earlier approval.
H audit duplicate run/replay idempotent, corruption detected, storage failure fail closed.
I UI displays exact synthetic/unverified status and no real transaction.
J existing Research/Verification/Risk tests and stored data unchanged.
Tests should include isolated unit tests, one offline E2E Streamlit or CLI path and actual live data ONLY after separate authorization.

## Four-day target, conditional
Day 1 (3-5h): inspect HANDOFF, STATUS, AGENTS, REQUIREMENTS, frozen scope, real source and schema; map interfaces and prepare migration/backout; parallel draft official 7-section PDF content privately.
Day 2 (7-10h): implement policy + Guard + additive audit with test matrix; use existing evidence fixtures.
Day 3 (8-10h): UI integration and one end-to-end reproducible demo; add failure/replay tests.
Day 4 (6-8h): official <=10-page PDF based on actual evidence, traceability/diagram, QA and package. **This is an aggressive target, not a guarantee**. If blocked by existing integration, ship PDF-only preliminary on time; do not misrepresent demo as real SEC or submitted.
No new paid APIs, production deploy, broad macro ingestion, ML training or DL retrieval before prelim. Existing 3 indices + 4 inflation series, conditional sklearn and pretrained filing retrieval remain **post-finalist** scope, per 2026-10-27 decision.

## Preliminary PDF
Use **organizer's exact seven required sections**; do not substitute a proposed ten-page outline for mandatory headings. Within <=10 pages cover problem, architecture, verification, demo Guard policy, evidence/audit, limitations, feasibility, value and finalist roadmap. Preserve official template, original and prior SHA pin; any exact private PDF modification or upload requires separate owner authorization. Official DAKER final click/receipt requires explicit permission.

## Status and next actions
Design approved and published only; Guard code, tests, E2E, live SEC, official PDF, Production and submission NOT completed by this document. Existing CI results reflect earlier code, not Guard functionality. Next: inspect actual source interfaces, implement additive module, validate offline, update STATUS/HANDOFF with code SHA/test counts. Keep lead/kic only, preserve DL-owned feature/disclosure-lightning, no force push.
