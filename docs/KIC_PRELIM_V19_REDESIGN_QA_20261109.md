# P284 — KUODRA V19 content+design review, 2026-11-09 KST

## Why V18 was not enough
V18 contained technical components and CI records but lacked a clear value bridge between (1) KIC's global issuer investment research/peer comparison/risk scrutiny; (2) KUODRA original/source-period checks, A/B/C, Guard and audit; (3) what the KIC analyst would receive; (4) proposed read-only interface and authoritative human decision boundary. Existing decorative English and dense styling made review harder. KIC actual public process: https://www.kic.kr/ko/investment/process and https://www.kic.kr/ko/investment/risk-management, aligned as a product PROPOSAL, not real internal KIC systems access.

## V19 content and implementation
Preserved V18 editable template-origin PPTX; used same 16:9 package/theme and 10 slide structure, rebuilt shapes/text/diagrams as **editable PowerPoint**. Official 7 KIC preliminary headings retained within 10 page PDF. All headings and practical explanation predominantly Korean; retained only named technologies and file interfaces (SEC, Qwen, GitHub, JSON/HTML).

New slide mapping:
1 cover readable Korean value proposition;
2 summary: 3 concrete KIC deliverables (source-linked numeric checks, missing/conflicting evidence and human review, auditable report);
3 Apple FY2025 30% hypothetical claim vs **manual curated** 6.43% mismatch illustration, explicitly NOT publisher-byte authentication;
4 proposed KIC research, peer-comparison and risk/committee workflows with concrete human deliverables + file read-only -> JSON/HTML -> internal review attachments; future internal API requires owner/security approval;
5 execution order: four SEC-shaped objects, seven-stage real offline replay, limited A/B/C, HOLD/REJECT, optional consented Qwen only AFTER original workflow validated;
6 mapping of reusable OSS/frameworks Python/Streamlit/SQLite/Playwright/GitHub CI vs KUODRA's own bounded issuer proof, A/B/C, Guard and audit logic;
7 data/rights, amended filing, as-of / no lookahead controls;
8 December 3–22 real MVP acceptance stages and 10 countercases;
9 reviewable result mockup + metrics to actually measure, no fabricated productivity improvement;
10 exact code CI evidence vs unfinished SEC primary original, permitted stock/true index feed, full real A/B/C, public production and **no current KIC integration**; 4 clickable official references.

## Verification (finished artifact in conversation container, not uploaded to Library or GitHub)
- Editable PPTX `KUODRA_KIC_V19_REDESIGN_PRIVATE_REVIEW.pptx`: 104604 bytes; SHA256 `1b30f78e7a8c9f026ec5f9f340a203744b154bb9e0ba103b82857723ebeb8b12`.
- PDF `KUODRA_KIC_V19_REDESIGN_PRIVATE_REVIEW.pdf`: 299185 bytes; SHA256 `596d476f145e38aae85ccd241478f15a1df0401f37ef92fd39560fe8598c64ff`.
- ZIP `KUODRA_V19_REDESIGN_REVIEW_PACK.zip`: 1085948 bytes; SHA256 `4848e09dc30be7edec8758c74f85d85e19ca229d094afdc1db1bdfb2c2237443`, holds exact PDF, PPTX, QA markdown, 10-page montage PNG; zip CRC and exact byte equality PASS.
- Checks: 10 editable slides and 10 landscape PDF pages; 7 required sections present; 4 web link annotations; all 10 pages rendered/visually reviewed through contact sheet; individual pages 1/4/6/10 inspected; PDF text coordinates in page bounds 0 exceptions; no flat image-only slide output. Font Noto Sans CJK KR, navy/white/teal/limited orange for unmet rights, inherited KIC template origin.
- Existing V18 PPTX SHA256 `0624d695a8223dbbccce987ae8dd36f57d3bf1443feea963d52d12c1c4185534` unchanged; V15 Library backup unchanged.
- Official DAKER 10 page/7 sections: https://daker.ai/public/hackathons/kic-ai-agent-competition . No official DAKER submission or team-leader '제출 완료' action.

## System and release boundary
Product functional SHA `1f89ef7671f158307fbca35e78c621de54264fa1` with mandatory GitHub CI 6/6 SUCCESS, Ubuntu Python 2188 tests; last doc HEAD `c10b2fd723e296b751d156792dbcc131a4b15df7`. No new code or CI run; four optional actual-model jobs skipped in prior code run. KUODRA product **76/100 RELEASE HOLD**. Real SEC first-party 4-original downloaded bytes/issuer attestation not acquired, stock & true Nasdaq-100 AI/display/contest rights not obtained, complete real data A/B/C and public Production not verified; KIC internal systems not connected. V19 is private REVIEW CANDIDATE and no submission action was performed.

## Decision/backup/next
Two viable designs: incremental V18 cleanup (less work but fragmented storyline) vs new Korean-first editable layout with KIC-specific use cases (selected as user expressly disliked old aesthetics and value explanation). Existing artifacts preserved, no paid calls, secrets, external raw source transmission, deployment, permissions or provider GET. Next owner may visually choose V19 or request wording iteration. If approved, use candidate PDF for DAKER before 2026-11-12 10:00 KST; team leader must click '제출 완료' and verify '최종'. User does not have to re-run CI. Files currently downloadable in active conversation; NOT persistently backed up to Library, and documentation links are NOT file bytes.
