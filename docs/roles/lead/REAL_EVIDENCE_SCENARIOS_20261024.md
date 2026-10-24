# ProofInvest 11/02 — Real-company filing claim scenarios (offline)
Date: 2026-10-24 14:18:36 KST

## Evidence input
- Existing **manually checked Samsung Electronics FY2024/2023 consolidated issuer PDF**: [data receipt](../evidence/samsung_2024_cfs_revenue.json) / [manual verification](REAL_FILING_VERIFICATION_20261024.md).
- FY2024 revenue KRW 300,870,903 million; FY2023 revenue KRW 258,935,494 million; **growth +16.20%**. This record is a manual transcription and check of issuer-supplied statements, NOT an authenticated OpenDART API response.
- DART filing ID direct viewer verification and DAKER permission/template remain separately blocked. PDF full text is not redistributed.

## Run reproducibly
```bash
python -m proofinvest.evidence_scenarios
python -m unittest discover -s tests -v
```
Three scenario results from **the one actual-company manually verified evidence record**:
1. `matching_claim: verified` — claimed **16.20%** agrees with recomputed annual consolidated revenue growth within 0.1 percentage points. The status means **claim-vs-record arithmetic agreement only**, NOT independent authenticity or investment judgment.
2. `incorrect_claim: conflict` — falsely claimed **30%**, contradicted by source-based **16.20%**.
3. `no_evidence: unavailable` — deliberate absence of source record blocks verification (no invented financial data, never `verified`).

The result returns `source_kind=MANUAL_PRIMARY_SOURCE_VERIFICATION`, `verification_scope`, actual issuer PDF `source_url` when evidence is accepted and the separately recorded `dart_viewer_verified=false` flag. Malformed claim, metadata mismatch, unreviewed source, wrong unit or stored arithmetic discrepancy fails closed as unavailable.

## Integration boundary
- `proofinvest/evidence_scenarios.py` is a **small deterministic decision tool**. No LLM planner, OpenDART call, web service, or automatic PDF extraction.
- The numeric parser reuses existing `proofinvest.engine.amount`, with stricter annual CFS/company/units/year/source/manual review checks. Historical synthetic CLI remains distinct.
- New `tests/test_evidence_scenarios.py` tests valid/false/missing paths, provenance, mutation safety, unit/period/tampering/claim guardrails and direct CLI JSON output.
- GitHub CI explicitly runs both the original synthetic demo and the real-company **offline manual-record** scenario runner. Do not call the latter `OpenDART production integration`.

## Acceptance gate (11/02 planned slot, developed early on 10/24)
| Gate | Points |
|---|---:|
| Review and link existing real-company official-source manual record | 20 |
| Implement three-state deterministic evidence evaluation with fail-closed semantics | 40 |
| Regressions and GitHub Actions CLI/tests pass | 30 |
| Remote evidence, day meter, lead and oversight handoff aligned | 10 |
| **Total** | **100** |

At initial code commit the implementation/source gates count as **60/100**; CI/report remain pending. The remaining conservative effort estimate is **0.5h base + 1h test/error buffer = 1.5h**, excluding external account/DART blockers unrelated to this standalone scenario unit. Work-time tracking `미계측`.

**NOT DONE by this unit**: complete end-to-end autonomous Agent product, DART official filing viewer validation, actual OpenDART fetch, deployment, official DAKER submission, full PDF evidence update.
