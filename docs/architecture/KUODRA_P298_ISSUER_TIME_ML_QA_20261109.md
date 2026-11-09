# P298 — KUODRA issuer/time out-of-sample ML validation (2026-11-09 KST)

## Implemented backend
- `proofinvest/kuodra_group_time_ml.py`: read-only canonical long records -> select one or more contemporaneously available features per issuer -> label from next observed timestamp -> issuer-disjoint holdout at later calendar time. Chronological CV on training issuers only, with released-label embargo for every fold and final fit; sklearn Ridge+StandardScaler vs DummyRegressor, chosen by training CV, untouched holdout MAE.
- Wrapper `evaluate_owner_local_group`: reuses existing owner-scoped `OwnerLocalGateway` ACL before copying a PRIVATE dataset.
- Wrapper `evaluate_owner_local_hybrid_group`: reuses `_build_joined` so PUBLIC+PRIVATE exact-key join and both dataset ACLs execute *inside the owner-local process*, returns guarded aggregate analysis only. No public or external service / new paid API.
- Explicit `NO_TRAIN` on insufficient issuer/time/embargoed observations, late features, no optional sklearn; all positive findings `HOLD`, no causal/probability/finance accuracy claim.

## Actual local test evidence
Command: `cd /mnt/data/kic_patch && python -m unittest discover -s tests -p 'test_kuodra*.py' -q`.
Result: **73/73 PASS** on local Linux **Python 3.13.5**, with sklearn 1.8.0; prior P297 was 63/63. New 10 tests cover disjoint issuer + later-time holdout, negative label control, late-label and future-feature NO_TRAIN, minimum groups/timestamps, lineage/units/target tampering, owner ACL/denial, synthetic PUBLIC+PRIVATE hybrid E2E and a mocked socket call. Positive synthetic fixture: train 360/holdout 30; Ridge vs Dummy +97.798% holdout MAE reduction; unrelated label fixture selects Dummy (0% improvement). **Synthetic performance is deliberately not evidence of financial predictive lift.**

## Verification boundary / known limits
- GitHub `lead/kic` new source commit `c3a0a9e09f9f51ff1ab4b2b958944cbde0a03e8f`, new tests `8449df7952759ec414fb0c31d46728254cb2a067`. GitHub read-back of both files PASS. Test file blob matches local; remote source blob differs from local working file by 52 characters, so full byte-identical remote execution has **NOT** been proven and is awaiting exact-SHA CI.
- Repository full Python 3.11/Windows CI **UNVERIFIED**: GitHub combined status returned empty statuses; available workflow-run connector only lists PR-triggered runs and returned empty. Empty != CI pass/fail. Container cannot fetch entire repo from GitHub over HTTPS.
- This is **not** an institution-approved trusted principal, OS/firewall no-egress isolation or hardened document parser. No real private data, secret, paid feed, live SEC GET, production deployment or official filing.
- Host-authenticated issuer identity, time-series regime shift/survivorship bias and calibration not solved; no export outside owner-local process.
- Rebaseline engineering estimate from P297 **51/100 to P298 53/100**, credit only +2 in Analytics (9/20 -> 11/20) for actual synthetic issuer + temporal holdout, still RELEASE HOLD.

## Next critical path
Backend first through 2026-11-10: exact remote-source reproducibility, whole repo Python3.11 CI, isolate private execution under trusted host (NOT self-asserted `authenticated_by_host`), source-linked local HTML/JSON restricted evidence report and human approval. No lawful real source/institution access claim. Preliminary ten-page PDF final edit scheduled 2026-11-11; DAKER team-leader upload+confirm by 2026-11-12 10:00 KST; NOT SUBMITTED.
