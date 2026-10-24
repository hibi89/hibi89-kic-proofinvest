# KIC Verification — same-statement duplicate-account fail-closed review (2026-10-24 14:02:36 KST)

**Implementer/reviewer:** KIC lead, `hibi89/hibi89-kic-proofinvest@lead/kic`.

## Actual changed code
- Implemented: `proofinvest/engine.py` `parse_accounts` detects repeats of the same normalized account key **within the selected FS only** (CFS preferred). It discards the metric on the second appearance and remembers the ambiguity to avoid treating the third row as a fresh valid account.
- `tests/test_engine.py`: five new synthetic offline regressions. Reject differing duplicate revenue; reject identical duplicate revenue; reject 3+ duplicates; reject duplicate liabilities from risk ratio; leave selected CFS valid when duplicated record is only in non-selected OFS. This is deliberately fail-closed, not arbitrary first-match.
- API adapter, input data, `feature/*`, `main`, live DART and user account/DAKER submission unchanged. This patch makes **no claim** that actual OPENDART statements were checked; legitimate repeated account names may also be excluded until a richer account-ID/statement classification design is accepted.

## Independent GitHub Actions evidence
- Actual integrated code SHA: `5c4aed4d4654a1ec942078eca09d8fa92120fe0c`.
- Job `120785164197`, [run 40064628185](https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/40064628185), complete success.
- Unit test log: `Ran 31 tests in 0.002s`, `OK`; **31/31 PASS**, 0 fail/error. Existing 26 remain green, all 5 added cases green.
- `python -m proofinvest --claim-revenue-growth-pct 20` synthetic demo step also success.
- Local run: NOT_RUN. Actual elapsed human/AI task time: **미계측** (no reliable timer).

## Daily 100% budget (original October 28 task, completed early on October 24)

| Tested evidence gate | Points | Verified |
|---|---:|---|
| Existing duplicate-account behavior and safe handling requirement reviewed | 20 | Yes |
| Code rejects ambiguity and stays in selected CFS/OFS | 40 | Yes |
| Five tests + all prior 26 pass on integrated branch | 30 | Yes |
| Original commit, CI evidence and handoff/report | 10 | Yes |
| **Total** | **100 / 100** | **100%** |

**Estimated remaining base 0h + error/review contingency 0h = remaining 0h for this scoped task**; not proof of entire KIC product completion.

**Independent pending gate:** DAKER planned October 25 account/form check still 35/100 (**65% blocked**): real participant account (40 points), official PPTX bytes (25 points). Attempts to fetch template: web gets `Unsupported content-type`, container download refuses unviewable link, container DNS lookup fails. No further same-method retry. Estimated after access base 1h + contingency 2h = 3h, waiting uncertain. Existing own 10-slide draft tested from private Library but not uploaded publicly.

**Next allowed productive work:** Verification date/period and CFS/OFS consistency, with new unit tests. **Do not repeat the accepted Research work or this completed duplicate-account patch.**
