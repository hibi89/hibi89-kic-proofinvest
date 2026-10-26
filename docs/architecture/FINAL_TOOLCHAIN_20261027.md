# KIC ProofInvest Global — FIXED REAL-WORLD TOOLCHAIN
2026-10-27 owner correction: exact software/SDK/API/DB/deployment tools, not generic categories. This document LOCKS selection, not installed/verified implementation. User's latest submission freeze prevails: Nov12 prelim ONLY organizer PDF, finalist Dec22 actual app if selected.

## A. Until Nov12 preliminary
| Area | Exact chosen program/tool | State |
| --- | --- | --- |
| Submission editing | Existing organizer slide/PDF original in its native editor, export to PDF; Python 3 + pypdf for count/header, local visual render inspection | Only signed-off exact PDF, <=10 pages and 7 organizer sections. Do not overwrite private candidate |
| Demonstrable prior prototype | Existing Python 3 proofinvest Research/Verification/Risk, Decimal / datetime / hashlib / JSON standard library | Offline prototype only; no SEC data claimed |
| Optional demonstration | Existing Streamlit streamlit_app.py | Optional, cannot delay PDF |
| Data source described | SEC EDGAR public data.sec.gov (Submissions, XBRL Company Facts) plus original official filing URLs | Actual source only when verified; otherwise clearly proposed |
| Development management | GitHub existing lead/kic + GitHub Actions + Python unittest | Existing CI not proof of real APIs |

## B. Only if Dec03 finalist: exact full MVP stack
| Layer | FINALIST tool selected | Job and verification |
| --- | --- | --- |
| Language | Python 3.11+ in venv, pip with compatibility-tested pinned requirements.txt | Reuse existing code, no React/TypeScript rewrite |
| SEC HTTP source | requests with official SEC EDGAR REST Submissions and Company Facts endpoints and original archive | SEC descriptive User-Agent, source ID/CIK/accession, fair access bounded requests, retries/caching; no SEC filer submission API |
| Text extraction | BeautifulSoup4 for SEC HTML and pypdf for approved searchable PDFs | Preserve original text spans and SHA256 |
| Normalize/compute | Python dataclasses, Decimal, datetime, pandas + numpy; pydantic only if strict adapter validation needed | Fiscal basis and currency/scale/period alignment; source-linked UNKNOWN if inconsistent |
| Local storage | sqlite3 (SQLite) + immutable raw file/JSON manifest + SHA256 + optional SQLite FTS5 | One local source/analysis ledger, no DBVORA dependency |
| Quantitative ML | scikit-learn with Dummy baseline then HistGradientBoosting/RandomForest ONLY on credible labelled issuer-time panel | Group/time holdout, leakage guard; otherwise NO_TRAIN. AI_AutoML_Analyst profiling ideas can be adapted only after provenance and licensing review |
| Deep-learning document retrieval | PyTorch CPU + sentence-transformers, model sentence-transformers/all-MiniLM-L6-v2 (Apache-2.0 model card; check exact weight revision/license when implemented) | Semantic similarity to retrieve English filing paragraphs; report source spans; never claim embedding alone equals validated finance extraction |
| Deep-learning evaluation | Manually reviewed small source-span labels and precision/recall; deterministic support/contradiction checks | No new foundation model training; no invented model accuracy |
| Visual app | Existing Streamlit + dataframe/charts | One global issuer search→verified facts→risk evidence→report, accessible locally |
| Final hosted URL | Streamlit Community Cloud using the existing authorized GitHub repo **IF verified and approved**, fallback candidate to be selected only if this fails | Must supply actual judge-accessible deployment URL for KIC finals, secure secrets, model CPU/memory cold start and browser test |
| QA and delivery | Python unittest, GitHub Actions, PDF original organizer template, pinned artifact hashes | KIC final URL + code + presentation PDF by Dec22; actual source proof beyond synthetic tests |

Important model license: ProsusAI/finbert model weights are CC BY-NC-SA 4.0 and not selected as a default commercial-compatible dependency; financial sentiment also does not establish deal due-diligence fact validity. Model used above must be evaluated on actual English financial filings.

## C. Registered add-on: Disclosure Lightning
KIC blueprint link: [Disclosure Lightning module](DISCLOSURE_LIGHTNING_INTERFACE_20261027.md).
Origin: PRIVATE hibi89/Bid_Owl, feature/disclosure-lightning. Intended responsibility = lightning-fast **authorized official public disclosure search/fetch + incremental sync + amended version tracking + raw evidence provenance** (CIK/accession/filing ID, source URL, collected_at, SHA256), NOT investment scoring. Current state DESIGN-ONLY, no implementation or repo rename. Proposed eventual tools **Python requests + SEC data.sec.gov + SQLite + hashlib**, contract RawFilingEnvelopeV1 and immutable references. No need for Lightning code or import for prelim PDF; KIC finalist can use directly validated SEC ingestion if Lightning isn't ready.

## D. Preprocessor still UNRESOLVED, not a dependency
Owner will check whether SMAX has actual preprocessing capability or build an independent component. No currently verified SMAX API/adapter. Do not start new project, assume present, or make deadlines depend on it. If later verified, normalized fact JSON with evidence spans, time/unit/currency validation connects Lightning to ProofInvest; else use narrowly scoped standard Python parsing only.

## E. Explicitly out
n8n, AX_FLOW, React/Next.js, new FastAPI microservices, PostgreSQL, Qdrant/FAISS service, full RAG_STUDIO runtime, private Bid Owl source code copying into public KIC, unapproved paid models, private KIC institutional data, deep learning re-training before prelim. Any dependencies may change ONLY for proven breakage; do not expand architecture.

References: https://www.sec.gov/search-filings/edgar-application-programming-interfaces ; https://docs.streamlit.io/deploy/streamlit-community-cloud ; https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 .
