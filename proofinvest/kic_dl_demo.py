"""One-command synthetic-only Disclosure Lightning -> ProofInvest MVP replay.

Runs SEC-shaped input -> canonical DL index -> immutable SQLite ->
deterministic SEC annual revenue arithmetic -> KIC metadata gate.
This is NOT live SEC data, a verified filing, an LLM or investment advice.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from disclosure_lightning.core import index_submissions, save_index, list_filings
from proofinvest.sec_companyfacts import TAG, verify_sec_annual_revenue
from proofinvest.dl_bridge import assess_dl_sec_handoff

SYNTHETIC_CIK = "0000000001"
SYNTHETIC_ACCESSION = "0000000001-25-000001"
AS_OF = "2025-10-16"
COLLECTED_AT = "2025-10-16T12:00:00Z"


def synthetic_submissions() -> bytes:
    payload = {
        "cik": 1,
        "name": "SYNTHETIC TEST ISSUER — DOES NOT EXIST",
        "filings": {"recent": {
            "accessionNumber": [SYNTHETIC_ACCESSION, "0000000001-25-000002"],
            "form": ["10-K", "10-K/A"],
            "filingDate": ["2025-10-15", "2025-10-16"],
            "primaryDocument": ["synthetic10k.htm", "syntheticamendment.htm"],
            "acceptanceDateTime": ["2025-10-15T12:00:00Z", "2025-10-16T09:00:00Z"],
        }},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def synthetic_companyfacts() -> dict:
    return {
        "cik": 1,
        "facts": {"us-gaap": {TAG: {"units": {"USD": [
            {"accn": SYNTHETIC_ACCESSION, "form": "10-K",
             "start": "2024-10-01", "end": "2025-09-30",
             "filed": "2025-10-15", "val": 200},
            {"accn": SYNTHETIC_ACCESSION, "form": "10-K",
             "start": "2023-10-01", "end": "2024-09-30",
             "filed": "2025-10-15", "val": 100},
        ]}}}},
    }


def replay() -> dict:
    """Return self-contained synthetic receipt; no SEC HTTP or external calls."""
    raw = synthetic_submissions()
    indexed = index_submissions(
        raw, cik=SYNTHETIC_CIK, as_of=AS_OF,
        forms=frozenset({"10-K", "10-K/A"}),
        provenance="OFFLINE_UNVERIFIED",
        collected_at=COLLECTED_AT,
    )
    with TemporaryDirectory(prefix="kic-dl-mvp-") as root:
        db_path = Path(root) / "immutable-index.sqlite3"
        first = save_index(db_path, raw, indexed)
        repeated = save_index(db_path, raw, indexed)
        stored = list_filings(db_path, cik=SYNTHETIC_CIK)
    numeric = verify_sec_annual_revenue(
        synthetic_companyfacts(), cik=SYNTHETIC_CIK,
        accession=SYNTHETIC_ACCESSION,
        current_end="2025-09-30", prior_end="2024-09-30",
        as_of=AS_OF, claimed_growth_pct="100.00",
    )
    link = assess_dl_sec_handoff(indexed, numeric)
    if not (
        first["new_filings"] == 2 and repeated["new_filings"] == 0
        and len(stored) == 2
        and numeric["status"] == "calculated_unverified"
        and numeric["growth_pct"] == "100.00"
        and link["status"] == "linked_metadata_only"
        and not link["authenticated_external_source"]
    ):
        raise ValueError("Synthetic DL-to-KIC MVP safety invariant failed")
    return {
        "schema": "proofinvest.dl-kic-synthetic-e2e-receipt.v1",
        "status": "offline_mvp_pass",
        "synthetic_data_only": True,
        "real_issuer_verified": False,
        "live_sec_requested": False,
        "full_filing_content_retrieved": False,
        "agent_executed": False,
        "official_hackathon_submitted": False,
        "issuer_cik": SYNTHETIC_CIK,
        "as_of": AS_OF,
        "dl_indexed": indexed["indexed_count"],
        "sqlite_inserted_first": first["new_filings"],
        "sqlite_inserted_repeat": repeated["new_filings"],
        "sqlite_listed_filings": len(stored),
        "submissions_json_sha256": indexed["source_sha256"],
        "original_filing_sha256": None,
        "synthetic_numeric_status": numeric["status"],
        "synthetic_growth_pct": numeric["growth_pct"],
        "kic_link_status": link["status"],
        "kic_external_authentication": link["authenticated_external_source"],
    }


def main() -> None:
    print(json.dumps(replay(), sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
