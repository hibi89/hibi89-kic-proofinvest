# P193 — Publisher-hosted Apple FY2026 10-K document discovery (free, 1 shot)

The official Apple Investor Relations FY2026 listing is retrieved via
HTTPS with redirects disabled, at most one GET; its 2026 10-K anchor must be
unique and resolve to an allowlisted first-party source or publisher-linked CDN.
Only then is a single additional size- and MIME-bounded public document GET
permitted. SEC.gov is NEVER called. No retries, source bytes saved, secrets,
paid API, uploads, external AI, trades or DAKER/Production changes.

Output is a redacted receipt with request counts and SHA256/byte size/URL only
on success. Because an issuer-linked URL alone cannot authenticate SEC-hosted
EDGAR raw bytes, the original SEC/NDX/stock/peer acceptance points stay HOLD
without further independent provenance and data use/rights verification.

This source-check workflow is path-triggered only for this workflow's initial
addition, not for ordinary application commits. Any first failure is final
for this probe; do not repeat without a materially different approved method.
