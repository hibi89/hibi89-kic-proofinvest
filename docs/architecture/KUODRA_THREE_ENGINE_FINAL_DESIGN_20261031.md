## 2026-10-31 P44 Engine A first implementation — offline price and market regression

**Scope (source + regression tests, pending exact commit CI):** proofinvest/market_reality.py reads bounded UTF-8 JSON (<=131072 bytes) with exact target SEC issuer CIK, as-of, ticker, a declared benchmark (S&P_500/NASDAQ_100/DJIA), explicit return_basis (PRICE_ONLY_CLOSE or ADJUSTED_CLOSE_TOTAL_RETURN_PROXY), and two matching lists of 31..501 ordered weekdays with strictly positive decimal prices (<=7 calendar-day gaps). Two separate source objects require vendor URL, SHA, publication date <= analysis as-of and >= final price observation. All source meta remain **UNAUTHENTICATED**. No web/API or trades.

Compute aligned daily *simple* arithmetic returns, sample OLS beta Cov(stock,benchmark)/Var(benchmark), daily intercept = mean(stock return) minus beta * mean(benchmark return), in-sample R², period compounded security/index returns. Exact Decimal arithmetic before display rounding; zero benchmark variance => no beta/alpha/R²; zero security variance => no R². This is a descriptive one-factor historical regression, not CAPM risk-adjusted alpha, performance attribution, stock valuation or a liquidity/bubble percentage. Do not infer EPS/earnings contribution from alpha. No market beta-to-bubble red card.

Existing localhost KUODRA upload flow provides optional Engine A source input. After the user-approved Guard review of the existing SEC triplet (no market influence on Guard), the regression can bind separately to the *same* issuer/as-of SEC 10-K revenue-growth report (filed-before-as-of, source SHA), generating user-readable context and HTML/JSON reports; market result is **not included in the existing Guard audit chain**. No persistent new market data. No direct provider authorization, real vintage/rights validation, independent SEC provenance or live price feed is claimed.

Two compared options: (A) offline Decimal OLS + source/date inputs + optional SEC context, **chosen** for zero provider costs and reproducibility with typed checks; (B) call paid market analytics vendor + LLM to label speculative "bubble %" or future target, rejected for data licensing/provider cost/model error, causal overclaim and live API authorization requirements.

Priority after P44: lawful time-as-of stock/index histories and genuine SEC filings, 3-engine report coherence with guard only after owner approvals, independent risk/valuation factors and factor-model diagnostics. Honest missing/conflicting data continues to withhold output. Existing Nov12 PDF-only preliminary approval stays frozen.

# KUODRA — Three-Engine Final Architecture / P43 Development Contract
Date: 2026-10-31 KST. Owner approved development of the full three-engine research system. Design lock is NOT a claim that every engine, AI feature, production site or live-data case is implemented.

## Mission / business problem
Evidence-grounded investment research distinguishing (A) market pricing versus company fundamentals, (B) earnings quality and accounting discrepancies, and (C) industry growth and future opportunity hypotheses. Existing SEC/Disclosure Lightning, Decimal verification, source bytes SHA, Guard HOLD/REJECT, explicit human consent and audit remain authoritative. Source authentication, financial arithmetic, model inference and investment execution are different trust domains.

## Definitive data and control flow
User issuer/date/intent → Research + lawful SEC/market/industry data with publication timestamps → source/issuer/period/license gate → deterministic Decimal SEC verification → independent A/B/C analysis modules → evidence-linked human-readable explanation → existing Guard + human review (NO automatic trading authority) → explicitly approved audit retention → Streamlit dashboard/JSON/HTML.
Every evidence claim has status, timestamp/period, units, underlying SEC accession or typed series ID, source digest, and uncertainty. Never turn a missing fact into zero.

## Engine A (future, separately test-gated)
Compute issuer/index returns with declared price-versus-total-return convention; beta = covariance of aligned returns / variance of benchmark returns, intercept/alpha conditional on the model, sample count/holding period/market selection and robust baseline. Compare observed financial growth and valuation separately. Alpha is NOT a causal share of fundamentals and beta is NOT the percentage of a price move caused by liquidity. A signal may request review of market exposure/valuation but NEVER declare objectively measured bubble percentages or trading profit.

## Engine B (P43 implementation slice)
Existing annual companyfacts parser and cashflow/balance readers are reused. A new read-only accounting_integrity module reads one issuer CIK, one 10-K accession, two consecutive fiscal ends, as-of date and bounded CompanyFacts bytes. Exact same accession, period, filing date and currency controls apply.
- NetIncomeLoss vs NetCashProvidedByUsedInOperatingActivities: net income less operating cash flow, CFO/net-income percentage ONLY if net income positive, descriptive review signal for positive earnings with negative CFO or CFO below positive earnings.
- Optional OperatingIncomeLoss is displayed if same annual period and filing date.
- Annual issuer revenue comparison uses existing strict single-concept US-GAAP revenue verifier.
- If two same-accession instant assets are disclosed in the same selected filing: AccountsReceivableNetCurrent and InventoryNet year-over-year percentage change, and each change minus same-period revenue growth in percentage points. The 10pp review threshold is a *heuristic* for a review card, not a calibrated probability, legal fraud diagnosis, or causal inference.
- Missing, future, ambiguous, mixed-currency, mixed-filing or zero prior-balance facts are UNAVAILABLE/PARTIAL_OR_CONFLICT, never healthy.
- Independent of Guard: source_authenticated=false, accounting_fraud_proven=false, guard_policy_modified=false, ai_generated=false, trade_executed=false. File SHA and input metadata are local byte integrity, not provenance authentication.
- P43 also removes an obsolete issuer==EDGAR-submitter-accession-prefix assumption in existing cashflow and balance side panels, keeping strict issuer CompanyFacts matching and exact accession row checks.
- Report integration is supplementary: local_sec_guard_report returns a linked accounting_integrity card without changing existing Guard evidence or SQLite audit semantics; local_sec_html_report escapes and verifies the card's CompanyFacts hash before display; localhost UI shows plain-language labeled numbers.

## Engine C (P42 basic kernel already tested; real-data stage future)
Issuer annual growth vs 0–8 comparable peers and relevant industry output/demand/growth series; sector label, geography, period and release vintage with source ID and license gate. Industry macro series and issuer revenue have different populations and cannot be conflated into market share or TAM. Up to three source-linked opportunity/threat hypotheses; future base/upside/downside scenarios must be conditional on explicit assumptions and evidence, never guaranteed CAGR or stock performance. P42 is user-supplied offline input, not a live feed.

## Interoperability, cost and alternatives
Option 1 (selected): reuse verified Python/Decimal/SQLite with separately test-gated engines, no new servers, optional grounded AI narration after source validation. Low infra cost and bounded failures.
Option 2 (rejected initially): new separate FastAPI/AutoML/LLM agents generating predictions via broad market scraping; higher API/rights costs, hallucinations, false certainty and unnecessary coordination.
Actual AI/ML evaluation and API access require source/license permission, point-in-time vintage and independent performance tests. Retain existing P41 offline ML explanation as an unverified input contract, never proof of fitted model. No data, token, environment or private official materials may be committed.

## Acceptance and priority
1. P43: synthetic no-network Engine B math and negative tests; full Python, Windows SQLite and real Chromium regressions at exact GitHub SHA, plus Guard and HTML source hash invariants.
2. Real lawful SEC issuer triplet and two comparable period filings, with consented provider requests or owner-provided lawful originals; verify issuer/submitter, restatements and note evidence.
3. Engine A robust market series alignment/model uncertainty and defensive UI, independent of policy Guard.
4. Real-data Engine C comparisons of one issuer plus two relevant peers and a lawfully obtained dated industry series; then verified conditional narratives.
5. Optional ML models and evidence-checked LLM description; measured holdout metrics and robust failure/no-train behavior; browser and Production security QA.
6. Separate Nov 12, 2026 10:00 KST official <=10-page preliminary PDF authorization and DAKER submission; do not edit protected original or infer submitted status from CI. Finalist deliverables and public deployment separate later approval.

No financial crime claims, definitive market-bubble conclusions, unverified investment advice, automated trades, or assertions that synthetic QA proves real-data quality.
