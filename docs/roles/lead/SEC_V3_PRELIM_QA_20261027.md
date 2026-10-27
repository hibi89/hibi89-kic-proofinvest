# SEC-referenced ProofInvest Global v3 preliminary candidate — 2026-10-27 KST

## Evidence and deliverable
- Preserved prior private Library frozen PPTX/PDF and review v2; created a **separate private review-only v3** PPTX/PDF in the conversation working session. Candidate files were **NOT pushed to this public repository or DAKER**, nor saved persistently to Library.
- v3 PDF: **10 pages, 493,063 bytes**, SHA-256 `bd07d0fa6283b9d2430a223402a443f14506f1ff2d147a98b8c3e10428d2e573`; v3 PPTX SHA-256 `54a641ff3c2d788a39d4deabac008b70084bb863acdf7104ce3a221596e14338`.
- Local QA: 10-page rendering, 0 extracted text elements outside page boundaries, 7 required contest proposal sections intact, working embedded KIC/SEC/GitHub/CI links; this does not equal official portal acceptance.
- New **manually checked** global source example: Apple Inc. FY2025 Form 10-K, CIK `0000320193`, accession `0000320193-25-000079`, SEC filing date 2025-10-31, year-end 2025-09-27. Official SEC Consolidated Statements of Operations page 29 total net sales USD millions: 2025 `416,161` vs 2024 `391,035`, manually recomputed 6.43% change. [SEC filing index](https://www.sec.gov/Archives/edgar/data/320193/0000320193-25-000079-index.htm) | [SEC filing primary document](https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm).
- **Critical limitation:** human web inspection and Decimal arithmetic are not ProofInvest auto-SEC API processing, live LLM, trained ML/DL, independent production E2E, stock recommendation, or authorized external publication. No such functionality claimed.
- Previous app commit `4fa5152` and documentation head `1043b0f`: [CI 40491440843](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40491440843) `257/257 PASS` offline only, **not** a test of new private v3 PDF or actual SEC adapter.

## Approvals and next action
1. The **participant must first approve the exact candidate PDF bytes and project title**. An earlier fixed SHA256 preflight is tied to the older frozen PDF; it must NOT be bypassed or marked pass for v3. Re-pin only after explicit approval and fresh independent input tests.
2. Only on separately explicit permission, authenticated team leader may upload the approved PDF, press final submit, and verify `제출 내역 → 최종` official receipt before 2026-11-12 10:00 KST. No submit attempted.
3. 2026-11-12 12:00–11-19 10:00 KST Elo voting and minimum vote condition also remain unperformed and account-gated.
4. Original Library files unchanged; this public note excludes private user documents and personal/credential data. Existing master progress stays **29 DONE / 3 BLOCKED / 28 NOT_STARTED**; new review-only proposal work is outside scheduled ledger, actual work hours unmeasured.

## Engineering next phase
Until prelim submission, prioritize artifact QA/approval rather than new runtime/ML expansion. If officially selected for the final round, investigate official SEC source ingestion, verifiable financial/capital/ownership history, bounded Agent, separate 3 index + 4 CPI YoY series and strictly holdout-tested conditional models; full security/production QA still required.
