# P106 — NVDA historical issuer IR alternative and KIC preliminary submission gate

## P105 stop boundary (immutable)
- Owner Windows local result, 2026-11-02 KST: one SEC GET attempted at ticker_map; HTTP 403 SEC_ACCESS_DENIED_403; UNAVAILABLE; no SEC source downloaded or stored. No retry, UA/proxy bypass or new SEC GET. Four-stage SEC pipeline remains UNAVAILABLE.
- Previous Python 1361 PASS / Windows / Chromium CI is offline regression, not proof of live SEC access.

## Alternatives
1. Further SEC attempts/mirrors/alternative IP or User-Agent: REJECTED due to explicit stop and authenticity/policy risk.
2. Official NVIDIA public historical issuer earnings-release table, manually transcribed bounded GAAP checks, offline: SELECTED. No new credentials, paid API, or existing SEC UI change. Source origin/redistribution rights are not authenticated by saved JSON.

## Source and reproduction
- NVIDIA Corporation (NVDA), official issuer release 2025-02-26, fiscal FY2025 ending 2025-01-26 versus FY2024 ending 2024-01-28. USD millions, GAAP consolidated condensed UNAUDITED.
- Official URL: https://investor.nvidia.com/news/press-release-details/2025/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2025/
- Figures FY25 / FY24: revenue 130497 / 60922; net income 72880 / 29760; operating cash flow 64089 / 28090; net accounts receivable 23065 / 9999.
- Run: python -B -m proofinvest.issuer_ir_replay
- Contradiction: python -B -m proofinvest.issuer_ir_replay --claim 140
- Tests: python -B -m unittest tests.test_issuer_ir_replay -v
- Results: revenue YoY 114.20%, FY25 operating cashflow / net income 87.94%, FY24 94.39%, receivables YoY 130.67%. arithmetic_state=verified means claim agrees with manually transcribed values only; never source authentication. Guard HOLD, misconduct flag false, no trade.
- Evidence file: docs/evidence/nvda_fy2025_issuer_ir.json. Its SHA256 checks local bytes only. Do not republish copyrighted source HTML/PDF without rights review. This is a HISTORICAL example, not the most recent annual data or a complete engine A/B/C run.

## Preliminary DAKER gate
- Official deadline 2026-11-12 10:00 KST; owner's internal early target 2026-11-10. Official organizer template, PDF 10 pages maximum, all seven sections: summary, problem, service, AI Agent, data, MVP, benefits.
- Frozen private V13 10-page candidate preserved; previously recorded SHA256 64810314b4fc8699f0c56087b8ad39c4da5658d243585e0500900f1b4b3f7ece. Actual source PDF file not accessible in this current GitHub connector work session, so no independent byte/page/visual verification now.
- Data-plan wording must distinguish real historical IR manual arithmetic P106 from P105 SEC live 403 and existing offline/mock-only source-to-engine flows. No claim of public Production, deployed external AI or real A/B/C/Guard complete automation.
- Owner must review exact frozen PDF and separately approve final submission, log into DAKER as authorized team leader, upload on submission tab, press final completion, verify status '최종' and preserve receipt. Team role, account access, actual submission remain UNVERIFIED.
- Elo peer evaluation for final submitted teams: 2026-11-12 12:00 through 2026-11-19 10:00 KST. Confirm minimum required voting on official DAKER interface.

## Verification and recovery
- Local isolated Python 3.11: 9/9 tests PASS, no external calls. GitHub Actions full CI and user Windows/browser are separately judged at specific SHA, not implied here.
- Additive paths: proofinvest/issuer_ir_replay.py, tests/test_issuer_ir_replay.py, docs/evidence/nvda_fy2025_issuer_ir.json, this document; short STATUS/HANDOFF entries. Original SEC UI, code engines, frozen PDF and historical evidence not modified. Ordinary git revert of new functional SHA if necessary; never force push.
