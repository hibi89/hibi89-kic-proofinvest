# KIC ProofInvest — three-scenario judge replay and reviewed-evidence freeze (2026-10-24 KST)

## Problem and objective
Previously the manual issuer example checked corporation ID, source URL and report year but did not bind the manually reviewed **JSON file bytes**. Someone could rewrite historical amounts and the stored growth calculation consistently, and still trigger a fresh 'verified' arithmetic result. It would not authenticate the original PDF and could misrepresent which manual record was reviewed.

## Decision (one independent offline hardening feature)
- **A: rely only on issuer/year/source URL** — unchanged source identity but silently accepts replaced amounts; rejected.
- **B: re-fetch issuer PDF or official DART every execution** — would need reliable external connectivity/rights, introduce unapproved new data access, and official DART direct viewer has remained blocked; deferred.
- **C (implemented): pin Git object's byte identity** for the reviewed public JSON, fail closed on all byte changes, and provide a deterministic one-command replay of three arithmetic claims. This is **integrity of a previously reviewed Git record only**. SHA-1 here is Git blob SHA-1, not a signature/authentication of the issuer PDF, independently proven publication, or an official DART receipt.
- `proofinvest/manual_case_demo.py` now verifies Git blob object SHA-1 `5535653a44297cc34022709be264801402688ecf` of `docs/evidence/samsung_2024_cfs_revenue.json` prior to every execution; any record replacement requires a separate human source review and justified re-baselining in Git. No record was modified.
- `proofinvest/judge_replay.py` composes three existing manual paths without LLM/API/network. It prints verdicts in a stable order and explicitly avoids unsupported balance-sheet Risk outputs. Optional `--json` emits machine-readable, **non-private** static public evidence metadata.

## Commands
From the full repository root on Python 3.10+:
```bash
python -m proofinvest.judge_replay
python -m proofinvest.judge_replay --json
```
Expected scenario outputs: `match: verified (manual arithmetic)`, `conflict: conflict`, `no_claim: unavailable`; all have `Risk=withheld`. A missing, tampered or silently revised reviewed record aborts; there is **no implicit fallback to synthetic values or automatic re-baselining**. No files are written.

## Verification
- New `tests/test_judge_replay.py` seven methods: three verdict states; false live/AI/submission flags; deterministic no-mutation output; altered revenue rejected; replaced source URL rejected; subprocess text/JSON; missing evidence rejected.
- New code SHA `79bdfc6e2a540d13698dcaf9939274178378e3b5` on `lead/kic`.
- GitHub Actions [40100217119](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40100217119): **COMPLETED/SUCCESS; 203/203 unittest PASS, 0 FAIL**, with canonical 60-day progress sync, Streamlit AppTest, synthetic snapshot save/read, synthetic-only ZIP build/extract/replay, original offline manual-data CI steps.
- Actual report bytes were NOT fetched from Samsung, DART or authenticated API during this run. The public repository's reviewed JSON stays frozen. No release/production deployment or mobile/local code execution took place.
- Rollback prior SHA `09fc0db78838cc21a5680038a8ac7ca792ff5c99` via ordinary Git revert; no forced pushes, secret or account mutations, paid resources, private PDF/PPTX export.

## Known limits, deadline priority
- Official [KIC rules](https://daker.ai/public/hackathons/kic-ai-agent-competition) say the **preliminary** work is a PDF AI Agent proposal at most 10 pages (2026-11-12 10:00 KST). The **finalist-only** stage requires a working demo URL, GitHub source and presentation PDF, with optional demonstration video. This task is an offline proof, NOT the mandatory finalist online demo and **not** a proven operational AI Agent.
- DAKER 2026-10-25 participant/team conversion/PDF authority **60/100 BLOCKED**; DAKER 2026-11-09 team leader upload capability **60/100 BLOCKED**. The authenticated account currently requires the user's browser context/possible phone authentication; no ability to verify final submit from this session and no upload or submission done. Separate explicit user approval required before final submission.
- DART original filing 2026-10-30 **90/100 BLOCKED**. Issuer statement metadata and manual arithmetic do NOT replace official accession-viewer confirmation.
- User private 10-page proposal PDF/PPTX and six Library backups remain frozen, unpublished. Intended 2026-11-10 early submit with written receipt; actual contest cutoff 2026-11-12 10:00 KST. The 2026-12-03 shortlist result check is future.

## Extra 100-point task score (NOT additional canonical calendar DONE)
| Gate | Weight | Verified |
|---|---:|---:|
| Investigate manually-reviewed record tampering & select pinning approach | 20 | 20 |
| Freeze exact file bytes, implement 3-scenario fail-closed replay | 35 | 35 |
| Seven new regressions / remote full 203-test CI | 30 | 30 |
| User instructions, QA & lead handoff | 15 | 15 |
| **Total separate work unit** | **100** | **100** |

Work unit **100%**, remaining base **0h** + contingency **0h** (these are not estimates for resolving external blockers); actual observed work time **unmeasured**. Canonical 60-day ledger is unchanged: **29 DONE / 3 BLOCKED / 28 NOT_STARTED**; 2026-12-03 NEXT WAIT. The follow-up docs-only commit CI must be checked independently.
