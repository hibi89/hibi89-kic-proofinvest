# KIC ProofInvest Global — Final Analytics Reuse and Visual Insight Decision
Date (KST): 2026-10-27. SCOPE: final product design / finalist-only implementation plan. This is NOT proof of completed integration, model training, deployment, or authorized publication.

## User value / evidence-based insight
Intended investor role: raise the **quality of decisions** by surfacing easily missed variables and testing how they appeared alongside issuer financial changes in historical periods. Do **not** claim causal identification, a calibrated chance of profit, future return prediction, statistical validity from cherry-picked correlations, or guaranteed decision success. Every candidate insight must show its observation window, sample size, lag, date-releases, missing coverage, confounder caveat, reproducibility score/held-out measure where applicable, and links back to source evidence. No fake 'confidence percentage' or investment recommendation.

## Reuse decision (comparison of >=2 approaches)
| Dimension | A: Selective code/interface reuse (CHOSEN) | B: Run full AutoML and DBVORA services as dependencies (REJECTED) |
| --- | --- | --- |
| Scope | ProofInvest verifier remains source of truth; reusable sklearn evaluation/visualization patterns adapted into existing Python runtime, existing Streamlit UI and SQLite. DBVORA optional later; no runtime dependency | Separate AutoML FastAPI and DBVORA FastAPI background servers, shared migrations and cross-service auth |
| Development and launch | Fewer deployments and new failure modes; existing KIC report remains stable | More dependencies, port/service orchestration, more public-repo IP concerns |
| Quality | Finance-specific time/group/as-of validation, deterministic source-linked metrics and risk | Generic CSV AutoML may permit leakage/invalid target and DB schema maps do not improve financial insight |
| Cost and maintenance | Free-first, selective tests/license review, no new paid platform | Installation, testing, API, packaging and maintenance complexity rise |
| Prelim gating | No runtime/API changes before Nov12; PDF only | Violates tight prelim prioritization |
Decision: **A**. No new source copied/merged until finalist selection, owner source-license review, compatibility and regression acceptance.

## Inspected reusable assets and limitations
- `hibi89/AI_AutoML_Analyst@feature/kmong-v1`: `backend/app/services/standard_delivery.py` includes baseline comparison charts, train-only CV and holdout labeling in PDF; `chart_design.py` contains five-chart cap, missingness, historical trend and numeric correlation heatmap; product documentation records BASIC/STANDARD/PREMIUM synthetic output and Linux CI tests. This does NOT prove KIC sector/temporal forecast validity; it is a separate product NOT KIC-ready.
- To adapt later: model runners, Dummy baseline, time/group split hooks, evaluation reporting and chart primitives. Require SEC/company-as-of time-window data schema, point-in-time CPI release lag, benchmark price/ETF semantics, licensed data, train-only transforms and walk-forward out-of-sample evaluation.
- **DBVORA@feature/p0-db-map** implements local SQLite schema inventory and diagram/API for DB metadata, not insight analysis. KIC already has local SQLite provenance ledger; DBVORA service/DB map/compression/restore adds needless dependency in contest. **NOT USED for KIC submission.** Consider read-only metadata observer only as future separate product interoperability after competition; never authoritative on company analytics.
- **ProofInvest existing `streamlit_app.py`** is synthetic/manual verification demo, not live market dashboard. Keep it as base, avoid React/Next or additional app server and verify any future deployments for real.

## FINAL investment-insight Streamlit dashboard layout (if finalist)
1. **Issuer header**: company, CIK, as-of date, source coverage indicator, filing vintage and factual verification status.
2. **Most useful overlooked factors**: max 3 evidence-backed candidate insights; grouped into `OBSERVED` / `HYPOTHESIS` / `INSUFFICIENT_EVIDENCE`. Each shows why it matters, affected metrics, historical window/lag, sample size, reference sources and data concerns. Ranking is a user review priority, NOT numeric investment success probability.
3. **Company fundamentals/ownership**: revenue, operating margin, leverage/cash, shares outstanding and significant-holder disclosed changes. Dates, units, numerator/denominator, company filings, missing data and amended filings surfaced. Separate original numeric facts from model inference.
4. **Market benchmark chart**: S&P 500, Nasdaq-100, DJIA shown as 100-based *normalized* comparable time series (or separate percent-return chart), with underlying index/ETF proxy choice disclosed. Avoid raw different-unit axis comparison.
5. **Inflation context chart**: US CPI-U, China headline CPI, euro-area HICP, Japan headline CPI monthly year-over-year change, all in %, with release-vintage labels and country series source links; separate chart from stock indices to prevent scale conflation.
6. **Historical relationships**: selective lag correlation / scatter / small multiples comparing relevant issuer outcome and factor; label `correlation != causation`, number of observations, lags, data availability, confidence intervals where supported, and multiple-comparison selection warnings. Only report robust/appropriate variables, not every pair.
7. **Model check**: actual baseline vs chosen ML performance on strict future-held-out issuer/time data, date range, calibration/uncertainty where relevant, train/test counts. If no eligible data or no gain, show `NO_TRAIN` or `INSUFFICIENT_EVIDENCE` and descriptive charts, never invent model accuracy.
8. **DL filing evidence inspector**: highlighted English 10-K/10-Q source passage, exact document URL/accession/date/span, relevant section and extraction status. Embedding/sentence similarity retrieves candidates; deterministic verifier and human-readable citation resolve claims.
9. **Report export**: downloadable source-backed PDF/HTML/Markdown only once generator and source/right/version parity tested, no extra database service. An explanation is supported only if links survive in exported report.

## Only final fixed data series
**Three equity benchmark series**: S&P 500, Nasdaq-100, DJIA.
**Four monthly national/regional headline inflation YoY series**: US CPI-U, China headline CPI, euro area all-items HICP, Japan CPI.
**Company-specific** SEC filing/financial/capital/significant-shareholder evidence remains a separate primary fact base. No Big Mac, Truflation, broader FX, metal prices, policy rates or new dataset expansion. The dataset itself has not been collected in this architecture phase. Dataset publication rights and actual value/frequency/time-index compatibility will be verified before use.

## ML vs DL boundaries
**ML**: historical relation discovery/evaluation only with meaningful time/group split and baselines (start simple scikit-learn; defer if insufficient records).
**DL**: pretrained licensed `all-MiniLM-L6-v2` for SEC English filing semantic retrieval, evaluated versus keyword/BM25 on hand-labeled source spans; no DL stock prediction.
**Rules**: SEC numerical facts, shares, ownership, arithmetic, units, conflicts and risk statuses validated deterministically; ML cannot rewrite the source of truth.

## Prelim and next
**Nov12 10:00 KST**: organizer's <=10-page, 7-section original PDF *only*, submitted once exact owner-approved and official DAKER receipt retained; report this analytics/dashboard as a conditional finalist roadmap, not a running product.
**Finalist Dec03 → Dec22 10:00 KST**: if selected, KIC lead first proves one authorized issuer/source case, then optional 7 series with date rights, then validated model + filing DL + Streamlit UI, before browser and export QA. Stop if rights/data/external host unreliable. No imported runtime, DBVORA setup, new repo, public source copy, original PDF change, paid services or unauthorized API calls from this document.

## Evidence sources inspected, as of 2026-10-27 KST
- https://github.com/hibi89/AI_AutoML_Analyst/blob/feature/kmong-v1/backend/app/services/standard_delivery.py
- https://github.com/hibi89/AI_AutoML_Analyst/blob/feature/kmong-v1/backend/app/services/chart_design.py
- https://github.com/hibi89/DBVORA/blob/feature/p0-db-map/dbvora/inventory.py
- https://github.com/hibi89/DBVORA/blob/feature/p0-db-map/dbvora/web/index.html
- https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/streamlit_app.py
- https://github.com/hibi89/hibi89-kic-proofinvest/blob/lead/kic/docs/architecture/FINAL_KIC_PRODUCT_DIRECTION_20261027.md
