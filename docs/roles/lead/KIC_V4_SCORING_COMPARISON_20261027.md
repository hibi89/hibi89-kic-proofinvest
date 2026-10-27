# KIC scoring-oriented v4 comparison draft — 2026-10-27 KST

**State: private comparison artifact, NOT owner-approved, NOT DAKER submitted, NOT a replacement for v3 or frozen original.**

## Why compare?
Official contest prioritizes solving a real finance problem with an Agent that interprets goals, chooses tools and produces results, not simply a question/answer chatbot. Existing v3 demonstrated SEC source validation and honest implementation boundaries but under-explained Agent tool decisions, differentiators vs generic RAG, and finalist pass/fail metrics.

## Private side-by-side draft
- Produced a separate v4 PPTX/PDF from v3 using the participant-provided ten-slide KIC editable layout. v3 and privately frozen original remained byte-identical. **No private candidate text, personal participant information, PDFs or PPTXs were committed to public GitHub.**
- Only **23 existing text shapes** were refined; no slide/shape/layout changes. PDF: **10 pages, 487,237 bytes**, SHA256 `65e47a56bdfcf2f9c7908ed06f8ce97b7f83d730903de5b8a0559831485ee2e4`; candidate PPTX SHA256 `e7b37df711e4c0c777822d34457685fa47b04bc92a224da20b36eafc5e6e8afd`.
- Verified same 258 shape IDs/types/geometries as original; PDF 0 out-of-page words, seven required sections, four known external links. Generated a private ZIP of v4 PDF, editable PPTX, review note and QA manifest, verified ZIP CRC and extracted bytes locally.
- **v3 remains the current named review candidate**, 493,063 bytes SHA256 `bd07d0fa6283b9d2430a223402a443f14506f1ff2d147a98b8c3e10428d2e573`. Existing public frozen-only submission preflight remains **old 513,113-byte original**, intentionally rejects v3 AND v4 unless separately reviewed and explicitly authorized. Do not bypass or silently re-pin.

## Precisely what improved (design only)
1. **Problem/differentiation:** `as_of`/disclosure timestamp gating, CIK+accession/version evidence chain, forced UNKNOWN for ungrounded conclusions; distinguishes source-evidenced review from generic Q&A or unbounded RAG.
2. **Agent architecture:** goal/CIK/date extraction -> planned LLM Planner tool sequencing -> planned official SEC Tool -> verifier -> risk -> cited response, with at most one failed retrieval retry before UNKNOWN and contradictory evidence escalated to HUMAN_REVIEW.
3. **Feasibility:** minimal finalist E2E target is one issuer's FY2025 10-K ingestion, source-linked arithmetic, and safeguards; explicit missing, contradictory and future-information tests rather than uncontrolled all-country expansion.
4. **Measurement:** planned five-question manual-vs-tool timing experiment, 20-citation manually audited sample, and a zero unsupported-confirmations safety target. These are proposed acceptance criteria, **not measured achievements**.
5. **Truthfulness:** real present evidence is offline Python/Decimal, rule-based PLAN/EVALUATE/DECIDE/REPORT, Streamlit AppTest, GitHub CI 257/257 PASS, *manual human* Apple 2025 SEC filing inspection. **LLM planner, live SEC API, automated data proof, model ML/DL, production, speed improvement or successful final submission have NOT occurred.**

## Selection, unchanged external gates
- **DO NOT mark v4 approved** from an informal continue command. Keep v3 as previous candidate and v4 as alternative pending participant's explicit exact file/title selection.
- Only once the participant explicitly selects a PDF: independently pin *that exact immutable file* without weakening any guard, followed by separately authorized authenticated DAKER final submission and confirmed `최종` receipt. Deadline **2026-11-12 10:00 KST**.
- No official 60-day ledger change: **29 DONE / 3 BLOCKED / 28 NOT_STARTED**, no actual work-hours claim. No deployment or DAKER account actions.
- Latest pre-work GitHub head `2ba3df7517d76d58b7a99e39dfe4da9b76ef08ef`, [prior successful CI #40495457622](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40495457622) 257 offline tests.

Official contest: https://daker.ai/public/hackathons/kic-ai-agent-competition

