# P185 — checked numeric draft is not a licensed data or real-AI claim

One customer-facing gap in P182/P183: a JSON-schema-correct model response can provide a wrong price-vs-index numerical statement. P185 adds a **read-only offline A/B/C review-packet numeric-claim verifier**:

- Input: unchanged canonical P178 reviewer packet + linked source-clearance receipt + one bounded JSON draft.
- Format: exactly `{"schema":"kuodra.local-model-numeric-claim.v1","engine":"A","claim_kind":"OBSERVED_PRICE_RETURN_GAP_PP","gap_pp":"...","decision":"HUMAN_REVIEW_ONLY"}`.
- Gate: reject duplicate JSON keys, arbitrary text/extra fields/BUY intent, wrong benchmark, mismatched source receipt and any gap that differs from **independent Decimal recomputation using both stock and NDX return operands**.
- Output: only original deterministic human-reviewed interpretation, exact local evidence checksum, Guard HOLD, no trades. A model is not called here; an operator may supply a saved draft from an authorized local model.
- No network, local model pull, external provider access, rights assertion, financial advice, new private data, Production or DAKER action.

This is a real **numeric mistake rejection** prerequisite for later lawful, source-checked AI explanations. It does not prove actual LLM inference for a numeric claim, SEC/vendor provenance, Nasdaq index licensing or source-grounded agent quality. The synthetic test uses public fixture rows only, and must not earn a final-product completion point under the current 51/100 acceptance rubric merely by passing locally.

Example (offline only):

```sh
python -m scripts.local_model_numeric_claim_cli --review reviewer.json --rights clearance.json --draft ai-draft.json
```

Expected canonical PASS exit 0 with `source_rights_verified=false`; malformed draft returns exit 2. Actual publisher-authenticated and licensed issuer/index/peer originals and factual LLM evaluation remain required separately.
