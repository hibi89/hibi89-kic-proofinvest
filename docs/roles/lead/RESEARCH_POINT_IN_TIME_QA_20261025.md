# KIC Research — point-in-time collection provenance guard (2026-10-25 KST)

## Reproduced structural gap
- `normalize_research` previously rejected a source with `published_at > as_of`, but accepted sources whose `collected_at` was **after the analysis `as_of` date**, and could accept a finding recorded **before its source was collected**. For historical as-of evidence this is look-ahead/temporal-provenance leakage. This is an offline synthetic-input defect, **not** a claim that a real DART record was falsified.
- A source published 2026-01-10, collected 2026-02-01, used as evidence for 2026-01-31 could be accepted before the fix. A claim as_of 2026-01-20 citing a source collected 2026-01-25 could likewise survive.

## Options and minimal change
- A (selected): Require `collected_at <= research.as_of` for each accepted source. For every cited finding also require the source's `collected_at <= finding.as_of`. Return warnings `future_collected` and `finding_precedes_collection`, keep rejected evidence outside accepted `sources`/`findings`.
- B (rejected): Require collection to happen exactly on the report/finding date; unnecessarily excludes historically collected, valid earlier sources.
- C (rejected): Online source re-fetch and current timestamp insertion; silently rewrites historical context, would need external authorization and changes the no-I/O contract.
- Code only in `proofinvest/research.py`; numeric Verification/Risk, existing output schema, URL and rights guards unaffected. Rejected sources are not treated as rights-denied and cannot be used by downstream chain.

## Synthetic offline regressions
- New `tests/test_research_point_in_time.py`: five tests for future collection rejection; finding before collection; collection on analysis date permitted; finding on collection date permitted; independent accepted source/finding survives partial rejection without mutating inputs.
- This is not live source authentication: accepted source/claim records remain caller-supplied, URLs are not fetched, licenses remain `not_established`.

## Source and CI
- Source commit `0359d0c259053af7c28d5e8db0589d905d223790`, previous baseline `f6cb84019e52dbd6f92e8f11a8e0da3620add71a`.
- CI run https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40110317704 — **completed/success, 244/244 unittest PASS, 0 failures/errors**; 60-day schedule guards, offline fixtures/demos and safe artifact workflow successful. Final documentation commit CI is a separate confirmation gate.
- No paid API, DAKER login/submission, user PDF/PPTX/Library 6 private draft change, or deployment.

## Progress and next external gate
- Separate unscheduled safety quality unit: reproduce+alternatives 20, fail-closed change 35, five regressions+CI 35, remote handoff+docs CI 10; 100/100 only after final docs-commit CI verified; remaining base 0h + reserve 0h after that, actual hours not measured.
- Canonical 60-day schedule unchanged: **29 DONE / 3 BLOCKED / 28 NOT_STARTED**. DAKER 10/25 **90% BLOCKED**, DAKER 11/09 **80% BLOCKED**, DART viewer 10/30 **90% BLOCKED**, 11/10 DAKER final submit **NOT_STARTED**.
- Before official 11/12 10:00 KST submission, user's separate permission is needed to enter final title/upload the frozen 10-page PDF/click final submit. The visible team-leader label does not prove final backend submission or receipt.
