# P180 — Browser UI for LOCAL model triage (opt-in, no model or external data license)

Existing KUODRA local Streamlit single-ticker screen has a new **independently actionable review panel**. It connects P178 generated, redacted A/B/C review JSON plus rights-gap JSON with the P179 strict, localhost-only Ollama-compatible protocol. No new account or deployment. The previous P179 CLI remains unchanged and useful separately.

Start `KUODRA-Local.cmd` from a trusted Python3.11/Streamlit environment (only 127.0.0.1 host). From the "자료 유형" selector choose **KUODRA · 종목 1개 검색 (로컬 전용)**. In "로컬 AI 검토 우선순위" expand the panel, re-upload the **redacted** P178 review/rights files, select a user-installed local model and local port, check **both** explicit consent boxes and click the one-shot button. The panel is independent of the SEC original 4-file input button. This prevents auto-calling a model on Streamlit reruns and prevents source originals from entering the model.

Security:
- No network until both consent boxes, two bounded canonical redacted files, explicit button and a valid localhost-only numeric port.
- Packet+rights pair are validated again by P179 module. Only three status codes A/B/C are sent, not ticker, CIK, accession, SEC text, stock/NDX observations, file names, hashes or keys. No request proxy or redirect; input and output size bound.
- Only `HUMAN_REVIEW_ONLY` and one A/B/C choice can emerge from a model, with predefined evidence-linked deterministic cautionary explanation. `Guard HOLD`, `source_rights_verified=false`, `ai_agent_executed=false`, `trade_executed=false` remain enforced.
- A localhost listener can still be configured as an outbound forwarding proxy, **so users must ensure a trusted local model configuration before opting in**. The app cannot authenticate provider/model weights. Do not load or send unapproved data to an untrusted local server.

Windows/Linux unit tests plus **real Playwright Chromium browser** in GitHub Actions verify upload, disabled controls, dual explicit consent, one real HTTP POST to a disposable localhost *emulator*, no raw-source identifiers in prompt, valid selected focus display and rejection of altered packet without extra network requests. This is verified UI integration, **not a genuine LLM response or verified financial interpretation**. Genuine model execution, lawful real original market data and live Production are still blocked/unverified. P105 SEC 403 and P176 Docker host-loopback failures must not be retried. DAKER prelim final submission separate owner authorization by 2026-11-12 10:00 KST.
