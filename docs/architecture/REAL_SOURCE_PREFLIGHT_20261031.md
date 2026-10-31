# P49 — KUODRA Offline Real-File Preflight

Date: 2026-10-31 KST. Tested code SHA: 5c69335c81c739378aec907fe715313d25f1eb8c. CI: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41207181153

## Selected implementation and alternatives
Selected: reuse the existing local 3-source SEC capture ZIP verifier, byte SHA, Guard with temporary SQLite, paired-market-CSV parser, industry comparison and safe HTML report renderer. Zero provider calls or data transmission.
Deferred: real SEC or market data API integration requires explicit approval, genuine contact identity, data rights, version history, corporate actions and cost review.

## Inputs
- A previously captured SEC ZIP containing manifest.json, submissions.json, companyfacts.json, original_filing.bin and bounded receipt timestamps; this program does not download or save such a bundle.
- Optional CSV with exact header date,security_close,benchmark_close, 31-501 aligned ascending positive daily sessions and user-claimed HTTPS source/date/price basis.
- Optional kuodra.industry-vision.v1 JSON with matching SEC issuer, fiscal periods, annual revenue and actual local CompanyFacts SHA in both target source references.

## Command
Run as one line in PowerShell, with owner-provided files and values (paths below are placeholders):

python -m proofinvest.real_data_preflight --sec-bundle C:/Data/sec.zip --prior-end 2024-09-30 --current-end 2025-09-30 --needle EXACT_10K_LITERAL --market-csv C:/Data/prices.csv --symbol EXAMPLE --benchmark NASDAQ_100 --return-basis PRICE_ONLY_CLOSE --market-source-url https://example.org/owner-source --market-published-at 2025-10-16 --industry-json C:/Data/industry.json

Both market CSV and industry JSON are optional. Omit all five market metadata flags when omitting the CSV.

Exit 0: local_structure_pass_origin_unverified, with sanitized JSON receipt and temporary Guard audit deleted. Exit 2: blocked, no success claim. SHA proves local byte equality, not SEC/provider authenticity. No raw file export, upload, public deployment, permanent audit, model execution or trade. Corporate actions, adjusted historic vintages and licenses remain unverified.

Acceptance for genuinely real data still requires owner-approved lawful originals or scoped SEC queries, independent issuer and release-vintage authentication, peer/sector data rights, fiscal comparison and actual data E2E; synthetic CI is not real-world market validation.
