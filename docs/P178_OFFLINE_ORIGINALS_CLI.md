# KUODRA P178 — local SEC + stock + genuine NDX evidence command

A Windows/Linux/macOS Python 3.11 **offline** command for an operator who **already legitimately possesses** the original inputs. P178 does not buy, fetch or authenticate any source or permit public reuse. It is a reliable non-UI path for generating *two redacted reports* from six required originals, with optional Engine A/C local inputs. Unlike the existing Streamlit download button, this can run without a browser or an external API key, and it fails before writing any file unless the complete original-source replay is accepted.

Example (paths are local files; the output directory **must not exist**):

```sh
python -B -m scripts.local_originals_review_cli \
  --ticker NVDA --as-of 2026-02-01 \
  --ticker-map ./inputs/ticker-map.json \
  --submissions ./inputs/submissions.json \
  --companyfacts ./inputs/companyfacts.json \
  --original-10k ./inputs/original-10k.html \
  --stock-daily ./inputs/stock.json \
  --ndx-daily ./inputs/ndx.json \
  --market-json ./inputs/market.json \
  --industry-json ./inputs/industry.json \
  --output-dir ./new-kuodra-review
```

The `market-json` and `industry-json` files are optional but unknown metrics are never synthesized. The user-provided actual benchmark must be **Nasdaq-100 NDX**, not QQQ/SPY or a renamed ETF. The command uses existing strict A/B/C+Guard HOLD mathematical engine, recomputes independent SEC/stock/NDX source hashes and verifies canonical evidence before writing. Any invalid original, file symlink, oversized file, incorrectly paired filing, unbalanced index, or a pre-existing output directory is rejected. After validation it creates a **new** private output folder with just `kuodra-offline-a-b-c-review-UNVERIFIED.json` and `kuodra-source-rights-GAPS-UNVERIFIED.json`. There is no overwrite, network request, local cache/SQLite write, SEC P105 retry, external AI call or trade.

For independent verification of the paired reports, run:

```sh
python -m scripts.source_clearance_cli \
  ./new-kuodra-review/kuodra-offline-a-b-c-review-UNVERIFIED.json \
  ./new-kuodra-review/kuodra-source-rights-GAPS-UNVERIFIED.json
```

**CRITICAL:** PASS establishes **local exact-byte consistency** only. The operator is responsible for publisher origin and captured source, data-as-of/vintage validity, vendor subscription and NDX/peer rights, permitted derived display/redistribution, and human review. `source_authenticated`, `source_rights_verified` and `external_sharing_allowed` remain **false** even on PASS. Never commit owner original/secret or redistribute a reviewer packet without separate clearances. Public Production and the official DAKER upload remain HOLD and require separately explicit approval.

CI independently executes `python -B -m scripts.local_originals_review_smoke` on GitHub Windows-latest and Ubuntu, using **temporary synthetic raw source files only**, plus the full Python regression set and existing Chromium/Guard/Docker tests. User's physical Windows 10 and genuinely licensed original input are **not** tested by synthetic CI.
