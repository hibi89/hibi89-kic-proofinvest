# KIC — Streamlit issuer/manual scenario and isolated synthetic recovery QA

## Result (2026-10-24 KST)
- `streamlit_app.py` has two explicitly labelled modes in the full `lead/kic` repository: preexisting synthetic fixture (default; stored/read-only support preserved), and Samsung FY2024/FY2023 **previously manually reviewed** consolidated revenue claim check.
- Manual mode choices: 16.20% matching manual numeric evidence; 30% conflict; missing claim unavailable. Data provenance, source URL, 2025-02-18 issuer posting date, no independent DART/authenticated API, and source rights not established are visible. Risk is **withheld**, not zero/safe. No upload, secrets, live calls, LLM/Agent, or investment advice.
- Full repository: `python -m pip install -r requirements-ui.txt` then `python -m streamlit run streamlit_app.py` and select '삼성전자 공개 재무제표 수동검산 (2024/2023)' via '자료 유형'. The browser UI has not been visually reviewed in this session; coverage is Streamlit AppTest headless.

## Preserve SYNTHETIC-ONLY public recovery
- The standalone archive is deliberately synthetic-only; it does **not** contain `docs/evidence/samsung_2024_cfs_revenue.json`, manual-case modules or other issuer records.
- A first implementation imported issuer-only modules at app startup, which would prevent synthetic-only restored ZIP apps from starting. Fix: import manual module only inside manual branch and show that branch only if the pinned evidence file exists beside the full repository app. The restoration branch presents only the synthetic option.
- Added independent regression in `tests/test_synthetic_demo_bundle.py`: build allowlisted ZIP, extract into **fresh directory**, start restored UI via separate Python subprocess using `streamlit.testing.v1.AppTest`; verify no exception, synthetic-only selector, and synthetic warning. This was executed in GitHub CI; browser/production hosting is still untested.

## Test evidence and repair history
- `tests/test_manual_issuer_streamlit.py`: six new UI tests for unchanged default synthetic radio, matching claim, mismatch, missing claim, provenance, risk not calculated and issuer IR link.
- Initial code SHA `6b7e565a39c9a060dc91b72edbca4e02efd2308a`, GitHub CI #40098886772 **FAILED**, five UI checks caused by `KeyError: report_year` (wrong result contract). It did not modify any secret or real dataset.
- Fixed to `verification['fiscal_year']` in SHA `df680334f88edd4858289d7cd235a73097e3f9fc`; GitHub CI #40098958804 **195/195 PASS**.
- Final safe-recovery code SHA `dbf180bb2034ebc04ccaba8c5275ea66b6d33947`: [GitHub Actions #40099102467](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40099102467) **COMPLETED/SUCCESS, 196/196 PASS**, including newly restored-UI regression, master ledger consistency, synthetic snapshot read/save and ZIP restoration. No actual UI browser review or real source authentication.
- Code rollback baseline prior to this unit: `2c5d162401aab20a0f9032ceecbca55fabaa8479` (regular Git revert if necessary). No force push.

## Extra, noncanonical 100-point completion meter
| Checkpoint | Weight | Earned |
|---|---:|---:|
| Screen/CLI source boundaries and restore compatibility design | 20 | 20 |
| Two scenario branches with explicit source labels and safe restoration | 35 | 35 |
| Six new UI + one recovery test / GitHub 196 pass | 30 | 30 |
| QA, operational usage and cross-chat handoff | 15 | 15 |
| **Additional task** | **100** | **100** |

**Remaining for this extra UI task:** base 0h + reserve 0h, actual execution time unmeasured. This is NOT 2026-12-15 `FINALIST_ONLY` production UI completion, not an official DAKER submission, and not a verified deployed site. The ledger remains 29 DONE / 3 BLOCKED / 28 NOT_STARTED, next date 2026-12-03 official result (future).

## Remaining P0/P1 external gates
- DAKER user participant/team-leader final PDF upload authority: 2026-10-25 60/100 BLOCKED; 2026-11-09 60/100 BLOCKED. Mobile/current chat lacks originating Browser context to inspect authenticated page. Account verification and final submission require separate participant action and explicit approval.
- DART exact filing direct-viewer check: 2026-10-30 90/100 BLOCKED, historical HTTP 502; issuer PDF and prior manual transcription do NOT close the DART filing accession test.
- 2026-11-10 intended early DAKER final submission NOT_STARTED; official 2026-11-12 10:00 KST deadline. Frozen private 10-page PDF/PPTX and six private Library backups remain unchanged and unpublished. No AI Agent, live OpenDART API, cloud deployment, or real E2E tested.
- User local execution not required for this work; optional local Streamlit launch only if they want to see the UI. No background automation.
