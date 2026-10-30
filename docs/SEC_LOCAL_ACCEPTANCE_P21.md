# KUODRA P21 — Windows local SEC three-file acceptance

This is an **offline read-only** check of already obtained SEC-shaped inputs. It does **not** collect any SEC data; it does not persist copies, a receipt, screenshots, an audit SQLite database or any API key. It does not independently authenticate an issuer. Do not upload original filings to a public GitHub branch.

## Prepare

In the existing `lead/kic` checkout, run `git pull --ff-only` and check Python 3.11 is on PATH (`python --version`). Put the three independently obtained files in one local folder:

- `submissions.json` — unchanged Submissions JSON for the issuer CIK.
- `companyfacts.json` — unchanged **full** CompanyFacts JSON, not the single-concept CompanyConcept response or a curated report.
- `original.html` — unchanged issuer 10-K filing HTML for the selected accession; filename can be overridden with `-OriginalFile`.

Know the 10-digit CIK, `##########-##-######` accession, desired historical `-AsOf` date, and the **actual known collection/observation UTC timestamp**. A made-up historical `-CollectedAt` is not evidence. If collection time is unknown, report it as unknown and DO NOT fabricate one; this CLI requires an explicit timestamp to test the existing historical as-of gate. All source paths remain local. Real data cannot pass unless it meets existing strict source/period checks.

## PowerShell invocation (repository root)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\verify_sec_local.ps1 `
  -SourceDirectory "C:\SEC-local" `
  -Cik "0000000001" `
  -Accession "0000000001-25-000001" `
  -AsOf "2025-10-16" `
  -CollectedAt "2025-10-16T12:00:00Z" `
  -OriginalFile "filing-10k.htm"
```

**The illustrative CIK, accession and timestamp in this command are synthetic test values, NOT a real issuer. Replace them with verified locally held metadata.** Use `-SubmissionsFile`, `-CompanyFactsFile` and `-OriginalFile` when local filenames differ; these options accept filenames only, not directory traversal. Spaces and Korean characters in the parent folder path should be passed inside double quotes.

The command prints JSON to the console only: `status=operator_review_required` with fiscal pair candidates, SHA-256 and optional iXBRL compatibility, or `status=blocked` and a reason code. Exit 0 indicates **only** reviewable untrusted local structure; exit 2 means blocked. No trade or recommendation is authorized. If supplying results in chat, copy only the JSON **after inspecting it**, not the source contents, private path, user contact or confidential data.

## What does not constitute success

An independent source provenance/right-to-use check, authentic original-to-accession linkage, actual browser render visibility, Gemini live proposal, investor-risk verification, and Production remain outside this test. P21 CI uses synthetic fixtures on hosted Windows; a real SEC trio is still a separate owner-led acceptance gate. There is **no requirement to run this** until the three source files have been obtained through permitted means.
