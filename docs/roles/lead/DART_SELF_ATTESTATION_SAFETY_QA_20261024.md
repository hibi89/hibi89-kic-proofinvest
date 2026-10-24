# KIC — DART JSON self-attestation trust-boundary correction (2026-10-24 21:29 KST)

## Risk identified and corrected
The existing offline-only `proofinvest/evidence_scenarios.py` previously set `dart_viewer_verified` from a caller-controlled JSON field, `dart_filing.direct_viewer_verified is True`, despite making no network request and possessing no signed or otherwise authenticated receipt. A modified fixture could therefore claim direct DART verification without opening the official viewer. This was a code trust-boundary defect, NOT evidence that the original repository fixture was dishonest.

- **Option A — keep caller-reported flag:** zero code change but permits false independent-verification claims. Rejected.
- **Option B — fail closed on offline path:** always return `dart_viewer_verified = False`; preserve the established `verified/conflict/unavailable` arithmetic claim classifications, issuer evidence URLs and DART reference metadata separately. Chosen. A future actual independent DART verification should use a distinct authenticated mechanism/receipt and explicit approval, not the caller's own JSON flag.

## Code and tests
- `proofinvest/evidence_scenarios.py`: never upgrades manual verification to direct DART status.
- `tests/test_evidence_scenarios.py`: two new regression tests cover forged `direct_viewer_verified: true` with plausible receipt metadata, and a bare/missing `dart_filing`; all stay false even when matching or conflicting claims are calculated. No real network calls or keys.
- Code SHA: `365d7f91ac5cf046906ce6a74e78bbd19e683376` ([GitHub commit](https://github.com/hibi89/hibi89-kic-proofinvest/commit/365d7f91ac5cf046906ce6a74e78bbd19e683376)).
- [GitHub Actions 40094034839](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40094034839): **completed/success, 165/165 unittest PASS, 0 FAIL**, master JSON consistency, Streamlit AppTest, offline scenarios, restored synthetic ZIP and save/reload all passed. CI runs Python 3.11; actual live API / DAKER production access still untested.
- Last baseline was **163/163** PASS on [CI 40093778478](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40093778478). New code adds exactly 2 tests. No expected original scenario result change.

## Official-source review and unresolved external blockers
- Tried the official DART URL `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250311001085` once in this new work cycle: **HTTP 502**. Per Stop & Pivot, did not repeat the same failing request. Independent source authentication still **BLOCKED**, score **90/100** for 10/30.
- Samsung Electronics official 2024 Business Report landing page remains readable: `https://www.samsung.com/global/ir/reports-disclosures/public-disclosure-view.84359/`. This supports an issuer-published report **link**, not the separate DART accession-viewer acceptance criterion. Previously reviewed Samsung consolidated statements are preserved, not re-published.
- DAKER 10/25 and 11/09 authenticated team leader/upload authority each **60/100 BLOCKED**; app navigation button is not a final-submit receipt. 11/10 intended submission is **NOT_STARTED**. No login, phone authentication, account alteration, file upload or final submission was performed.
- Public repository contains no private PDF/PPTX, secrets, browser tokens or copyright-restricted entire filing copies.

## Separate safety-hardening task meter (NOT a new 60-day scheduled DONE)
| Evidence gate | Weight | Earned |
|---|---:|---:|
| Review code/actual DART access and reproduce unsafe trust path | 20 | 20 |
| Minimal fail-closed fix preserving offline arithmetic path | 35 | 35 |
| 2 new regressions and remote 165-test CI SUCCESS | 30 | 30 |
| QA, status and cross-chat handoff sync | 15 | 15 |
| **Total** | **100** | **100** |

**Additional safety unit 100/100, remaining base 0h + contingency 0h, actual hours unmeasured.** This is NOT full DART verification and does NOT alter the 60-day canonical ledger: **29 DONE / 3 BLOCKED / 28 NOT_STARTED**, with `2026-12-03` result check `WAIT_OFFICIAL_RESULT` (future). If owner permission becomes available, DAKER submission preflight overrides other work.

## Recovery
The previous GitHub code HEAD `a456f3f456782e65ef3f7ac6a4b131bba0e51639` remains available in history for normal revert if regression found. No force push, API key issuance, expense, or access policy change. Date verified: 2026-10-24 21:29 KST; this report reflects code CI before the follow-up documentation commit; the documentation CI must be separately observed.
