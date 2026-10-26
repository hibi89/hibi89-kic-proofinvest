> **2026-10-27 LATER SMAX PREPROCESSING CHECK:** User delegated reusable Data Preprocessor to SMAX chief in existing PRIVATE `hibi89/SMAX@preprocessing` (branch existence independently verified). Existing original JS `frontend/site/csv-transform.mjs` and `frontend/site/sales-report.mjs` contain bounded CSV normalization, row preservation/review and calculation; universal preprocessor on preprocessing branch is **NOT verified ready**. For future KIC integration, use a narrow, versioned JSON/CLI artifact from SMAX, with source ID/hash/span, units/currency/fiscal period, validation state and review; Python `proofinvest` cannot directly import JS as a Python module. **No KIC prelim PDF/lead code changes, no import/publication, and no additional initial submission dependency.**

# KIC ProofInvest — Disclosure Lightning (external public-disclosure collector) module spec
**Owner decision: 2026-10-27 KST. Documentation only; integration not implemented.**
**User's intended name:** **Disclosure Lightning**, meaning "fetch public disclosures lightning-fast". Distinct from "Lightening". Existing source repository: PRIVATE \`hibi89/Bid_Owl\`, reversible isolated branch \`feature/disclosure-lightning\`. Internal blueprint: https://github.com/hibi89/Bid_Owl/blob/feature/disclosure-lightning/DISCLOSURE_LIGHTNING_BLUEPRINT.md (only accessible to authorized GitHub users). It is **NOT yet a separate renamed repo, deployed service or verified SEC connector**.

## Product positioning
Disclosure Lightning is ProofInvest's **external read-only disclosure-sourcing adapter** for global public-company research. It handles authorized SEC EDGAR and later other official issuers/regulators, returns original source evidence quickly and deterministically without silently mutating history. The "lightning" claim is about bounded incremental fetching and avoiding unnecessary network requests, not unrestricted scraping or verified fastest-in-world speed.

## Responsibilities
- Search/fetch with issuer **CIK** disambiguation, SEC \`submissions\`, \`companyfacts\`, selected source filing URLs/forms, fetch timestamps, accession numbers, amendment/revision relationships, source hashes.
- Track \`first_seen\`, \`last_checked\`, \`filed_at\`, \`published_at\`, \`collected_at\`, \`source_uri\`, as-of availability, origin and rights; preserve original raw file and revisions. Treat changed or incomplete data as UNKNOWN rather than silently inferred.
- Rate limiting, official SEC fair access/User-Agent, timeout/retry/backoff, caching/ETag when supported, idempotent duplicate detection, resumable checkpoints, read-only network retrieval.
- Output versioned \`RawFilingEnvelopeV1\` JSON manifest and a *reference* to original content; never insert financial ML scores or unverified claims into raw receipts.
- **External preprocessor boundary** after Lightning: normalize currencies/units/fiscal periods/form types/field aliases into \`NormalizedFactEnvelopeV1\` with source spans/quality states and transformation log. **Owner will ask SMAX if it already has preprocessing; until verified preprocessor implementation and contract remain OPEN / NOT A CURRENT PROJECT.** ProofInvest can instead parse a small SEC example in its own bounded proof path; do not block prelim PDF on preprocessor.

## Proposed schema (no implementation claim)
\`\`\`json
{
  "schema_version": "1.0",
  "provider": "SEC_EDGAR",
  "issuer_cik": "0000000000",
  "accession": "PLACEHOLDER",
  "form": "10-K",
  "filed_at": null,
  "published_at": null,
  "collected_at": null,
  "source_uri": "OFFICIAL_SOURCE_URL_REQUIRED",
  "raw_sha256": null,
  "as_of_cutoff": null,
  "amends_accession": null,
  "evidence_status": "NOT_VERIFIED"
}
\`\`\`
This is a format illustration; it contains NO actual SEC record.

## KIC ProofInvest integration
\`\`\`text
Official SEC EDGAR -> Disclosure Lightning (raw acquisition/index)
                         -> optional validated preprocessor (undecided)
                         -> ProofInvest existing Research/Verification/Risk
                         -> evidence-linked capital/shareholding + financial peer analysis
                         -> [finalist only] evaluated ML, pretrained financial document DL
                         -> source-grounded due-diligence report
\`\`\`
Use a **JSON/file contract or read-only local API**, not an import of the whole Bid Owl procurement app. KIC public contest source must not embed private Disclosure Lightning code until owner explicit rights and disclosure decision. Actual external source and preprocessor require compatibility and end-to-end independent tests.

## Priority and hard boundaries
- **Nov12 KIC prelim**: list Disclosure Lightning as one planned modular acquisition tool in the KIC architecture and note its actual status "design-only". Do NOT write SEC collector, import it, rename Bid Owl repo, create preprocessor, reformat private KIC PDF, or train ML/DL merely because this page exists.
- **Only if Dec03 finalist:** implement/test approved official SEC source in Lightning isolated branch, record provider evidence with correct fair-use, link 1–2 real companies end to end, resolve preprocessing through SMAX feature if VERIFIED or minimal local parsing fallback; ML/DL separately tested; preserve original source and provenance; report measured fetch performance, not hypothetical.
- Official KIC prelim exact PDF and participant submission approval remain separate. No original PDF changed. This doc is not a claim of running application.
