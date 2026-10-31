## P51 — Direct SEC 3-source files (alternative to capture ZIP)

A separately saved capture ZIP is **not** required if the operator has the original three individual files. The same local SEC validation, SHA pinning, temporary Guard, optional market CSV/evidence and industry JSON are reused without any provider/API call or original-file overwrite.

Example **single PowerShell command** (replace all file paths, issuer/accession, filing dates and 10-K text literal with your own authorized values):

```powershell
python -m proofinvest.real_data_preflight --sec-submissions C:/Data/submissions.json --sec-companyfacts C:/Data/companyfacts.json --sec-filing C:/Data/10-k.htm --issuer-cik 0000000001 --accession 0000000001-25-000001 --as-of 2025-10-16 --collected-at 2025-10-16T12:00:00Z --prior-end 2024-09-30 --current-end 2025-09-30 --needle EXACT_10K_LITERAL --market-csv C:/Data/prices.csv --symbol EXAMPLE --benchmark NASDAQ_100 --return-basis PRICE_ONLY_CLOSE --market-source-url https://example.org/price-history --market-published-at 2025-10-15 --industry-json C:/Data/industry.json
```

Supply the full group --sec-submissions, --sec-companyfacts, --sec-filing, --issuer-cik, --accession, --as-of, --collected-at OR --sec-bundle, never both. Capture must use UTC YYYY-MM-DDTHH:MM:SSZ or +00:00 on the same UTC day as as-of. This clock is operator-reported, never authenticated. The examples are placeholders, not real SEC data. Market and industry arguments remain optional; adjusted total-return prices require --market-evidence-json as specified below.

Direct mode returns sec_input_mode=DIRECT_THREE_FILES_UNAUTHENTICATED, sec_capture_digest_matched=false (no capture ZIP), sec_local_byte_sha256_computed=true. All three local raw SHA hashes appear in the sanitized receipt after a local structural pass. source_authenticated=false, external_http_called=false, audit_retained=false and the existing data rights/PIT flags remain false.

Selected architecture: direct read-only ingestion of bounded originals with existing SEC review (no extra dependencies, no provider/API costs). Alternate existing ZIP replay for captured bundled inputs, kept fully backward compatible; a new downloader would need explicit permission, real User-Agent, market rights and provenance.

---

## 2026-10-31 KST — P50 market source/adjustment declaration gate

New optional flag: `--market-evidence-json PATH` alongside `--market-csv`.
Price-only CSV without a manifest keeps existing behavior but reports `MISSING_OPERATOR_EVIDENCE`. Adjusted-close total-return proxy CSV **requires** an explicit evidence JSON and fails closed without one.

The exact `kuodra.market-data-evidence.v1` JSON fields are:

```json
{
  "schema": "kuodra.market-data-evidence.v1",
  "issuer_cik": "0000000001",
  "as_of": "2025-10-16",
  "symbol": "SYNTH",
  "benchmark": "NASDAQ_100",
  "return_basis": "PRICE_ONLY_CLOSE",
  "market_csv_sha256": "REPLACE_WITH_ACTUAL_64_CHAR_CSV_SHA256",
  "price_first_date": "2025-08-01",
  "price_last_date": "2025-10-02",
  "claimed_source_url": "https://example.org/combined-price-sheet",
  "claimed_published_at": "2025-10-15",
  "captured_at_utc": "2025-10-15T12:00:00Z",
  "price_provider": "OPERATOR_DECLARED_PROVIDER",
  "rights_scope": "UNKNOWN",
  "revision_policy": "VERSIONED_SNAPSHOT_CLAIMED",
  "stock_split_treatment": "UNADJUSTED",
  "stock_dividend_treatment": "EXCLUDED",
  "benchmark_total_return_claimed": false
}
```

**Example data is synthetic and intentionally not executable unchanged**; the digest, symbol, price basis, URL, published_at, exact period and source fields must be replaced by values corresponding to the actual local CSV. The schema is closed; API keys, email addresses, personal identifiers and other free fields are rejected.

Allowed rights_scope: `UNKNOWN`, `LOCAL_RESEARCH_CLAIMED`, `REDISTRIBUTION_CLAIMED`. Revision policy: `UNKNOWN`, `RETROSPECTIVE_UNVERSIONED`, `VERSIONED_SNAPSHOT_CLAIMED`. Split: `UNKNOWN`, `UNADJUSTED`, `ADJUSTED_CLAIMED`; dividend: `UNKNOWN`, `EXCLUDED`, `INCLUDED_CLAIMED`.

`PRICE_ONLY_CLOSE` requires dividend `EXCLUDED` and benchmark_total_return_claimed=false. `ADJUSTED_CLOSE_TOTAL_RETURN_PROXY` requires `ADJUSTED_CLAIMED` split treatment, `INCLUDED_CLAIMED` dividends and benchmark_total_return_claimed=true. The labels are operator claims, **not certification of corporate actions or vendor licenses**.

Captured-at must be UTC `YYYY-MM-DDTHH:MM:SSZ`, no earlier than claimed release. If captured after analysis as-of, preflight records `RETROSPECTIVE_CAPTURE_NOT_POINT_IN_TIME`, never true historical vintage certification. If captured before/on as-of it records `PRE_ASOF_CAPTURE_CLAIMED_UNAUTHENTICATED`, still not third-party authenticated.

Example CLI addition: append `--market-evidence-json C:/Data/price-evidence.json` to the prior P49 command. Output reports local metadata SHA, `market_evidence_status` and `market_evidence_vintage`, while `source_authenticated`, `data_rights_verified`, `corporate_actions_verified` and `point_in_time_backtest_verified` remain false.

Two designs compared: (1) this bounded no-network declaration-and-digest gate (selected: no provider cost, strong input consistency, minimal dependencies); (2) authorized vendor API/archive/total-return reconstitution (deferred: provider rights/API cost/history and corporate action evidence required). Neither self-attested JSON nor metadata SHA proves authentic provenance. P50 synthetic CI does not prove real market reliability.

---

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
