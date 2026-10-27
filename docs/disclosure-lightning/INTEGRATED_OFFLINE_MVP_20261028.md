# KIC + DL — runnable offline minimum vertical unit (2026-10-28)

**Single canonical DL runtime:** disclosure_lightning/core.py, executable as python -m disclosure_lightning. This staging/integration branch intentionally does NOT include alternate experimental mvp.py+cli.py or a second SQLite schema. No private Bid_Owl source copied.

## One command

    python -m proofinvest.kic_dl_demo

Runs actual public Python code SEC-shaped **synthetic** Submissions bytes -> DL index_submissions -> SQLite save/replay/list -> deterministic KIC SEC annual revenue verify -> read-only KIC dl_bridge. Prints a machine-readable JSON receipt. Uses Python stdlib, temporary database auto-cleanup, no API key, zero network, no external LLM, no real issuer amounts or original 10-K file.

## Verify

    python -m unittest tests.test_kic_dl_mvp_end_to_end -v
    python -m unittest discover -s tests -v

Replayed metadata and annual revenue numbers are wholly invented, issuer CIK=0000000001 and filing accession fake; never infer investment claims. A link status 'linked_metadata_only' means only structurally consistent metadata, not SEC authentication. Submissions source SHA256 is not the original filing SHA256 (null). Original official preliminary PDF and DAKER submission authorization remain separate.

## Contracts and next step

DL tech lead owns feature/disclosure-lightning. KIC chief owns integration branch + proofinvest/dl_bridge. Once CI succeeds and code audit passes, integrate into lead/kic (not main). Then add actual SEC direct GET only after proper user authorization/contact and check policy, plus incremental data, audit history, error handling and frontend by submission; no completion claims for those post-MVP items.

Full status shared through GitHub draft PR #1 and branch handoff; merge is not a silent automatic chat sync.
