# ProofInvest Global — Adaptive macro + industry indicators (owner-approved, 2026-10-30 KST)

**Status: DESIGN DECISION ONLY. No feed, license, API, model, benchmark, UI or submission implementation is asserted.**
**Precedence:** This 2026-10-30 owner decision supersedes the *seven-series-only* and *no extra rates/commodities/FX* restrictions in 2026-10-27 FINAL_KIC_PRODUCT_DIRECTION, FINAL_TOOLCHAIN, ANALYTICS_REUSE_VISUALIZATION_DECISION, REQUIREMENTS and SUBMISSION_SCOPE_FREEZE **for finalist product design only**. Earlier documents remain historical and are not silently rewritten. The **2026-11-12 10:00 KST official <=10-page seven-section PDF-only preliminary, original file protection, explicit owner review and DAKER submission authorization remain unchanged**. Do not make this expanded design a preliminary dependency.

## Product rule: common candidate pool + company-specific dynamic selection

Do not create a generic always-on economic dashboard or assert that more series necessarily improves investment decisions. Start with a **bounded common candidate pool of 11 named series**, then use issuer SEC filing evidence (geography, input costs, debt, supply chain, sector, dated exposure) to select and explain only relevant factors. Relevance is a *review hypothesis*, not causality or a trade signal. Missing, non-licensed, revised or temporally invalid data => NOT_CHECKED / INSUFFICIENT_EVIDENCE; do not synthesize.

### Common candidate pool (11; 3 equity + 5 inflation + 1 yield + 1 gold + 1 oil)

| Category | Candidate | Interpretation / guard |
| --- | --- | --- |
| Equity 1 | S&P 500 | Official index vs ETF proxy must be labeled |
| Equity 2 | Nasdaq-100 | Not Nasdaq Composite; ETF QQQ is a proxy |
| Equity 3 | Dow Jones Industrial Average | Price-weighted 30-stock index |
| Inflation 1 | United States CPI-U, all items, monthly YoY % | BLS; publication timestamp / vintage |
| Inflation 2 | China national headline CPI, monthly YoY % | NBS; release date / revision |
| Inflation 3 | Euro area all-items HICP, monthly YoY % | Eurostat; euro area is a region |
| Inflation 4 | Japan national all-items CPI, monthly YoY % | Statistics Bureau of Japan |
| Inflation 5 | **South Korea nationwide all-items CPI, monthly YoY %** | Statistics Korea / KOSIS; avoid treating index levels across countries as directly comparable |
| Rates 1 | **US 10-year Treasury yield** | Level in %; distinguish yield change vs level and issuer debt/refinancing exposure |
| Safe-haven 1 | **Gold price** (one specified USD benchmark, e.g. spot XAU/USD or recognized fixing, chosen only after rights verification) | USD/oz and source; not an automatic fear gauge |
| Energy 1 | **WTI crude oil price** (Brent as alternative/sector-specific, not silently a 12th common feed) | USD/barrel, benchmark/source/roll method; industry relevance required |

These are **candidate data contracts**, not a requirement to ingest all 11, to add 11 charts, or to include them in the preliminary PDF. For the five CPI/HICP series compare **YoY rates**, not raw index levels. For cross-series comparisons retain frequency, currency, units, source URL/license, first-publication/release and collection timestamps, revision vintage and as-of eligibility. Avoid interpreting correlations as causal.

### Industry/issuer-specific optional extension (not globally required)

- **FX / USD exposure:** relevant exchange rate or DXY where issuer filings support export/import, USD debt or international revenue exposure; currency pair, source, date and quote convention explicit.
- **Copper:** industrial/material input and electrification exposure; specific price series and unit/source.
- **Rare earths:** not one generic "rare-earth price"; choose **specific material/grade/market** (e.g. NdPr oxide or dysprosium oxide) only with verified company relevance and lawful, adequately historical data. Price opacity and data rights may force NOT_CHECKED.
- **Semiconductor prices:** DRAM/NAND or other precisely specified contract/spot series only for a materially exposed issuer and after commercial data rights/frequency review.
- **Other industry variables:** require a separate evidence-based proposal, named source/license and approval; do not auto-expand feeds from untrusted prompts.

**Selection pipeline:** issuer filing/source-backed exposure → candidate factor + rationale → rights/coverage/release-vintage gate → as-of temporal alignment → descriptive baseline → optional walk-forward/group-safe ML with meaningful out-of-sample gain → max three source-backed overlooked-factor review cards. Show selected and rejected/not-checked factors with reasons. No invented exposure, causal identification, model confidence percentages, neural price forecasts or automatic trading.

## Architecture and reuse boundaries

ProofInvest Research → SEC/Disclosure Lightning evidence → deterministic Verification → Risk → Guard/human review/audit → source-linked Streamlit Report. Adaptive macro/industry context enriches **Risk/Report**, never overrides SEC fact verification or Guard policy. Existing AI_AutoML_Analyst supplies **selected, rights-reviewed** baseline/split/chart patterns, not its entire FastAPI service. Licensed pretrained English filing text retrieval (MiniLM) is conditional and evaluated against keyword/BM25. **No SMAX, DBVORA, HAE, LA, SOVIA, RAG_STUDIO or full AutoML service dependency for KIC**.

## Delivery gates and priorities

1. **Now, preliminary (due Nov 12):** keep organizer's official PDF unchanged unless separately approved; seven mandatory sections, <=10 pages, truthful current-vs-roadmap wording. The adaptive indicator architecture may be described as a **future finalist roadmap**, not implemented.
2. **If finalist (Dec 03 decision):** one lawful SEC issuer case and deterministic verified report first; establish source/rights/time metadata for the 11 common *candidates*, then select the smallest genuinely relevant subset. Verify Korea CPI source/vintages; gold/yield/WTI licensing and coverage before use.
3. **Optional industry expansion:** add one specific rare-earth/copper/semiconductor/FX feed only when a named issuer's filing supports it, rights are acceptable, and temporal evaluation is meaningful.
4. **QA:** unit/contract tests for missing/vintage/licensing, as-of leakage tests, one issuer E2E, source citation and chart labels, no-train fallback. Actual results must be reported from executed tests; do not claim a live feed based on this document.
5. **Finalist submission (Dec 22):** judge-accessible working URL/code/report only after genuine execution, rights, owner authorization and browser verification.

**Scope-change rationale:** Owner explicitly requested South Korean CPI, US 10-year yield, gold and oil as common candidates, with FX/copper/rare-earth/semiconductor indicators selected dynamically by issuer/sector. This replaces the old fixed seven-series ceiling while preserving the preliminary deadline and safety gates.
