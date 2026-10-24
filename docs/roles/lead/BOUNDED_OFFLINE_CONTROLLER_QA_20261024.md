# KIC ProofInvest — Bounded offline workflow controller QA (2026-10-24)

## Delivered
- `proofinvest/agent_controller.py`: explicit **RULE_BASED_OFFLINE_NOT_LLM_AGENT** controller for one pre-supplied research/financial/evidence case. It checks requested 8-digit issuer and fiscal year against the provided records *before* tool invocation; then dispatches at most one local `evaluate_offline_chain` call and issues a deterministic next-action reason. Trace: PLAN → EVALUATE → DECIDE → REPORT, or PLAN → BLOCKED if input invalid.
- **No independent research agent, LLM planning, remote document selection, real OpenDART, URL fetch, automatic retries, writing files, trading, or external tool execution.** `ai_agent_executed=false`, `live_api_called=false`, `authenticated_external_source=false`, `official_contest_submission=false` are forced even if input metadata self-attests otherwise.
- The single selected tool reuses previously proven `Research→Verification→Risk` arithmetic gates. The controller is an accountable **workflow skeleton**, not a finished autonomous AI Agent; judge scoring or finalist status cannot be inferred.

## Decisions
| Input state | Branch | Downstream action |
|---|---|---|
| Malformed request / issuer/year mismatch / missing records | `blocked` before local tool | Request structured valid input / manually check issuer + year |
| Evidence URL/issuer/Research finding not linked | `UNLINKED_PROVENANCE` | Manual primary-source/citation review; no Risk |
| Historical revenue claim conflicts | `GROWTH_CLAIM_CONFLICT` | Request analyst review; do not calculate Risk |
| Claim missing or invalid | `CLAIM_UNAVAILABLE` | Request usable claim; do not calculate Risk |
| Matching arithmetic but no eligible liabilities + equity | `RISK_FACTS_NOT_ELIGIBLE` | Request source-linked balance-sheet facts; never report risk=0 |
| Synthetically supplied risk facts structurally compute | `STRUCTURAL_RESULT_ONLY` | Require **independent source and usage-rights validation**; not authenticated verified |

## Reproducibility
```bash
python -m proofinvest.agent_controller --claim 16.20
python -m proofinvest.agent_controller --claim 30
python -m unittest discover -s tests -v
```
- The command reuses pinned *previously manually transcribed* Samsung FY2024/FY2023 public-source JSON. The 16.20% arithmetic match results in `needs_evidence` (Risk withheld), the 30% claim results in `blocked` (conflict). Neither counts as a fresh issuer document authentication, signed receipt or AI run.
- Existing private frozen 10-page contest PDF/PPTX and six private Library records **untouched**, no user session/access/phone auth, no account or submission action.

## Tests and CI
- 13 new unit test methods in `tests/test_agent_controller.py`: matching claim, conflicting claim, absent/invalid claim, malformed request fail-closed, year/issuer mismatch, absent inputs, unrelated citation, forged DART verification, structurally computed synthetic Risk still not authenticated, absent/bad Risk, bounded deterministic trace and input immutability, CLI subprocess, pinned-manual no-write.
- Code SHA: `3aa9a3a4e416e6a9632d18ab339cf8314d6c6ea8`; [GitHub Actions #40103929809](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40103929809) **COMPLETED SUCCESS, 227/227 PASS** (prior 214/214). GitHub CI also checks 60-day ledger sync and existing separate synthetic ZIP/public manual judge artifact.
- Follow-up CI adds two explicit CLI smoke executions against the pinned manual source, asserting `RISK_FACTS_NOT_ELIGIBLE` and `GROWTH_CLAIM_CONFLICT`, tool count ≤1, 0 external calls, no real AI or DART. Documentation+CI commit must be independently verified.

## Tradeoffs and next development boundary
- A: Add LLM/remote OpenDART end-to-end now — requires caller source authentication, API permissions, rights, live retries, deployment secrets and contest phase. Risks confusing unverified source with trusted data; **defer pending explicit scope/permissions and submission gate**.
- B: Write more static agent architecture slides — little additional executable proof.
- C: Use existing verified-only offline functions behind a traceable finite-state controller, cover wrong inputs and human stop reasons (chosen).
- Real autonomous Agent/tool choice, isolated data source validation, a deployed URL and E2E test remain not verified. The original frozen proposal truthfully described these as goals; no change to it is required.

## Status/next priority
- Official 60-day ledger **29 DONE / 3 BLOCKED / 28 NOT_STARTED**, next 2026-12-03 future result check; this new work is an additional isolated feature, **not an originally scheduled 60-day task or 100% overall product completion**.
- External P0: DAKER authenticated team/individual leader and final PDF submission authority on 10/25 and 11/09 each **60/100 BLOCKED**. DART official filing direct-viewer accession on 10/30 **90/100 BLOCKED**. Intended Nov10 controlled submission NOT_STARTED; official Nov12 10:00 KST deadline; submission plus Nov12–Nov19 peer voting require actual account and explicit human action.
- Standalone controller implementation/CI/QA task: 100/100 completed once documentation-only CI passes. Remaining for this narrow unit base **0h + reserve 0h**; actual elapsed work hours unmeasured. Additional real-API/Agent effort/time **not** zero and has no verified estimate.
- Rollback previous HEAD `ad16c99cc53a3efa01bc191d7f444b72e78cfe9e` by normal Git revert only; no force push.
