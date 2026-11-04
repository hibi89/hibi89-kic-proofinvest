# P186 - Real customer UI for P185 offline numeric claim review

P185 offered only an operator CLI for checking a JSON draft against a source-linked review packet. P186 wires that **unchanged, existing pure offline verification function** into the actual localhost ticker Streamlit screen.

## Design comparison
- Add a third upload to P180's consent-to-LLM controls: shares a network-capable button path and complicates consent; rejected.
- Separate default-closed, local-only review section with three bounded uploads and a distinct explicit verify button: selected. No model HTTP, SEC calls, paid vendor access, new storage, account change, Production setting or leaked originals.

The result can only display verified local Decimal price vs true NDX *receipt* gap in a pre-authored deterministic note. A forged correct JSON, a wrong number, inconsistent receipt, oversized input, or rights/auth escalation blocks.

Acceptance: focus UI unit tests (default-closed, disabled button, actual numeric validated result, wrong-number fail, auth escalation fail) and the unchanged full Python/Windows/Chromium CI. Synthetic fixtures are not publisher-authenticated legal financial data. UI execution or CI green alone does **not** earn any of the blocked 49 final-product acceptance points; baseline **51/100 remains until an independently fulfilled remaining official gate**. This section is not an LLM invocation, source licensing or DAKER submission.

## Actual Chromium acceptance

The existing `scripts/local_model_triage_browser_smoke.py` browser script now opens the P186 panel in a real local Chromium Streamlit session, uploads three PUBLIC SYNTHETIC documents, verifies the local Decimal return gap, then mutates the saved draft to verify blocking and stale-success clearing. The already bound P180 localhost HTTP emulator remains at exactly one POST: P186 causes **zero additional HTTP calls**. No production or licensed sources are involved. Passing the browser test is a necessary functional check, not proof of rights or completeness.
