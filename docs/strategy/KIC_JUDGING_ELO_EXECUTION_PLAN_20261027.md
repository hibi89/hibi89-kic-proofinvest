# KIC ProofInvest Global — Judge-Criteria Response and ELO Participation Plan (2026-10-27 KST)
**Authority:** Owner shared the published official judge scorecard, original source https://daker.ai/public/hackathons/kic-ai-agent-competition . Live official page checked on Oct27. This document is a SUBMISSION PROPOSAL and checklist, NOT an altered official 7-section original PDF or proof of submission. Keep [final product inputs](../architecture/FINAL_KIC_PRODUCT_DIRECTION_20261027.md) and [analytics reuse/visualization](../architecture/ANALYTICS_REUSE_VISUALIZATION_DECISION_20261027.md); no scope expansion, raw code edits, external API, or training required before preliminary.

## Actual score, not inferred 100% bars
**Preliminary final weighting**: professional committee 70%, participants' pairwise ELO 30%.
**ELO**: November 12 12:00 – November 19 10:00 KST; ONLY finalized-submission participant teams vote, their own artifact not in pairs, minimum direct votes required for *both cast and received results* to count ("No Vote, No Gain"). **Exact minimum vote count NOT VERIFIED: must check actual DAKER UI/official notice; never invent it.** Do not engage in collusion/manipulation. Register final PDF using organizer upload, **captain must click "제출 완료"**, receive final proof by Nov12 10:00. AI may remind users but cannot perform their authenticated ELO votes without explicit actions; no automated vote bots.
**Professional judges (100-point rubric; 70% of preliminary overall)**:
- Problem definition / investment-finance suitability **20** — actual decision-maker pain: time, conflicting filings, changes in ownership/capital structure, blind spots in interpreting global market and inflation data; avoid generic "investors need chatbot".
- AI Agent composition/design **25** — explicit **Research→Verification→Risk→Report** decision/tool chain, state machine, source IDs/CIK/accession/date, planner triggers/subagent/tool calls, cross-check, re-run, UNKNOWN/error handling, measurable autonomy without fabricating independent models.
- Differentiation/creativity **20** — evidence-linked discrepancy detection and overlooked historical variables/hypothesis generator, **not** promised stock prices or generic LLM summarizer.
- Feasibility for finalist window **20** — actual existing Python unit-test evidence accurately labeled OFFLINE/SYNTHETIC; plan one real SEC issuer + 3 benchmark indices + 4 CPI as ceiling, rules/ML/no-label fallback, use existing Streamlit. Never infer test accuracy from CI or claim full sources already ingest.
- Utility/scale **15** — one traceable reproducible issuer case, exportable cited report, cross-company future reuse, bounded costs and analyst human review.
**Final 100-point online presentation on Dec29**, selecting **6 out of 12 finalists**:
- Practical issue solving/value 20
- Agent implementation completeness 25
- Agent technical depth 20
- Results trustworthiness 15
- Usability/practicality 10
- Presentation/Q&A 10.
**Tie-break order:** Agent completeness (25) -> problem/value (20) -> Agent technical depth (20).
Finalist code + judge accessible demo URL + PDF due Dec22 10:00, optional Youtube demonstration may have bonus as official rules describe.
Source: https://daker.ai/public/hackathons/kic-ai-agent-competition .

## Primary product proposition (can be evaluated quickly by ELO voters)
'ProofInvest Global — SEC 등 기업 공시 근거를 교차검증하고, 투자자가 놓친 과거 변수와 지분·재무 위험을 찾아내는 AI 투자 리서치 Agent.'
**Immediate ELO comprehension within one preview:** (1) user types issuer and as-of-date, (2) Agent tool/verification graph, (3) concise one-page evidence-backed result card (Observed / Tested Relationship / Missing). Use readable typography, not a page of model acronyms or dense infrastructure.

## Narrow Agent design — actual action autonomy vs source of truth
(1) User chooses issuer, question and as-of date; planner determines required SEC filings and historical context, without requiring a new paid system.
(2) Research Agent uses official SEC filing metadata and authorized public filing URLs; record CIK, accession, publication timestamp and exact source spans. If source unavailable, mark UNKNOWN.
(3) Verification Agent normalizes financial units/periods/stock issuances/beneficial shareholding facts, cross-checks issuer claims, citations and sources, classifies VERIFIED / CONFLICT / UNAVAILABLE; numeric calculations deterministic and auditable.
(4) Risk Agent forms risk and **missed factor candidates** ONLY from verified available facts. Historical context only 3 stock indices + 4 monthly YoY CPI/HICP inflation series; time-release alignment and provenance, conditional sklearn ML with walk-forward held-out baseline and `NO_TRAIN` when insufficient.
(5) Licensed pretrained MiniLM semantics can retrieve English filing risk-related passages with benchmarked accuracy; independent factual verifier, no free-form "DL detects risk" assertion.
(6) Report Agent produces concise analyst memo/dashboard and export with transparent source URLs, timestamps, citations, unknowns and no investment orders.
**Demonstrable tool cycle**: User goal → planner selects official filing fetch + allowed historical context → verifier catches incompatible accounting period or source conflict → planner retrieves amended/source alternative if valid → evidence-sensitive risk draft → human reviewer sees source and uncertainty. Must distinguish implemented synthetic prototype from finalist roadmap.

## Recommended 10-page maximum storyboard using EXACT organizer 7 required sections
1. **Summary**: main tagline, sponsor user, one high-impact annotated report mock (visibly labeled mock), input→evidence→action outcome.
2. **Problem definition**: real KIC investor workflow and the missing verified/evidence problem; bounded example, no fake statistics.
3. **Service proposal**: issuer company/as-of research UX, signal cards, human-in-the-loop reporting, one sample.
4. **AI Agent composition**: four agents and control states, decision/tool routing, autonomous vs approved actions.
5. **AI Agent composition (cont.)**: exact SEC/API, error/conflict/UNKNOWN re-plan sequence and illustrative evidence chain.
6. **Data utilization plan**: SEC company/ownership core + THREE indexes + FOUR monthly all-items inflation YoY sources; time/currency/rights/revision guardrails, no expanded FX/rate/metal series.
7. **Data utilization plan (cont.)**: justified conditional sklearn ML vs baselines and pretrained filing-DL retrieval; no forecasting guarantee; descriptive fallback.
8. **MVP development plan**: current code and offline CI with status, bounded implementation tasks by Dec22, actual acceptance tests. Existing source status truthfully labeled; no training/deployment claims.
9. **MVP plan / product proof**: visible Streamlit-style mock view of top-3 candidate insights, verified filing/ownership, separate 3-index and 4-CPI charts, sample-source passage and trust statuses. Explicit prototype/roadmap boundary.
10. **Expected effects**: analyst time/accuracy/oversight intended effects as testable outcomes, measured vs hypothetical split, future extension.
Slide/page labels must preserve all 7 required organizer sections and template structure; use existing organizer file and exact user approval, not publication of private PDF.

## Decision priority
1. Score 25 design and 20 feasibility through authentic tool/guard flow; no new frameworks as prelim dependency.
2. ELO 30% requires visual one-glance clarity and actual timely vote participation. Record screenshot/time/proof of minimum votes; do not assume target is met.
3. Finalist ties favor completeness then actual investor utility; if budget limited, make SEC evidence/source exact and reliable before optional new DL/ML/historical charts.
4. Before submission: inspect exact 7-section official PDF, 10-page count, layout, correctness, source rights, repo claims, owner approval, submit proof. Post-submission: ELO vote due Nov19 10:00; expert window until Dec1; finalists Dec3; final Dec22 / presentation Dec29.
5. KIC source repo current PR/prototype may have offline synthetic tests only. No success percentage is manufactured from programmatic plan or tester count.
