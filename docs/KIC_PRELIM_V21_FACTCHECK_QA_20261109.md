# P288 KUODRA V21 preliminary reviewer-facing proposal QA — 2026-11-09 KST

## Why the revision matters
V20 had small body text, abstract technology story, insufficiently differentiated custom-owned work and a potential confusion between 2,188 passing code tests vs actual financial/ML efficacy. V21 is a substantive 10-page redesign. Unlike cosmetic V20 edits, it organizes one main proposition per page with enlarged institutional type and KIC workflow mapping.

## Files outside GitHub
- PDF KUODRA_V21_KIC_PRELIMINARY_SUBMISSION_CANDIDATE.pdf — 256649 B; SHA256 34e1691964d4c7a03947b9e2d66ccf31ac2679a8be5d3e386e4d890453b00349
- PPTX KUODRA_V21_KIC_PRELIMINARY_EDITABLE.pptx — 102408 B; SHA256 ce94e50395c833a63df617653910c69b88e5737436d02543bf1990eceafc4402
- Contact KUODRA_V21_ALL_10_PAGES_PREVIEW.png — 698847 B; SHA256 a859ecbc6d38f2d4a219186e883db1845e25653a776cf166170585d03c1f0fc7
- Review ZIP KUODRA_V21_KIC_FINAL_REVIEW_PACK_20261109.zip — 959804 B; SHA256 224de9e0d9a94b3fd0f2e81c65062316688efc63059bd5843e6912f6085c97b3
- All files generated and byte/CRC validated within this conversation container; NOT uploaded to Library or GitHub repo. Historical V20 and V19 original untouched.

## Validated PDF/presentation
PPTX 10 editable slides, 258 text shapes, zero picture-shape flattening. PDF 10 landscape 16:9 pages. All 7 mandatory sections detected: summary p2, problem p3, service p4, AI Agent p5, data p7, MVP p8, expected effect p9. Six functional hyperlink annotations: Apple primary source (p3), KIC process and risk (p4), GitHub source, exact CI, DAKER terms (p10). Text bounding words outside page: 0. All pages rendered; master KIC logo + page number collision discovered in initial version and corrected, inherited shadow removed, final contact sheet examined.

## Claims and boundaries
- Existing self-coded 7 stage flow in proofinvest/ticker_local_workflow.py: prepare source receipt; revenue check; iXBRL original check; Engine B; optional A/C; Guard report; independent report replay. Source consistency does NOT authenticate official SEC publisher bytes. Source code also proofinvest/owner_source_global_agent.py, proofinvest/kuodra_sec_guard.py.
- Reused tools: Python/Decimal, Streamlit, SQLite, Playwright, GitHub Actions and optional local Qwen. Custom issuer/period/10-K/A gating, A/B/C integration, Guard HOLD/REJECT, hashes and independent replay. Optional local Qwen requires 2 consent gates after full original replay; real inference quality unverified.
- ML implementation proofinvest/ml_explainability.py parses operator-supplied evaluation and verifies format, walk-forward date, issuer/source references, but neither trains models nor independently measures predictive gain. V21 intentionally labels ML conditional, with genuine rights/input, predeclared baseline and out-of-sample walk-forward evaluation, MAE/RMSE for regression, PPV/Recall/Brier if classification; if no gain/insufficient evidence => NO_TRAIN. No invented model accuracy, probability, Sharpe, trading return, or KIC selection chance.
- Apple FY2025 $416,161m vs FY2024 $391,035m = +6.43% manual calculation from https://www.apple.com/newsroom/pdfs/fy2025-q4/FY25_Q4_Consolidated_Financial_Statements.pdf . +30% is prominently fictional comparison, not Apple claim nor tested KUODRA source authentication.
- KIC examples are PROPOSED handoff from official https://www.kic.kr/ko/investment/process and https://www.kic.kr/ko/investment/risk-management; no actual interface/integration. No measured work-time benefit.
- Functional code SHA 1f89ef7671f158307fbca35e78c621de54264fa1, actual GitHub Actions https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/42521769506 completed SUCCESS, six mandatory jobs/Ubuntu 2188 tests passing; Windows 2187 PASS, 1 SKIP. This verifies the offline code path only. Four optional real model jobs SKIPPED. Official product 76/100 RELEASE HOLD; primary publisher-origin SEC originals, contest market index/stocks rights, full real A/B/C, model efficacy and Production unresolved.

## Submission constraints
Official DAKER https://daker.ai/public/hackathons/kic-ai-agent-competition: PDF<=10 pages, seven mandatory sections; submission deadline Nov 12, 2026 10:00 KST. Team leader must upload PDF, click 제출 완료 and verify final. As of this document: **NOT SUBMITTED**, no user approval yet. No billable API, license change, SEC 403 retry, production exposure or private presentation publication. PPTX Windows font parity not revalidated; tested PDF is primary.
