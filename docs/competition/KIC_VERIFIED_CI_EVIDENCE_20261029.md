# KIC 2026-10-29 — verified offline CI evidence

## Recorded verified result (not an estimate)
- Branch: `lead/kic`.
- Commit: `b5fc779aff8269c6dec9f92081debdb2b4925e00`.
- Workflow: `offline-tests`, run **40876711470**, conclusion **success**.
- Direct evidence: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40876711470
- Full verifier: syntax **PASS**; **568 tests PASS**.
- Guard suite: **43 tests PASS** (executed twice in the workflow).
- Offline Guard demo: **PASS**; curated Apple 10-K excerpt + synthetic HOLD/REJECT/APPROVE, explicit simulation-only review; source authentication false; no trades.
- Deterministic Korean/English question router: **three actual offline paths**, explicit execution from Streamlit, missing/conflicting intent fails closed; **not an LLM planner**.
- Independent Chromium job: SEC Guard audit + human acknowledgement + source selector + actual growth-router button + `GROWTH_CHECK → REJECT` all **PASS**, screenshots and JSON receipt archived.
- The workflow's all other verification steps also concluded success (synthetic snapshot, recovery bundle, judge receipt, controller, evidence scenarios).

## Downloadable GitHub Actions artifacts (retention 14 days)
- `proofinvest-guard-offline-receipt` (`guard-demo.json`; artifact ID `12897764814`)
- `proofinvest-synthetic-demo-recovery` (artifact ID `12898118594`)
- `proofinvest-public-judge-replay` (artifact ID `12898018932`)

- `proofinvest-guard-browser-evidence` (`guard-browser-clickthrough.png`, `intent-router-browser.png`, `guard-browser-evidence.json`; artifact ID `12898616476`)

## Failures identified and resolved
- `tests/test_disclosure_lightning.py`: mocked network fetch test assumed an historical observation on 2026-10-27 although the actual test ran later. Changed test to use its real observation time as cutoff, **without weakening** production's collection-after-as-of rejection.
- `tests/test_offline_review_batch.py`: CSV test expected literal backslash-n characters instead of CSV line terminators; corrected the expected string.
- `scripts/verify_local.py`: bounded failing-test diagnostics now surface in CI to enable independent debugging.

## Submission disclosure boundaries
- CI verifies the **offline code and tests**, including rule-based keyword router and actual headless Chromium UI clicks, NOT external SEC source authentication, LLM inference/agent operation, brokerage orders, uptime, service impact, or legal/data license review.
- `APPROVE` is demonstration eligibility for human simulation review, **never a trading authorization**.
- SQLite SHA-256 hashes indicate limited tamper evidence; privileged complete DB rewrite is outside the threat model.
- Official 10-page submission PDF must be aligned with the organizer-provided PPTX template, reviewed and actually submitted separately. No submission receipt at this time.
