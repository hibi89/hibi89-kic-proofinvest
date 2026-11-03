# P169: lawfully held stock and Nasdaq-100 CSV, offline only

**2026-11-04 KST · KUODRA `lead/kic` · RELEASE HOLD**

## What changed

KUODRA P167 previously needed a stock and NDX `Alpha Vantage`-shape JSON pair to create the initial redacted A/B/C packet. P169 additionally accepts **a locally selected stock CSV and index CSV** (two files together). This is not a new market-data provider, auto-fetch, scraper or free-license entitlement. If legitimate data is already held in permitted CSV form, no external request, purchased index API, API key or provider data transmission is necessary to reproduce the numerical workflow.

The exact UTF-8 CSV grammar is:

```csv
symbol,date,close
NVDA,2025-11-03,100.25
NVDA,2025-11-04,101.20
```

The header must be exactly `symbol,date,close`. Use **31–100 ascending unique trading weekdays** with canonical `YYYY-MM-DD` dates no later than the selected `as_of`. Every stock row must repeat the requested ticker. Each actual Nasdaq-100 index row must repeat `NDX` (never QQQ, SPY, another ETF/index, or a synthesized substitute). `close` is an unadjusted price-only positive decimal string; the pipeline does not silently use adjusted close, infer splits, resample dates, fill market holidays, interpolate missing prices, or claim vendor authenticity. Inputs with extra columns, invalid rows, future dates, duplicate or missing-day gaps, malformed numeric data or unpaired JSON+CSV uploads fail closed.

This example has **only two illustrative rows and cannot pass production validation**. An eligible real local file needs at least 31 valid rows. The analysis still requires the four SEC issuer source bytes, aligned issuer/filing/as-of, and legitimate Engine A/C auxiliary sources if included.

## Use the existing single-ticker local UI

In the **SEC 4원본 + 종목·NDX 로컬 입력으로 통합 보고서 최초 생성** section, either provide (A) stock JSON + NDX JSON, *or* (B) stock CSV + NDX CSV. Do not mix. Supply the four SEC originals, type one ticker and analysis date and explicitly acknowledge the data-rights warning, then click the original P167 **offline** initial A/B/C review button.

If the six input originals and the optional Engine A/C inputs replay successfully, all P167/P168 downloads remain available. In CSV mode, a **third** redacted file is created: `kuodra-csv-lineage-UNVERIFIED.json` (original stock/index CSV SHA-256, locally converted stock/NDX JSON SHA-256 and exact A/B/C review packet SHA). The existing source-rights gap report's market SHA values refer to the **converted JSON bytes**, *not* to the CSV source bytes. The CSV lineage explicitly binds these conversions to the original CSV fingerprints, without containing individual market prices or provider tokens.

The lineage verifier `proofinvest.local_market_csv_bridge.inspect_csv_lineage_receipt(raw, packet=review_packet_bytes)` verifies internal report binding. It cannot reproduce the original CSV rows without those original files, and neither it nor a matching SHA grants legal rights. For original SEC and JSON price/index independent numerical replay, use P166 and the converted JSON bytes; do not replace required raw provider responses with arbitrary text.

## Usage and legal hold

Official Nasdaq states that index data used for benchmark performance needs an appropriate license; its [May 9, 2024 update](https://www.nasdaqtrader.com/TraderNews.aspx?id=DN2024-5) clarified that redistribution of Nasdaq Global Index data requires prior approval, including historical/end-of-day usage. [Alpha Vantage documentation](https://www.alphavantage.co/documentation/) marks its INDEX_DATA endpoint Premium. **This adapter is not a means of obtaining data, evading subscriptions or making a copyright-restricted CSV distributable.** Confirm index and stock source licenses, account entitlement if applicable, attribution/derived-data display and redistribution before any actual external deployment or official submission.

Source authenticity, acquisition timestamp, historical vendor vintage, license validation, representative industry cohort and publication rights remain **UNVERIFIED**. Guard policy stays **HOLD**, no trade, no real SEC GET after prior 403, no paid market call, no background fetch and no automatic contest submission. The original frozen KIC preliminary PDF is not modified.
