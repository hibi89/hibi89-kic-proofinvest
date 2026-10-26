# ProofInvest Global — FINAL PRODUCT DIRECTION / DATA AND ML-DL SCOPE
Decision date: 2026-10-27 KST. Owner-authorized **design lock**, NOT implementation, data ingestion, trained models, submission, or permission to edit private organizer PDF.
Precedence: This latest KIC product *finalist* scope is read with [2026-10-27 submission freeze](../../SUBMISSION_SCOPE_FREEZE_20261027.md). **2026-11-12 10:00 KST preliminary is PDF ONLY (official <=10 pages, 7 sections); no new source/API/train/deploy dependency before that.** PayPal and UGREEN unaffected.

## Final user value
User chooses a US/global listed-company issuer and as-of date; ProofInvest produces an investment **research/due-diligence** report with evidence-linked SEC filing facts, capital changes and major-shareholder disclosures, a tightly capped market/inflation history comparison, held-out historical ML findings **only if validated**, DL-assisted source passage retrieval, and explicit gaps/uncertainty. No investment order, trading or guaranteed prediction.

## Fixed inputs — strict ceiling, no additional external macro feeds
**Existing core kept**: SEC public issuer filings (e.g. 10-K/10-Q/8-K, relevant ownership disclosures, accession/CIK/source URL/date), annual/quarterly finances, share count / issuance / potential dilution and significant-shareholder changes where actual public filing coverage supports them; do not fabricate ownership frequencies or 100% investor coverage.

**Stock-market context (exactly THREE named U.S. indices)**:
1. S&P 500 (official index; vendor-specific symbol e.g. ^GSPC); IVV/SPY/VOO are fund price/total-return PROXIES, not automatically identical to index returns.
2. Nasdaq-100 (official index; provider-specific NDX); QQQ is a tracking ETF proxy and is not a NASDAQ Composite index.
3. Dow Jones Industrial Average (30-member price-weighted index; provider-specific DJIA ticker).
Record source and license, total-vs-price return/dividends, data frequency and original available-at timestamps. No new sector indices/extra equities as *system-wide benchmarks*.

**Inflation context (exactly FOUR monthly all-items YEAR-OVER-YEAR series)**:
1. United States: nationwide CPI-U, all items, 12-month percentage change. Primary source US BLS https://www.bls.gov/cpi/ .
2. China: national headline consumer CPI, 12-month percentage change. Primary source NBS https://www.stats.gov.cn/english/Statisticaldata/MonthlyData/ .
3. Euro AREA (aggregate economic region, NOT a country): all-items HICP, annual percentage change. Eurostat latest prc_hicp_minr https://ec.europa.eu/eurostat/databrowser/product/view/prc_hicp_minr .
4. Japan: national all-items CPI, 12-month percentage change. Statistics Bureau https://www.stat.go.jp/english/data/cpi/ .
IMF national CPI https://data.imf.org/Datasets/CPI may be a secondary standardized cross-check. Historical data access/terms, base-year revisions, first-publication *release timestamp*, vintages, seasonality and data freshness require verification **before implementation**. Compare inflation RATES, not absolute cross-country index levels; do not synthesize missing values. Align release dates so a model only sees data publicly known at the research as-of date; do not use later revisions as historical contemporaneous facts. Map which geographies are relevant to a given company only when filings provide geographic exposure; otherwise label as economy-wide context, not confirmed firm-specific exposure.

**Explicit final exclusions**: NO new interest-rate feeds, multi-country FX, gold/silver/copper/rare-earth commodities, other proprietary/trendy price or sector indexes, additional countries, automated ETF baskets. **Big Mac index not included**: it is mainly a PPP/currency-comparison illustration and historical Economist updates are not suitable as a substitute for monthly national inflation. Economist open data https://github.com/TheEconomist/big-mac-data are not a newly selected runtime feed. **Truflation not included**: licensed historical/API access may entail paid tiers https://truflation.com/pricing . No extra crawling or paid subscription approved.

## Machine learning — CONDITIONAL and test-gated
- Compare selected historical issuer outcomes and issuer-appropriate macro/market inputs, with predetermined forecast horizon or descriptive correlation objective. NO claim these demonstrate causation or profitable trading.
- Start with deterministic descriptive change/comparison, Dummy and simple statistical/regression baselines; sklearn models only if provenance-verified training labels, enough truly independent observations, and meaningful out-of-sample advantage. Small single-issuer quarterly dataset (~40 points/10 years) is NOT sufficient justification for sophisticated ML.
- Use walk-forward temporal split, company/group leakage control, publication-date lag (SEC filings and CPI vintages), survivorship bias checks, adjusted return conventions, regime shifts and uncertainty intervals. Define evaluation metrics before training. If unavailable or no gain: `NO_TRAIN` / `INSUFFICIENT_EVIDENCE`, publish explanatory charts only.
- Do NOT use a deep neural network to forecast share prices from 7 aggregate macro indices or claim future alpha.

## Deep learning — preferred narrow, measurable use
- Selected pretrained licensed English text encoder `sentence-transformers/all-MiniLM-L6-v2` on CPU with source-preserving retrieval for 10-K/10-Q/etc passages; check model revision/license. No big-model training or fine-tune before prelim. Optional filing-version semantic change candidates / risk-related passage candidates; never automatically certify risk or compute finance facts from similarity.
- Compare against literal keyword/BM25 baseline on human-reviewed passage queries: Recall@k, source-span citation accuracy, false positive/unsupported claim rate, runtime/memory. A DL feature ships only if source-grounded quality is measured and no security/operating regression. Otherwise retain simpler rule-based/keyword approach.
- Formulae, ownership, share counts, units, restatements and issuance arithmetic stay in deterministic ProofInvest Verification → Risk engine. Generative prose must carry source date/URL/segment and distinguish observed fact, calculation, model hypothesis and UNKNOWN.

## Preferred design versus rejected alternative
**A (SELECTED, free-first modular)**: Existing ProofInvest Python/SEC validation + exactly 3 benchmarks/4 public CPI-HICP monthly series + optional sklearn with leak-safe measured gains + licensed pretrained MiniLM filing retrieval. Costs: no new paid data, minimal infra, auditable; quality: grounded and reproducible; maintenance: controlled 7 external series.
**B (REJECTED)**: Big Mac/real-time proprietary index, expanded macro/FX/metal feeds and full neural price prediction. Costs/licensing/coverage uncertain; high overfit and attribution risks; submission complexity grows. No implementation.

## Architecture (finalist only)
Official SEC/public issuer filing raw + evidence versioning (Disclosure Lightning interface OPTIONAL after independent verification)
  → optional verified SMAX preprocessing adapter; else narrow Python validated parser
  → financial/ownership deterministic verification
  + exactly 3 index series and 4 all-items inflation YoY series (lawful source/release metadata)
  → point-in-time align and missing/quality gate
  → simple comparisons and conditional sklearn baseline-tested ML
  + licensed pretrained semantic filing text retrieval with citation quality check
  → Streamlit report: key issuer facts, ownership/capital changes, seven series context, tested historical association or NO_TRAIN, filing quotes with source-span and unknowns.
Keep public contest repo licensing/IP guards; no private Bid Owl/SMAX source copies without authorization.

## Acceptance and schedule
**Prelim due Nov 12 10:00 KST**: only exact user-approved official PDF, seven required sections and <=10 pages. Briefly state finalist features as roadmap, NOT delivered implementations; do not edit frozen original. Retrieve official DAKER receipt after user-authorized submit.
**If Dec 03 finalist**: prioritize one real SEC issuer, cited report and deterministic risk; add 3 indexes/4 inflation series only after data licenses & as-of checks, ML only if baselines/out-of-sample clear, DL only if evaluated retrieval improves. **Final due Dec 22 10:00 KST**: working judge URL, repo, PDF and browser/API verification, contingent on approval/rights.
**Current truth**: documentation architecture only. No price/CPI integrations, no valid issuer-index ML test, no DL retrieval benchmark, no finalist code or release proved by this document. Preserve original source and artifacts. Any further dataset scope extension requires a NEW explicit owner decision; no automatic growth.
