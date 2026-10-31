## P73 — Read-only verification of a saved P70 report ZIP (requires original receipt)

P70 optionally creates `new-kuodra-analysis.zip` after the offline local Guard/three-engine run and returns `report_bundle_sha256` in its JSON receipt. Store the receipt digest **separately from the ZIP**. Later, the ZIP can be checked without rerunning the data analysis and without reading external services:

```powershell
python -m proofinvest.local_report_bundle_verify "C:/Data/new-kuodra-analysis.zip" --expected-sha256 REPLACE_WITH_64_HEX_FROM_P70_RECEIPT
```

This is a real CLI option (the 64-character replacement is required). The verifier reads the local archive only, checks the exact original ZIP byte hash, bounded non-symlink regular file, exactly `report.json`, `report.html`, `manifest.json`, canonical JSON, stored file SHA-256/lengths, Guard/Engine report state and re-renders the existing escaped HTML for a byte-for-byte match. It refuses duplicate/unexpected entries, malformed/oversized ZIP and false origin/rights/AI/trade/audit claims. On success exit `0` with `LOCAL_ZIP_BYTES_MATCH_RECEIPT_ORIGIN_UNVERIFIED`. On failure exit `2` with sanitized `BLOCKED` JSON. No report is exported or mutated in verification.

**Integrity scope:** The verifier proves a local report ZIP still matches an **independently retained digest**, not who obtained its SEC/market/sector inputs or whether any self-reported release timestamp, data rights or provider claims are genuine. A matched file can contain only synthetic test data. Never treat an output digest as original SEC/issuer/publisher authentication or official contest submission. P73 source SHA `1afa1c8bc1b54df29b7575bf62d45167669f1cdc`, CI #41236018194 1,213 Python PASS and Windows/Chromium tests pass on synthetic inputs only.

## P70 — Explicit locally saved complete JSON/HTML report bundle (no output by default)

The existing one-shot offline preflight supports a **new optional** flag:

    --output-report-zip "C:/Data/NEW-kuodra-report.zip"

Append it to a correctly populated P69 command using lawfully held raw SEC 3-source ZIP or individual files, peer CompanyFacts, normalized industry-sector CSV and optional market CSV. All original filename/clock/rights requirements remain the same. The output path must be a new, previously nonexistent .zip file on the local filesystem; any existing file, symlink, invalid original, blocked Guard/revenue/industry/market contract or output failure returns the existing sanitized blocked JSON and exit code 2 without overwriting a user file. No destination folder or report file is made when this flag is omitted.

The one ZIP contains report.json (full offline SEC/Guard and A/B/C analytic evidence, not just summary status), report.html (existing safely escaped offline report), and manifest.json (original byte size and SHA-256 for the two report files and explicit flags that issuer origin, economic source rights and historical price/sector vintage remain unauthenticated). The command prints report_bundle_created=true and report_bundle_sha256 when successful; the ZIP never certifies first-party SEC original authenticity or source license and contains no persistent SQLite database. The ZIP itself is a USER-CONTROLLED local copy, so never redistribute customer-specific or licensed input-derived report content without permission.

Example for a user who has ALREADY supplied all necessary P69 input flags:

    python -m proofinvest.real_data_preflight [REPLACE_WITH_GENUINE_P69_SEC_MARKET_SECTOR_PEER_FLAGS] --output-report-zip "C:/Data/new-kuodra-analysis.zip"

The bracketed portion is an explanation placeholder, not literal runnable CLI flags. See preceding P69 documentation for the complete sample. P70 tested exact source SHA fdc373647bd8fbcc2205b1661ece83798d19c922 in GitHub Actions #41231426016: Python 1,197 PASS and Windows/Chromium jobs SUCCESS, using synthetic sources, not actual SEC and vendor originals. Do not count the generated report alone as actual investment or data integrity certification.

## P69 — ONE offline command for SEC originals, market CSV, and auto-derived Engine C

This mode **does not** require first writing a separate Industry Vision JSON. Provide (a) the verified-local-form SEC capture ZIP OR three direct SEC raw files and associated exact issuer metadata, (b) one or more raw peer CompanyFacts JSON files, (c) a **strict two-row UTF-8 normalized sector CSV** whose two `period_end` values equal the selected target SEC fiscal prior/current ends, and (d) optionally a stock/index market CSV and its existing URL/date/price basis evidence. Industry original SEC figures and peer SHA-256 are taken directly from bounded original bytes. Publication metadata and rights are self-declared, not independently certified.

**Synthetic placeholder invocation (NOT usable with real issuer data without replacing every identifier, period, source and value):**

```powershell
python -m proofinvest.real_data_preflight --sec-bundle "C:/Data/sec.zip" --prior-end 2024-09-30 --current-end 2025-09-30 --needle EXACT_SOURCE_TEXT --industry-sector-csv "C:/Data/sector-two-rows.csv" --industry-sector-url "https://example.org/source-data" --industry-sector-published-at 2025-10-15 --industry-name "Example sector" --industry-series-name "Example output index" --industry-series-kind PRODUCTION_INDEX --industry-sector-unit index_points --industry-target-name "Example target" --industry-peer-name "Example peer" --peer-companyfacts "C:/Data/peer-companyfacts.json" --peer-cik 0000000007 --peer-accession 0000000007-25-000001
```

For **direct original three-file mode**, replace `--sec-bundle` with `--sec-submissions C:/Data/submissions.json --sec-companyfacts C:/Data/companyfacts.json --sec-filing C:/Data/10k.htm --issuer-cik 0000000001 --accession 0000000001-25-000001 --as-of 2025-10-16 --collected-at 2025-10-16T12:00:00Z` (all example values fictional). For **Engine A**, add prior standard `--market-csv PATH --symbol NAME --benchmark NAME --return-basis PRICE_ONLY_CLOSE --market-source-url HTTPS_URL --market-published-at YYYY-MM-DD`. The previous manually prepared `--industry-json` mode remains supported, but **do not mix** it with any `--industry-sector-*` or new derived-mode fields. Repeat each `--industry-peer-name`, `--peer-companyfacts`, `--peer-cik`, `--peer-accession` exactly once for every peer in matching order (max 8).

On success, output JSON `industry_input_mode=LOCAL_ORIGINALS_DERIVED_NO_SAVE`, `industry_generated_sha256` (actual in-memory derived bytes), `industry_original_sha256=null`, `peer_sec_companyfacts_check` and existing Guard/Engine A/B/C summaries. No intermediate Industry JSON, raw original persistence, live HTTP or trading. On source mismatch, exit 2 with a sanitized blocked reason. An equal file SHA verifies only local byte identity, **not real issuer origin, industry license, vintage, comparable fiscal calendars, model accuracy or economic truth**. Industry release must not be earlier than its selected sector observation period end, nor later than `as_of`. The tool **does not invent** a quarterly alignment if authentic sector data are calendar-year based.

Exact synthetic CI #41230534239: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41230534239 (3/3 green, Python 1,191 PASS). Real sourced A/B/C E2E requires owner-supplied lawful originals and rights, plus separately approved provider GET if needed.

## P68 — Build Engine C industry input from local company and sector files

This is a NEW optional LOCAL tool for a user who already lawfully holds original target+peer SEC CompanyFacts JSON and a normalized sector CSV, NOT a downloader and NOT publisher authentication. It replaces manual JSON revenue/sha transcription with verified offline calculations and SHA pinning. All peers must have two annual periods with exactly the same end dates; no FX/fiscal calendar adjustment is invented. Each SEC file <=24MB; total financial originals <=48MB; normalized CSV <=1MB.

Normalized operator CSV must contain EXACTLY two rows and these two column names:

    period_end,value
    2024-09-30,200
    2025-09-30,240

These are SYNTHETIC EXAMPLE numbers, not economic evidence. The CSV values must come from a legally sourced primary publication; the program cannot verify that publication. The example below uses fictional SEC CIKs and records and MUST NOT be run unchanged. Replace each quoted path/name/accession and sector source URL/date/period with real values:

    python -m proofinvest.industry_packet_builder --target-companyfacts "C:/Data/target-companyfacts.json" --target-cik 0000000001 --target-accession 0000000001-25-000001 --target-name "Example Target" --peer-companyfacts "C:/Data/peer-companyfacts.json" --peer-cik 0000000007 --peer-accession 0000000007-25-000001 --peer-name "Example Peer" --industry-csv "C:/Data/industry-normalized.csv" --sector-source-url "https://example.org/actual-publisher-source" --sector-published-at 2025-10-15 --industry-name "Example Industry" --series-name "Example Output Index" --series-kind PRODUCTION_INDEX --sector-unit index_points --as-of 2025-10-16 --prior-end 2024-09-30 --current-end 2025-09-30 --output-json "C:/Data/new-industry-vision.json"

Repeat the four --peer-companyfacts / --peer-cik / --peer-accession / --peer-name flags in the same order for each peer (1–8). The tool reads bounded original local bytes, calculates annual revenue from selected same 10-K, checks sector two-point numerics/dates, derives SHA for each file, calls the existing Industry Vision+P66 raw-source gate and then exclusively CREATES a new JSON (exit 2 if filename already exists; no overwrite). Generated kuodra.industry-vision.v1 is uploadable to the existing P67 localhost Engine C interface with the matching SEC originals and to real_data_preflight --industry-json. It does NOT persist any raw issuer originals, send HTTP/AI calls, store Guard audit or place private data on GitHub.

The reported sector publication URL/date is user-asserted; CompanyFacts URL and filing date are not true API snapshot custody. No issuer/market publisher provenance, licensing, historical point-in-time vintage, FX/GAAP peer normalization, corporate actions, future earnings or investment recommendations are proven. Real-data validation remains blocked until lawful original source files and rights are available. Synthetic exact-feature CI: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41228921594 (3/3 success, 1,185 Python PASS).

## P67 — Localhost Engine C raw peer upload and downloadable evidence

The existing localhost-only user workflow can now verify **the same P66 peer CompanyFacts evidence** without CLI. After providing your SEC three original files, issuer, accession, analysis as-of, fiscal dates and unique 10-K quote, upload a valid Engine C industry/peer JSON. Then enable the checkbox `경쟁사 SEC CompanyFacts 원본 검산 추가 (로컬, 출처 미인증)`. For **every declared peer** (1–8), select its locally held original SEC-format CompanyFacts JSON and enter the exact 10-K accession. Each file may be up to 24MB, total peer originals up to 48MB. Nothing is sent to SEC, Gemini or an external vendor. As usual use Preview → explicit consent to ephemeral SQLite → Guard.

When requested, the peer gate must pass for Engine C to appear in the downloaded JSON and HTML. The report records each peer's original local CompanyFacts SHA-256, 10-K accession and computed annual revenue growth, with source origin/data rights and PIT historical vintage **all unverified**. If any peer original is absent, changed, misdated, wrong issuer or has a conflicting number/hash, Engine C and the peer receipt are **excluded** from the report; the previously verified target SEC Guard/HOLD/REJECT and temporary audit are unchanged. HTML output rechecks receipt identity/digest/amounts and escapes all caller text.

This is an additional local interaction for P66, not independent SEC publisher authentication. It was validated with synthetic files in Playwright Chromium via exact code SHA `b3460de10a26c7507e57e9b197b55522d3009921`, CI #41226880981 3/3 green, Python 1,180 PASS. Genuine real issuer/peer raw bytes, legal market/sector prices and original-data vintage are **NOT** established. For UI launch keep `KUODRA_ENABLE_LOCAL_SOURCE_UI=1` and `--server.address=127.0.0.1`; do not publicly expose uploads.

## P66 — Validate Engine C competitor growth against local SEC CompanyFacts originals

By default KUODRA keeps the older offline A/B/C preflight intact; uploaded industry JSON contains operator-declared peer revenues and is NOT independently authenticated.

To **opt in** to raw-byte checks for peers already declared in `--industry-json`, append the following THREE flags for **each** peer (up to 8) to the existing `python -m proofinvest.real_data_preflight` command with `--sec-bundle` or direct SEC 3 source files:

```text
--industry-json C:/Data/industry.json --peer-companyfacts C:/Data/peer_1_companyfacts.json --peer-cik 0000000007 --peer-accession 0000000007-25-000001
```

The above CIK/accession are **synthetic placeholders**. Repeat the three peer flags for every declared peer; mixed/incomplete coverage is blocked. All peers are currently required to share the exact prior/current period-end dates in the supplied industry JSON. This intentionally fails closed on mismatched fiscal calendars; different issuer calendars require an approved alignment strategy before claiming comparable market growth.

Each peer's raw SEC-format CompanyFacts JSON is read locally (regular file only, no symlink, max 24MB each, max 48MB aggregate). The existing SEC annual revenue parser validates issuer CIK, selected 10-K accession, filing/as-of, period continuity and complete USD revenues. The exact file SHA must equal both that peer's previous and current source SHA values in industry JSON; both claimed source URLs must be `https://data.sec.gov/api/xbrl/companyfacts/CIK<PEER_CIK>.json` and claimed published date must match the selected filing date. Neither the URL claim nor local SHA certifies provider origin, timestamp, historical vintage or distribution rights. A successful report adds `peer_sec_companyfacts_check` with peer count, filing, digest and matched revenues; all authentication and rights flags remain false.

Malformed/changed/contradictory files, unaligned periods, missing peer or wrong hash return `status=blocked`, `reason_code=PEER_COMPANYFACTS_CHECK_BLOCKED` and CLI exit=2; the temp SQLite audit is destroyed. Do NOT automatically accept failing peers or substitute other companies. This feature performs **zero SEC GET, vendor calls, database retention or trades**, and was tested with synthetic SEC-shaped bytes only. It is ready for owner-provided genuinely sourced file validation, NOT a real-data certification.

## P65 — Optional Apple 2025 original 24-cell gate in the complete offline A/B/C preflight

Apple statement-table checking previously existed as a separate CLI/UI (P58–P63), while the read-only real-file preflight (P49/P51) independently evaluated the same SEC original against SEC-derived numbers and optional market/sector evidence. P65 connects those paths **only when explicitly enabled**, preserving existing behavior for other issuers and users without Apple original HTML.

Append `--apple-10k-24-cell-check` to an existing `python -m proofinvest.real_data_preflight` invocation with real, lawfully held `--sec-submissions`, `--sec-companyfacts` and `--sec-filing` inputs (or a valid existing `--sec-bundle`). It requires all five exact target fields: `--issuer-cik 0000320193`, `--accession 0000320193-25-000079`, `--as-of 2025-10-31`, `--prior-end 2024-09-28`, `--current-end 2025-09-27` and existing `--collected-at`, `--needle`. On a structurally valid file, the existing SHA-256 of the original filing is reused and 24 FY2025/FY2024 numeric values across income, balance and cash statements are checked against P57 manual issuer-manifest values; the full SEC/Guard + optional Engine A/C process continues after this check. The receipt includes `apple_10k_original_table_check` with computed original SHA-256, 24 matched cells and **source_authenticated=false**; it does not retain the original or certify genuine issuer bytes.

A malformed, inconsistent, wrong-identity or missing original 10-K returns **exit 2** with `APPLE_10K_24_CELL_CHECK_BLOCKED` and no raw byte/path leakage. The optional mode does not establish third-party issuer authentication, data rights, actual SEC source or valid historical price vintage. Source verification and licensed market/sector inputs remain necessary even if all checks pass.

A non-Apple original follows the unchanged preflight when the flag is absent. The new tests in `tests/test_real_data_preflight_apple.py` use **constructed synthetic HTML**; passing those tests is not an Apple/SEC real-byte demonstration. The first legally supplied genuine original may reveal layout variants and must be run through the real parser with an independently recorded byte SHA.

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
