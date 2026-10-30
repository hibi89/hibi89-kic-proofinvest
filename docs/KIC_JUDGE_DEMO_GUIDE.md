# ProofInvest KIC — 60-second judge demo (offline-only)

> **Scope:** Fictional SEC-shaped fixtures, deterministic local evaluation and
> temporary SQLite integrity evidence. **Not** live SEC/DART authentication,
> source-rights verification, real LLM execution, investment advice, trading,
> or official KIC submission.

## Open the judge view

In a local checkout of the full repository (not the reduced recovery ZIP):

```powershell
python -m pip install -r requirements-ui.txt
python -m streamlit run streamlit_app.py
```

Open `http://localhost:8501/?demo=guard` (or the actual port printed by
Streamlit, followed by `/?demo=guard`). This is **a local address, not a
deployed public demo URL**. The query parameter preselects **SEC→Guard 감사 연결
— 합성 오프라인**; it does not execute a case or write an audit file.

## 60-second walkthrough

1. **Before execution:** Show the evidence-first message, three case previews,
   and the explicit **SYNTHETIC ONLY** warning. No audit database should be
   created just by opening this page.
2. **Matched:** Click **합성 SEC→Guard 검증 실행**. View calculated_unverified,
   Guard **HOLD**, visible raw-byte citation status, six-stage evidence trace,
   the local SQLite audit receipt, and the human review next action.
3. **Conflict:** Select **주장 불일치 → REJECT** and run again. Guard must show
   **REJECT** for the deliberately conflicting claimed growth percentage.
4. **Script-only citation:** Select **스크립트에만 있는 인용 → HOLD** and run again.
   The text-node citation status must be **unavailable**; script literals
   cannot substitute for visible source text.
5. **Comparison:** Click **3개 시나리오 일괄 비교**. Expected policy outcomes are
   **HOLD / REJECT / HOLD** with 3/3 **local** audit-chain checks. Download
   the JSON comparison or the synthetic-only ZIP containing `START_HERE.html`.
   The results must not be described as authenticated investment decisions.

## Reproducibility and evidence

The Chromium runner `python -B -m scripts.guard_browser_smoke <output_dir>`
automates the real Streamlit click-through and produces screenshots, a
read-only SQLite inspection receipt, the comparison JSON, and an offline
synthetic judge ZIP. The additional
`judge-direct-link-before-run.png` proves that a **cold new browser page**
opens the intended judge view without triggering evaluation.

These are **checks scripted in the repository**; passing CI or a real
browser verification must be confirmed for the exact checked-out commit.
Do not describe a queued run as passed. Review the GitHub Actions artifact
`proofinvest-guard-browser-evidence` only after the browser job finishes.

## Non-negotiable boundaries

- SHA hashes are **local byte-integrity receipts**, not issuer signatures.
- Growth arithmetic is **structural**, not source authentication.
- Risk inputs lacking independently supported provenance stay in review.
- Guard **HOLD / REJECT** never authorizes simulation or a real trade.
- No private preliminary PDF or API credentials should be added to the
  public synthetic ZIP or public GitHub repository.
- A local Streamlit link is not a production URL or submission proof.
