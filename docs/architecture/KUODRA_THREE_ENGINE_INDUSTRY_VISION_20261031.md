# KUODRA — Three-Engine Industry Vision (P42)
Date: 2026-10-31 KST.

## Scope and truthful current state
Owner requests a third independent engine that compares the selected issuer's growth against peers and market/industry growth, then explains that market's vision, opportunities and risks. The previous two proposed engines remain: A Market Reality (alpha/beta and valuation), B Financial Integrity (SEC cash conversion and accounting signals). A/B are design scope, **not claimed fully implemented**. P42 implements only a bounded read-only input comparison of user-supplied historical data; real market ingestion, Gemini outlook, ML forecasts, authenticated provenance, scenarios and Production are NOT yet verified or implemented. Keep Nov 12 preliminary PDF-only scope and original submission file frozen.

## Options and selection
Option A: Generative model directly answers industry vision from broad search. Low initial engineering cost but higher provider expense, copyright/rights and hallucination risk; reject as first stage.
Option B (selected): Decimal-based, release-date/source-ID-bound industry and peer comparison, followed by strictly source-grounded optional AI narrative. Small Python-only offline implementation, low provider cost and testable comparisons; preserve existing SEC/Guard path.
Option C: Multi-issuer ML forecasting of sector TAM, company share and market winners. High data, rights, regime-shift and temporal-leakage risk; defer until independent evidence supports validation.

## Intended complete data flow
User issuer/date/industry request -> issuer-specific SEC original and comparable peer filings -> original and time-based validation -> Engine A (market exposure and valuations) + Engine B (earnings quality) + Engine C (industry growth and relative company performance) -> Evidence-grounded explanation -> existing Guard/Human Review -> approved audit/evidence -> dashboard report.

Engine C detects: company revenue growth vs selected peers, relative change vs relevant industry-wide production/sales/output, structural industry tailwind/headwind **hypotheses** tied to issuer evidence. It does NOT mathematically prove liquidity causes share-price movement, accounting fraud, future share return, or company market share.

## P42 input and result contract
Python module proofinvest/industry_vision.py and opt-in existing localhost-only UI proofinvest/industry_vision_ui.py; JSON schema kuodra.industry-vision.v1. No external requests or model training.

Strict 65,536-byte bounded UTF-8 JSON:
- issuer_cik, as_of, industry, prior_period_end, current_period_end (one annual 330-380 day period; current <= research as-of).
- target and up to 8 peers: name, issuer CIK, prior_revenue_usd, current_revenue_usd (nonnegative decimal strings), prior_source_id, current_source_id. No duplicate CIKs.
- industry_series: name, kind one of REAL_GROSS_OUTPUT/NOMINAL_INDUSTRY_SALES/PRODUCTION_INDEX/DEMAND_INDEX, unit, prior_value, current_value, prior/current source IDs.
- up to 3 user-supplied vision drivers: label, OPPORTUNITY/RISK/MIXED and existing source ID references.
- 2–24 sources: unique ID, HTTPS URL without credentials/query/fragment, publication date <= as-of, SHA256 (syntax only).

Compute annual YoY as 100 times (current minus prior) divided by prior, using Decimal. Never silently divide by zero. Display target and peer revenue growth, peer median growth, industry **indicator** growth, issuer-minus-industry and issuer-minus-peer-median gaps in percentage points. Industry gross output or an index is not the same measure as an issuer's revenue; comparisons are growth context only and cannot establish market share. Accounting definitions, reporting dates, currencies, geographic coverage and revisions must be matched before claiming comparable real economics.

The explanation only describes operator-provided observations and hypotheses. Every return is source_authenticated=false, industry_outlook_verified=false, ai_generated=false, trade_signal=false, guard_decision_changed=false. No Guard policy change; all calculations are unverified until raw inputs and releases are actually authenticated. A future LLM must consume a typed evidence bundle and undergo deterministic claim validation before being allowed to explain opportunities, risks, and base/upside/downside scenarios.

## Candidate source methods (not called)
SEC CompanyFacts XBRL standard-tag issuer facts and submissions for company revenue/financial context; per-filing definitions, fiscal periods, amendments and filings availability are essential. BEA industry gross output / industry GDP for a U.S. sector benchmark and Census industry production/orders for specific sectors, after source rights and release vintage review. Existing KUODRA 11 common macro candidates remain optional/relevance selected, not an 11-API mandatory build. No broad unlicensed scraping and no automatic conclusion that the market will grow.

## Acceptance gates
P42: file source/CI prove strict schema, exact date/CIK/ID, zero denominator, source release, out-of-range and unsafe URLs rejected, no network, no persistent audit or false source trust; localhost optional UI displays input comparisons.
Genuine industry vision: lawful real SEC issuer and at least two relevant peer disclosures, plus licensed sector index and authentic release timestamps, normalization, gap/limitation visibility and source citation from report to original. Real-world E2E and user-specified data rights are still pending separate approval.
AI/ML: point-in-time walk-forward baseline and explainable source-tethered scenarios, reject causal/price predictions; Gemini/data provider usage requires separate approval. Existing core SEC Decimal/Guard, privacy controls and original contest submission files remain untouched.
