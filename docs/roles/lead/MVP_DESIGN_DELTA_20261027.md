# KIC MVP 구현 대비 최초 설계 검토 — 2026-10-27 KST

## 적용 범위와 원칙
- Repo `hibi89/hibi89-kic-proofinvest`, branch `lead/kic`, verified source commit `4fa5152fe84fad95ea311af89875aa1362dee949`.
- CI `40488983968` completed/success: `257/257` offline tests PASS; 0 failures. GitHub Actions AppTest is headless test, NOT a deployed browser/Production proof.
- Prelim DAKER due 2026-11-12 10:00 KST: officially formatted <=10-page PDF, seven sections; local application is optional. No public draft PDF added/changed and no official submission.
- Full finalist-oriented architecture: official SEC filings/provenance → capital/finance/ownership checks → conditional descriptive/ML analysis → uncertainty-aware research report. Exactly 3 index + 4 CPI/HICP context series deferred and subject to lawful licensed data; no DBVORA as a contest dependency.

## Implementation vs design
| Component | Source-backed condition | Remaining proof/gap |
|---|---|---|
| Research/source chronology | Implemented offline input metadata chronology and point-in-time rejection | First-party SEC retrieval/issuer original independent confirmation NOT_VERIFIED |
| Verification/revenue | Manual pinned Samsung historical issuer data arithmetic, conflict/unavailable controls | Historical manual transcription ≠ current issuer PDF certification |
| Risk | Verified-input-only ratio gating and withheld missing liabilities/equity | Real source-supported balance sheet absent for issuer demonstration |
| Bounded decision control | `proofinvest/agent_controller.py` PLAN/EVALUATE/DECIDE/REPORT, <=1 local tool | Deterministic rule-based controller only; LLM/actual AI Agent NOT_EXECUTED |
| User-facing MVP | `streamlit_app.py` synthetic and manual modes; new opt-in decision trace when manual case selected | CI AppTest PASS, production HTTP/Chrome visual validation NOT_VERIFIED |
| Reporting | Reproducible offline receipt/synthetic evidence screens | Full overseas SEC due-diligence and downloadable multi-issuer report NOT_BUILT |
| Historical index/inflation | Final 3+4 source list documented | Ingestion/charting NOT_BUILT (finalist phase only) |
| ML and DL | Leakage safe holdout and MiniLM retrieval baseline specified | No SEC dataset/labels/model tests/training or validation; NO_TRAIN |
| KIC preliminary | Frozen candidate PDF referenced privately, upload preflight code | Exact official PDF/title, DAKER final permission, receipt, ELO voting NOT_VERIFIED |

## Engineering option selection
- **A (selected):** add bounded rule decision trace to the existing Streamlit manual-case UI. No fresh dependencies or external requests; retains proven evidence-chain and tests. Fast, low-cost, reversible.
- **B (rejected at this gate):** build new FastAPI/React dashboard or pull AutoML/DBVORA runtime immediately. Higher integration, API/license, security and schedule cost with no official preliminary requirement. Re-evaluate only after finalist decision.
- The UI checkbox invokes the existing pinned manual evidence path locally and validates the controller's safety contract; it cannot certify original DART/SEC publication, execute trades, or substitute real LLM.

## Verified change and safety
- Code: `streamlit_app.py`; tests: `tests/test_manual_issuer_streamlit.py`, 3 new AppTest cases for agreement, contradictory claim and missing claim.
- Code commit `4fa5152fe84fad95ea311af89875aa1362dee949`, CI `https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40488983968`.
- Existing default synthetic view preserved. Extra controller evaluation runs ONLY when explicitly checked in manual mode; static data read-only, no network, no password, no private PDF/Library edits.
- Tests `257/257 PASS`; live API calls `0`, real original source authentication `NOT_VERIFIED`, Production `NOT_DEPLOYED`, DAKER receipt `NONE`.
- Plain Git revert of the code commit is the rollback route; no force push. No independent read of private PDF contents in this cycle.

## Next actions (strict priority)
1. With private organizer PDF accessible and exact user permission: compare existing frozen <=10 page seven-section candidate with official form and current overseas/AI-Agent differentiation brief; do not expose private source on public GitHub.
2. Obtain separate owner approval for exact filename/title/DAKER upload/final submit, then verify official submitted-history/receipt. Never infer approval from code development.
3. If finalist, use existing Streamlit base to add licensed SEC evidence and owned-source traces first; only then test index/CPI histories, leakage-safe ML baseline and optional pretrained filing text retriever. Preserve UNKNOWN instead of fabricated predictions.
4. Final security/stability: real HTTP/visual/accessibility/API/permissions/failed-input checks with trace and complete regression after implementation; no success claims without external proof.

Canonical 60-day plan remains 29 DONE / 3 BLOCKED / 28 NOT_STARTED. This is a **separate out-of-plan UI MVP evidence unit**, not a retroactive increment of the official schedule. Actual engineering duration was not timed.
