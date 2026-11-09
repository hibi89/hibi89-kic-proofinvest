# P296–P297 KUODRA Hybrid + Local Document Backend — 2026-11-09 KST

## Change / decision
- Added `proofinvest/kuodra_hybrid.py`: owner-scoped PUBLIC + PRIVATE *local* join on exact issuer ID and observation time, with both-dataset ACL checks, source and release validation, separate public/private metric namespaces, bounded derived in-memory dataset, optional existing FDR or CV-selected time regression, and PRIVATE/HOLD result-only response. No public export path.
- Added `proofinvest/kuodra_document_ingest.py`: bounded, machine-readable PDF **pipe-delimited canonical text lines** or DOCX **single six-column canonical table** -> existing canonical numeric long schema. Original document byte SHA-256 and PDF page/line or DOCX table/row source spans tracked. No OCR, LLM, macro execution, network, disk persistence, or blind narrative numeric inference. PDF/DOCX libraries remain optional; invalid/oversized/embedded/external-linked inputs denied.
- Added `tests/test_kuodra_hybrid.py` (15 tests) and `tests/test_kuodra_document_ingest.py` (11 tests), including DOCX -> private ingest -> public CSV join -> FDR analysis; previously existing 37 tests preserved. No changes to old SEC A/B/C, source fixtures, frozen PDFs or old model logic.

## Actual tests
- Local Python 3.13.5: `cd /mnt/data/kic_patch && python -m unittest discover -s tests -p 'test_kuodra*.py' -q` => **63/63 PASS**; `python -m compileall -q proofinvest tests` => PASS.
- First document test expected PDF source line 2, actual extracted PDF includes an intervening blank line: text line 3. Corrected *test expectation* to actual line location; no production source altered by this test mismatch. Follow-up 63/63 PASS.
- Hybrid negative controls: unauthenticated and unauthorized subject, cross-tenant, dataset ID enumeration, wrong source zone, edited source ID, public future-only feature, no joined observations, insufficient paired issuer count, duplicate metric namespaces, multi-issuer ML NO_TRAIN, no socket.connect calls, and external public export denied.
- Document negative controls: oversized/malformed PDF/DOCX, private missing consent, injected text outside canonical rows, duplicate measurement, Excel-formula-like value, cross-tenant role, mocked network egress. Generated synthetic bytes only.
- Git blob read-back matches exact local `git hash-object` for 4 new files (checked at source/test commits); latest code predecessor HEAD `6cb9f0016401a3aa6e56561e9586e65d3532f0e9`.
- GitHub Actions full Python 3.11 repository test suite and real browser/production **NOT VERIFIED**. GitHub combined statuses `[]`, commit workflow lookup `[]` (PR-only API); absence is not a CI failure or success.

## Security / validity caveats
- Gateway's `authenticated_by_host` comes from trusted caller contract, NOT real identity provider or token verifier. Host firewall/isolated sandbox and no-egress policy not provisioned.
- Local Python `socket.connect` monkeypatch verifies tested code path only, NOT OS-level egress. Libraries (PDF/DOCX/SQLite) must run in an isolated worker before handling arbitrary untrusted or confidential documents.
- Join does NOT silently impute values, cross-map differing issuer IDs, convert units, or send private-derived inputs to public providers. Same observation/time IDs are required; historical predictive features use existing `available_at <= observation_at` rule and label embargo. Dataset SHA is local byte lineage, **not** issuer authentication or rights clearance.
- Cross-sectional FDR uses exploratory Pearson/BH; independence not verified, correlation is not causality, no released-financial predictive uplift or calibrated probability certified. Guard HOLD; no investment recommendation.
- Input PDF/DOCX parser is intentionally strict; it does not handle arbitrary layout, scanned PDF or freeform research documents.
- No licensed SEC/NDX market data, real KIC documents, paid API, external model, deployment, owner account actions, or official contest filing touched.

## Progress and next
New estimated 100-point acceptance: SEC/Guard 16/20, schema 9/15, lawful public 4/10, authorized private 7/15, ML/statistics 9/20, security 3/10, report 3/5, real production E2E 0/5 = **51/100**, up from P295 46/100. This is an engineering estimate backed by synthetic tests, not certified production completeness.
Next: local protected worker/real host identity & deny-egress, approve-only hybrid joins, issuer/time/group holdout and negative controls, source-backed private report/UI, full Python3.11 CI. PDF editing specifically **deferred by owner to 2026-11-11**, one day before official 2026-11-12 10:00 KST preliminary deadline; DAKER remains NOT SUBMITTED.
