# P188 — real local model weak focus: stop and pivot to safe bounded fallback

## Evidence and stop point

P183 real model trial [Actions #41866473820](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41866473820) actually loaded public Apache-2.0 SmolLM2 135M, executed token generation, then **failed the strict independent P183 missing-evidence priority**. Earlier source syntax `)::` was removed and AST-before-pull added; the model now actually executed and returned a rejected review. No repeated retries, model/provider swap, added remote API, weaker schema, higher model allowance, or source transfer is justified by this evidence.

## Selected design

1. Continuing to require the tiny model's approval of the deterministic worklist (expensive repeated CI, never release-eligible when it disagrees): **rejected**.
2. **Selected:** after checking strict JSON schema, compare with trusted A/B/C status-based human priority; return an explicitly BLOCKED response if different. A model JSON shape verified flag is **not** a reviewed priority; no focus, interpretation, trade or suggestion may reach the UI. The real-model CI now checks both acceptable outcomes: actually agreed with deterministic local policy **OR** safely blocked without external network, trade or original upload. The CI receipt differentiates success from fallback and NEVER asserts that blocked output is accepted human focus.
3. If the model output is malformed rather than just disagreeing, the existing strict parser blocks it. The CI reports `real_model_structured_focus_accepted=false` rather than inventing success. The old P182 actual accepted model proof remains historical evidence at SHA `5f74970a...`; latest behavior must be judged from the new exact SHA.

This is a testable safe operation of the real local model despite its limited ability, **not proof of financial agent accuracy**. Publisher-authenticated real original SEC, genuine licensed stock/true NDX/peers, source-grounded model explanations, public Production and DAKER final receipt remain unverified; final acceptance **51/100 ceiling pending verification**, no incremental point from graceful fallback. All external rights/approval gates and owner V13 preserved.
