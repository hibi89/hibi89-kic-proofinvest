# DL feature → KIC lead selective integration audit (2026-10-30 KST)

**Immutable comparison:** KIC \`lead/kic@ee5addb5e91a12e1e9768460cfcfdf01d4eae9f2\`; DL \`feature/disclosure-lightning@760ddd3a0e4ad5814e76146c0d536bebc4520f81\`. Different \`core.py\`, \`originals.py\`, SQLite contracts and time/as-of semantics. **Do not merge branches wholesale.** All data here remains locally supplied/unverified; no live SEC requests or rights approvals.

| Feature-only DL file | Existing KIC equivalent | Judgment | Work / gate |
| --- | --- | --- | --- |
| \`companyfacts.py\` | \`proofinvest/sec_companyfacts.py\` deterministic revenue checks and \`sec_three_source.py\` bounded 3-source opt-in (no durable HTTP cache) | **PARTIAL OVERLAP / DEFER FULL CACHE** | Full DL adds ETag, conditional GET, independent index/DB and SHA versioning; requires the newer DL core/schema, SEC-usage contract and provenance testing. No reason to overwrite current KIC 3-source behavior for preliminary PDF. |
| \`extract.py\` | \`dl_source_span.py\` anchors exact raw string but does not establish whether string is in HTML body text; \`numeric_literal_anchor.py\` checks numbers only | **SELECTIVE ADAPT** | KIC-owned \`visible_text_evidence.py\` checks exact UTF-8 HTML text-node byte span, denying script/style/attributes/comments while preserving current raw archive. Offline tests and negative trust flags; no full DL extraction/DB APIs copied. |
| \`history.py\` | \`disclosure_lightning.core\` recently indexed submission window only | **DEFER** | Older 10-K history/manifests, accept-time filtering and revisions useful only if legally sourced/as-of reproducible. Needs pinned manifest ledger and schema absent from KIC; migrating alone risks release-time leakage. |
| \`xbrl.py\` | \`ixbrl_revenue_review.py\` strict bounded XHTML revenue context/unit/period; \`numeric_literal_anchor.py\` | **PARTIAL OVERLAP / DEFER GENERAL FACTS** | DL general candidate extractor is unverified HTMLParser-based, broad tags/contexts; KIC has narrower fail-closed revenue check. General XBRL mapping requires robust period/unit/taxonomy, provenance and dedicated tests. |

## Engineering alternatives evaluated

1. **Whole feature merge:** most coverage now, highest conflict and schema/regression risk; higher maintenance and CI cost. **Reject.**
2. **Selective KIC-only text-node check:** smallest security/evidence value without changing SEC network/DB contracts; bounded offline CPU and no API cost. **Selected.**
3. **Defer all four until finalist:** lowest cost but retains risk of raw source span referring only to script or HTML attributes; less reliable citation quality. **Reject that one narrow gap, otherwise defer.**

## Accepted limited behavior

\`build_local_sec_review_packet\` includes \`source.html_text_node_literal_check\` and still returns its original raw archive/verified-bytes metadata. A positive result proves *only* that the already pinned ASCII phrase occurs inside a decoded UTF-8 HTML text node and matches its original byte offset. It does **not** prove browser-rendered visibility, SEC authenticity, issuer financial truth, XBRL period/unit, rights, or a trade decision. Negative/ambiguous/invalid HTML input returns \`unavailable\`; no trust flag is elevated. For prior consumers, original schema and existing keys are preserved.

## Verification and restrictions

Run \`python -B -m unittest tests.test_visible_text_evidence tests.test_local_sec_packet -v\` then existing full verifier. GitHub Actions PASS must be recorded by exact code commit SHA. This audit does not permit copying private Bid_Owl code, live requests, a new dependency, altering the private approved PDF, or DAKER submission. The 2026-11-12 10:00 KST <=10-page official preliminary submission is an independent gate; adaptive macro factors remain finalist-only design.
