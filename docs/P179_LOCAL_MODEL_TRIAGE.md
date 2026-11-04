# P179 — Optional Ollama-compatible LOCAL model triage (NOT source-authenticated AI)

This is a separate, explicitly opt-in **localhost-only** precondition for a future grounded LLM/agent. The model chooses one of A/B/C for *human* review; it **cannot** write its own financial claim, assert source rights, place orders, change Guard HOLD, publish a recommendation, or approve KIC filing. Its output shows an existing strict deterministic interpretation from the validated packet, **never the free-form model text**.

The official Ollama-compatible non-streaming `POST /api/generate` JSON contract is used, constrained to `http://127.0.0.1:11434/api/generate` (or an explicitly provided different *local-only port*). Proxy and HTTP redirects are disabled; timeouts and request/response byte ceilings apply. There is no startup, model installation, download, GPU requirement or billable API call in this feature. It does **not prove** the service on localhost is a genuine LLM; a local proxy could still forward data, so run only after checking the local server configuration.

Pass both redacted outputs from P178 (NOT original SEC/stock/NDX files), **after checking their source authorization and internal receipt integrity**:

```sh
python -B -m scripts.local_model_triage_cli \
  --review ./review/kuodra-offline-a-b-c-review-UNVERIFIED.json \
  --rights ./review/kuodra-source-rights-GAPS-UNVERIFIED.json \
  --model llama3.2 \
  --allow-local-model --confirm-local-derivative-processing
```

The caller must make two explicit consents at runtime; default action is BLOCKED without any HTTP. The model receives only A/B/C **local unverified status labels** and a fixed prompt, not ticker, CIK, accession, raw financial values, market price series, original HTML, user filenames, SHA or API credentials. A selected engine and exact `HUMAN_REVIEW_ONLY` label are returned by the model; KUODRA refuses any extra/free-form text, mismatched model, advice, duplicate-key JSON, redirects or malformed response. Only an already authored, offline-verified interpretation is shown.

**Verification scope:** Python full regression and real loopback POST to a disposable Ollama-shaped HTTP **emulator** on GitHub Windows/Linux; vendor/model inference is **not** tested and `model_inference_authenticated=false`, `ai_agent_executed=false` even after protocol PASS. Model quality, publisher rights, actual authorized LLM processing, cloud Production and official DAKER submission remain HOLD. Existing P176 Docker host port failure never retried.

Protocol reference: https://github.com/ollama/ollama/blob/main/docs/api.md.
