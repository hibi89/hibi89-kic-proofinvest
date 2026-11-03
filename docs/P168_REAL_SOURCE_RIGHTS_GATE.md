# KUODRA P168 — live source rights and original-byte checklist (2026-11-04 KST)

## Purpose

To analyze one ticker in the real world, the reviewer must first obtain legitimately usable SEC issuer, stock, true Nasdaq-100 index and peer/sector originals. A replayed SHA or a successful A/B/C calculation **does not authenticate** a publisher, the acquisition time, paid entitlement or the right to display/redistribute figures. The local app never sets rights flags to true. No live SEC retry after P105 403, no premium GET before contract and owner authorization. Frozen preliminary V13 PDF and official submission remain outside this workflow.

## Separate the two offline artifacts

After supplying SEC original 4 files, company daily-price response JSON, **NDX** daily-index response JSON and optional Engine A/C local sources to the localhost single-ticker page, use **local first-packet creation** (P167) explicitly. It now produces:

1. `kuodra-offline-a-b-c-review-UNVERIFIED.json`: strict, redacted numerical A/B/C and Guard HOLD reviewer packet.
2. `kuodra-source-rights-GAPS-UNVERIFIED.json`: eight original-role SHA-256 fingerprints, issuer/filing/as-of/matched-window metadata, unresolved source rights and no external-use authority. It does **not** contain SEC HTML, stock/index close rows, API keys, account IDs or private source bodies.

A reviewer with these two existing files can check the pair without activating any provider or needing access to the originals:

```bash
python -m scripts.source_clearance_cli kuodra-offline-a-b-c-review-UNVERIFIED.json kuodra-source-rights-GAPS-UNVERIFIED.json
```

Exit **0** = internally linked, canonical files with all external rights still pending; exit **2** = malformed, mismatched or corrupted receipt. Neither exit code grants public display rights, certifies a publisher, executes Guard, or approves trade/contest release. For stronger independent original-byte replay, P166 requires all eight raw inputs to be supplied again; the downloaded pair alone is insufficient.

## Official supplier research and decision gates

| Source/path | Checked official facts | Pre-release action |
|---|---|---|
| Direct SEC `data.sec.gov` | Prior P105 HTTP 403; no retry/bypass authorized. | **Do not attempt** direct SEC HTTP; only use operator-possessed legitimate originals or separately approved licensed provider. |
| Alpha Vantage stock daily / `INDEX_DATA` | `INDEX_DATA` for actual index symbols is listed as **Premium** in supplier documentation. The free key cannot be assumed to include it. | Owner approval of account, entitlement, query cap, charges and specific display/derived-data license **before** a real GET. Offline JSON shape is not proof of acquisition or rights. |
| FRED `NASDAQ100` | Nasdaq, Inc. is the source; FRED page flags **copyright**. FRED terms require contacting the third-party rightsholder for non-personal usage and include broad restrictions on FRED content in connection with software/AI development. | **Not** a drop-in free KUODRA AI/commercial data source. Obtain appropriate authorization and legal review first. The P167 raw NDX parser does not import FRED CSV. |
| Same-industry peer/sector evidence | One company or unverified sector dataset is not a representative industry sample. Publisher-period and reported units must match issuer/as-of before Engine C inference. | Preserve `UNAVAILABLE`/unverified where missing; do not manufacture industry growth, optimistic investment recommendations, or representative market share. |

Official references, not reuse licenses:
- [Alpha Vantage official API documentation](https://www.alphavantage.co/documentation/)
- [FRED NASDAQ100 index source/copyright notes](https://fred.stlouisfed.org/series/NASDAQ100)
- [FRED service terms and proprietary data/AI restrictions](https://fred.stlouisfed.org/legal/terms/)
- [SEC EDGAR overview](https://www.sec.gov/edgar/about)

## Evidence needed before a genuine external release

Record separately, without placing any secret/token or raw private evidence in GitHub: (a) issuer's exact primary publication URL, accession/CIK, fiscal period/units, and controlled retrieval date; (b) market provider's legal identity, exact NDX benchmark symbol, paid entitlement contract and index display/derivative/redistribution scope; (c) actual raw source SHA and observation dates bounded by analysis as-of, including corrections/vintage; (d) peer-company membership and representative sample limits; (e) written owner approval for extra charges, external file transfers, domain/security changes and KIC/DAKER upload. Source metadata self-reported by an operator remains unverified until its independent acquisition evidence is inspected.

Until all gates are satisfied: **RELEASE HOLD, source_authenticated=false, source_rights_verified=false, external_sharing_allowed=false, Guard HOLD, no trade, no official contest submission**.
