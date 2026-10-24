# KIC Samsung issuer manual evidence CLI — 2026-10-24

## Outcome and user-facing command
New executable command: `python -m proofinvest.manual_case_demo` (default claimed revenue growth 16.20%). Alternative `python -m proofinvest.manual_case_demo --claim 30` deliberately returns Verification `conflict`. Both continue to withhold Risk when issuer liabilities/equity are absent. No OpenDART key, external API, AI model, new PDF, account access, or extra packages are required beyond this repo's existing Python implementation.

## Evidence and limitations
- Pinned existing issuer financial record: `docs/evidence/samsung_2024_cfs_revenue.json`, manual 2024/2023 consolidated revenue amounts 300,870,903 / 258,935,494 KRW millions and +16.20% Decimal-derived growth; these were manually checked in an earlier QA session, not reverified from actual PDF during CLI execution.
- Official issuer IR 2024 consolidated statements publication page, 2025-02-18: https://www.samsung.com/global/ir/reports-disclosures/public-disclosure-view.84315/ . The posted PDF link exactly matches the existing manual-evidence record. This date is distinct from Samsung's separate 2024 Business Report listing dated 2025-04-30.
- Program source `proofinvest/manual_case_demo.py` derives one issuer citation linking Research to manual Verification and intentionally passes NO invented Risk liabilities/equity. Research source rights remain `not_verified`/`not_established`. External source authenticated=false, DART viewer checked in this execution=false, AI Agent executed=false, live API called=false, latest fiscal year claimed=false.
- The `verified` claim label only means arithmetic agreement against a manually transcribed previously reviewed statement, NOT freshly authenticated report bytes. Real OpenDART API, independent DART viewer check and real Risk input are still untested/blocked.

## Decision and QA
- Rejected: fabricate a full-company Risk figure to make all three modules show calculations; risk score would have no financial statement basis.
- Chosen: reproducible one-command historical issuer demonstration with honest Risk withholding and official source provenance.
- New `tests/test_manual_case_demo.py`: 7 cases (matching claim, conflict, invalid claim, no falsely authenticated/live assertions, official issuer page/rights, tampered source/issuer/year fail closed, subprocess CLI both claims).
- Code commit `a630451473eb34bf32dd4e827bae09f2f70f61dc` on lead/kic. GitHub Actions https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40096891638 completed SUCCESS, 189/189 tests PASS including 7 new tests, master progress sync and synthetic demos also pass.
- Program has no browser-access or PDF-page-count check; prior private 10-page frozen KIC submission candidate and 6 Library files untouched; never publish them in public GitHub.

## Daily gate, schedule and continuation
| Standalone executable-demo gate | Points | Earned |
|---|---:|---:|
| Official issuer date/earlier evidence contract and alternative review | 20 | 20 |
| Historical issuer one-command executable with fail-closed unsupported Risk | 35 | 35 |
| New 7 tests and 189-test GitHub CI | 30 | 30 |
| QA and handoff documentation | 15 | 15 |
| **Additional standalone task** | **100** | **100** |

Remaining for this extra task: base 0h + contingency 0h (not an estimate of external blockers); actual work time unmeasured. Does NOT complete the official 2026-12-14 finalist-only real-source SQLite/Web/Agent E2E task. 60-day schedule: 29 DONE / 3 BLOCKED / 28 NOT_STARTED; next 2026-12-03 WAIT_OFFICIAL_RESULT (future).
DAKER authenticated participant/team leader and PDF-upload authority 10/25 + 11/09 remain 60/100 BLOCKED; DART filing viewer 10/30 remains 90/100 BLOCKED; actual final submission 11/10 NOT_STARTED. Official deadline 11/12 10:00 KST, intended early submission 11/10, subject to participant authentication/explicit approval and receipt verification.
Previous code HEAD before CLI: d61a146d4b521f5a38342b1d9fa8f12b781239ee. Rollback by normal Git revert if needed. New documentation commit follows the successful code run; verify separately.
