# KIC ProofInvest — source-linked offline Research→Verification→Risk integration (2026-10-24 KST)

## Value and scope
A narrow code integration between existing modules, not a new AI service or live OpenDART feature. Before this change, Research, manual two-year financial Verification, and verified-only Risk were separately tested. The new `proofinvest/evidence_chain.py` exposes `evaluate_offline_chain` to orchestrate these existing contracts on **caller-supplied** records, with an explicit linked-provenance gate. The module is programmatic; no Streamlit new UI, production demo, LLM planner or network.

**Boundary:** this is out-of-schedule preparation while DAKER authenticated submission is externally blocked; it is **not** the 2026-12-14 conditional FINALIST_ONLY production integration task, and it must not be reported as finalist qualification or the complete AI Agent.

## Architecture choice and behavior
- **A (rejected):** compose the three raw statuses directly; valid arithmetic from unrelated financial issuers could slip through as an apparently cohesive report.
- **B (chosen):** require that an accepted Research finding cites the **same HTTPS issuer-PDF URL**, that Research target ID equals Verification evidence corporation code, and Verification fiscal year equals the financial record's report year. Missing/conflicting growth claims prevent risk calculations. Even when upstream matching succeeds, Risk facts must match the same issuer and exact PDF URL and use manual source provenance. The existing Risk gate separately enforces liabilities/equity, CFS, year, annual code, unit, same evidence_ref and usable numeric amounts.
- Stage-level outputs are preserved so investigators can see which gate failed. An invalid research request fails closed without making network calls.
- The successful **structural** path explicitly declares `mode=OFFLINE_SUPPLIED_EVIDENCE_CHAIN`, `ai_agent_executed=false`, `live_api_called=false`, `authenticated_external_source=false`, `source_rights_verified=false` and result `status=structurally_calculated_unverified`. A successful metadata chain or self-reported `state=verified` is **not independent authentication**; issuer/source rights and fact correctness still require separate actual source checks.
- **No company facts invented:** new tests construct wholly **synthetic** provided records (including synthetic amount values, URLs and publication timestamps). They are not presented as real financial facts, and do not modify the existing Samsung 2024 manually transcribed evidence.

## Tested evidence
- Python source `proofinvest/evidence_chain.py` + `tests/test_evidence_chain.py`.
- 10 new independent test methods: full linked chain, wrong growth claim blocks Risk, absent evidence blocks, wrong citation URL blocks, absent finding blocks, cross-issuer/source/provenance risk facts blocked, missing two Risk facts withheld, target-ID mismatch blocked, input immutability/order invariance, invalid research payload fail-closed.
- Code commit [`ceaba2c7d976b0ae82b5c912fae36704d7a94ef9`](https://github.com/hibi89/hibi89-kic-proofinvest/commit/ceaba2c7d976b0ae82b5c912fae36704d7a94ef9) on `lead/kic`. [GitHub Actions #40096210221](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40096210221) **completed/success, 182/182 unittest PASS, 0 FAIL**; progress checker/Streamlit AppTest/synthetic ZIP restore/persistence scripts all successful. Previous baseline 172/172.
- **Untested:** actual authenticated financial API, real Bank/issuer direct ingestion, actual model/LLM/tool orchestration, web browser UI, user-scoped account access, DAKER final submission, real deployment.

## Gate accounting, recoverability
| Extra offline integration evidence gate | Points | Earned |
|---|---:|---:|
| Inspect 3 existing modules and select fail-closed chain | 20 | 20 |
| Implement structural provenance linking and downstream withholding | 35 | 35 |
| New 10 regressions and full remote GitHub CI 182 PASS | 30 | 30 |
| QA + status + central-lead handoff | 15 | 15 |
| **Separate unit total** | **100** | **100** |

Remaining **base 0h + contingency 0h**, actual elapsed working time **unmeasured**. This 100-point unit is not a new canonical 60-day date; official calendar **29 DONE/3 BLOCKED/28 NOT_STARTED** remains unchanged with `2026-12-03` next future `WAIT_OFFICIAL_RESULT`.

**External blocks unchanged:** DAKER 10/25 and 11/09 at **60/100** each (real participant/team leader submission/phone-verification step unverified); DART official viewer 10/30 at **90/100** (live filing access 502); DAKER 11/10 final submission NOT_STARTED. Private 10-page PDF/PPTX and Library 6 assets untouched, no public upload, no fees. Current connected browser requires originating browser context. Once user authentication/authorization available, submission eligibility P0 remains first priority.

Rollback code SHA before this integration: `5e5f5349832d8255275ece436ddeb0b4bdf2c8db`; regular revert only if needed, no force push. This document final CI is verified separately after its own commit.
