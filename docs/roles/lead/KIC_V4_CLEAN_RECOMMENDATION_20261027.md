# KIC v4 clean private final comparison — 2026-10-27 KST

## Decision
Recommend the privately created **v4-clean** PDF over v3 for the upcoming **participant review**, based on greater specificity in the official higher-weighted Agent (25), differentiation (20), and feasibility (20) criteria. This is qualitative editing judgment, not an official judge score or selection prediction. Only the participant may approve exact PDF/title. Do not interpret an informal "continue" as authorization.

## Exact separate review artifact (NOT PUBLIC REPOSITORY)
- Name: KIC_ProofInvest_Global_V4_CLEAN_REVIEW_20261027.pdf
- 10 pages; 487,207 bytes; SHA256 `c53fb77f79e4b290c9d67d4d17d24d8a21ab4be189fb81885065cbbce570a8b1`.
- Editable PPTX SHA256 `f0efd10ac76f4bac3e494016f5f7e2faba199e8365b4cf879d9fd0e03f3aa195`.
- Compared with preceding private v4: **exactly two text labels** rewritten, replacing "draft candidate" on title page and "v4 comparison candidate" on last page with plain evidence/limitations. Technical claims and all remaining content unchanged.
- Owner-supplied private frozen editable template retains **258/258 geometrically identical shapes** across ten slides; PDF 0 page-overflow words, no replacement glyphs, four known SEC/contest/repository/CI hyperlinks and seven required sections present. Page 1 and 10 rendered and inspected visually.
- Source frozen PPTX/PDF, prior v3 and v4 originals SHA-verified unchanged. New review files are **conversation artifacts only**; never added to public GitHub or DAKER.
- The Apple FY2025 filing numbers (+6.43% YoY based on 416161/391035 USDm) remain *manually source-reviewed*, not produced by a functioning SEC API Agent.
- Current real implementation remains local deterministic verification/Streamlit trace, prior CI **257/257 PASS**. LLM Planner, live SEC API, ML/DL, deployment, performance outcomes and final submission **NOT_VERIFIED**.
- Existing `scripts/kic_submission_preflight.py` MUST continue to pin OLD original PDF 513113-byte digest; intentionally rejects this clean candidate. Do not bypass or re-pin until owner approves exactly this file and a fresh gate has passed.

## Next explicit owner and portal gates
1. Participant reviews the **exact named review candidate + official submission title**, and explicitly selects/approves.
2. On separate authorization, validate/re-pin a non-bypassable new submission guard without modifying original, and repeat file hash/format tests.
3. Only with authorized authenticated DAKER interaction, upload final PDF and confirm team leader `제출 완료` -> `최종` receipt **before Nov 12 10:00 KST**.
4. Independently handle Elo minimum voting 11/12 12:00 to 11/19 10:00 KST.
5. KIC official 60-day progress **29 DONE/3 BLOCKED/28 NOT_STARTED** unchanged; authoring time unmeasured. No code/deployment/public private-content transfer.

Official organizer source: https://daker.ai/public/hackathons/kic-ai-agent-competition
