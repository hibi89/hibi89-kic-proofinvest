# KIC — bounded public three-scenario judge replay artifact

## Status (2026-10-24 KST)
**IMPLEMENTED_VERIFIED** — an actual GitHub Actions artifact that a mobile user/reviewer can obtain from a completed CI run without executing local Python. This artifact is evidence of three *offline manually transcribed* arithmetic scenarios; it is NOT KIC official submission confirmation, a live AI Agent, an official DART document receipt, or proof of source re-authentication.

## Concrete source, command and generated artifact
- GitHub repository: `hibi89/hibi89-kic-proofinvest` branch `lead/kic`.
- Code commit: `0255dc672b2c3fe6f76f4984b6c40b2b71062f24`; changed `.github/workflows/ci.yml`, `scripts/public_judge_artifact.py`, `tests/test_public_judge_artifact.py`.
- CI: https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40101393570 **COMPLETED/SUCCESS** (209/209 tests PASS).
- **Observed actual artifact**: `proofinvest-public-judge-replay`, artifact ID **12562706988**, archive size **497 bytes**, `expired=false` at inspection, `retention-days: 14`. The earlier `proofinvest-synthetic-demo-recovery` artifact is separately available in the same run, ID **12562223870**. Artifacts are ephemeral, not permanent repositories.
- CI creates `/tmp/kic-public-judge-replay/judge-replay.json` by `python -m scripts.public_judge_artifact <path>`, validates it with `--verify`, and uploads only the JSON through `actions/upload-artifact@v4`. No private PDF/PPTX, private Library files, credentials, environment variables, raw issuer filing or other workspace files are in the public receipt.
- **Mobile steps**: open linked CI run → Artifacts section → `proofinvest-public-judge-replay`. GitHub access/sign-in may be required by platform; do not invent a direct file URL. Inside zip is a single JSON receipt.

## Why this method
- Option A: CI test logs only — no portable structured result and difficult to inspect/compare on mobile.
- Option B: upload full financial/PDF/project directory — unacceptable scope, private-material exposure and rights risk.
- **Option C selected:** exact allowlisted JSON projection (three cases + pinned previously-reviewed public JSON Git blob) with explicit false flags and strict maximum 2048-byte JSON content. CI artifact size observed 497 bytes is ZIP compression, distinct from uncompressed JSON bound.
- The JSON `verified` string is **arithmetical agreement with previous manually transcribed data only**, never issuer-document authenticity. All three cases `risk=withheld`; external DART, AI execution, official submission false. No current-year claims or portfolio ranking.

## Test plan & actual evidence
- Added **6 tests** for fixed scenarios and unauthenticated flags, exact public allowlist and size limit, receipt mutation/extra-field rejection, upstream false-live flag tampering, new-file create+verify and overwrite rejection, missing receipt rejection.
- [GitHub Actions #40101393570](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40101393570) reports **209/209 unittest PASS, 0 FAIL**, master 60-day progress check PASS, renderer check PASS, synthetic ZIP/snapshot backup PASS, `Generate bounded PUBLIC judge replay receipt` PASS, `Archive PUBLIC manual judge replay receipt` PASS.
- The artifact list was independently read from GitHub Actions run `40101393570`; observed ID `12562706988`, size 497 bytes, not expired. No actual phone download was personally performed.
- Verified code/CLI checks are **not** DAKER account/participation rights, PDF upload authority, signed evidence or receipt proof.

## Scored supplemental task (separate from 60-day schedule)
| Evidence gate | Weight | Verified |
|---|---:|---:|
| Review existing CI and select public-only portable proof | 20 | 20 |
| Strict JSON projection + CI build/verify/upload | 35 | 35 |
| Six new regressions, 209-test CI success, artifact actually present | 30 | 30 |
| Documentation, recovery and supervisor handoff | 15 | 15 |
| **Total** | **100** | **100** |

- Remaining this supplemental task: **base 0h + reserve 0h**; actual hours **unmeasured**. This 100/100 is not overall KIC product readiness or a newly DONE date.
- **Canonical 60-day ledger unchanged:** 29 DONE / 3 BLOCKED / 28 NOT_STARTED, NEXT `2026-12-03` official shortlist result (future WAIT). DAKER October 25 participation/team leader 60% blocked, November 9 team leader final upload 60% blocked; DART October 30 official original filing 90% blocked; November 10 final contest submission NOT_STARTED.
- **Preliminary priority remains** participant-authenticated DAKER KIC page: verify team/individual status and team-leader authority, phone authentication if demanded, correct single 10-page frozen PDF (private), final submission enabled vs draft, and official submission-history `최종` receipt. Never submit, convert team or expose private files without user permission. Internal target Nov 10; official cutoff Nov 12 10:00 KST.
- Frozen private PDF/PPTX and six Library backups unchanged; no live OpenDART or LLM/agent E2E, no public web deployment, no independent browser screenshot audit.

## Rollback and expiry
- Previous verified code HEAD `f303ba15ac48b77b1df63bd1340af284473aa48f`; ordinary revert can remove the additional public artifact steps. No force pushes or changes to `main`.
- GitHub artifact expires after 14 days; if needed later, rerun permitted CI on unchanged code and check fresh artifact ID. Never claim the existing ID remains downloadable after expiry.
- The documentation-only follow-up commit needs its own successful CI before final handoff.
