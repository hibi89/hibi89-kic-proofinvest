"""Run synthetic DL submissions -> saved original bytes -> KIC review span.

All parties/filing IDs and numeric samples here are artificial.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from disclosure_lightning.core import index_submissions, save_index
from disclosure_lightning.originals import (
    locate_original, persist_original, read_original_bytes,
)
from proofinvest.dl_source_span import anchored_source_span
from proofinvest.dl_bridge import assess_dl_sec_handoff
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.sec_companyfacts import verify_sec_annual_revenue

SYNTHETIC_HTML = (
    b"<html><body><p>Not a real SEC document. "
    b"TEST_LITERAL_SOURCE_SPAN is present but unverified.</p>"
    b"<script>alert('untrusted content');</script></body></html>"
)
PHRASE = "TEST_LITERAL_SOURCE_SPAN"


def replay_original() -> dict:
    raw_index = synthetic_submissions()
    indexed = index_submissions(
        raw_index, cik=SYNTHETIC_CIK, as_of=AS_OF,
        forms=frozenset({"10-K", "10-K/A"}),
        collected_at=COLLECTED_AT, provenance="OFFLINE_UNVERIFIED",
    )
    with TemporaryDirectory(prefix="kic-dl-raw-source-") as folder:
        db = Path(folder) / "records.sqlite"
        first = save_index(db, raw_index, indexed)
        receipt = locate_original(
            db, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        )
        saved = persist_original(
            db_path=db, receipt=receipt, raw=SYNTHETIC_HTML,
            kind="application/octet-stream", origin="OFFLINE_FILE_UNVERIFIED",
        )
        repeated = persist_original(
            db_path=db, receipt=receipt, raw=SYNTHETIC_HTML,
            kind="application/octet-stream", origin="OFFLINE_FILE_UNVERIFIED",
        )
        original = read_original_bytes(
            db_path=db, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION, sha256=saved["filing_sha256"],
        )
        span = anchored_source_span(
            db_path=db, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION,
            sha256=saved["filing_sha256"], needle=PHRASE,
        )
    verdict = verify_sec_annual_revenue(
        synthetic_companyfacts(), cik=SYNTHETIC_CIK,
        accession=SYNTHETIC_ACCESSION,
        current_end="2025-09-30", prior_end="2024-09-30",
        as_of=AS_OF, claimed_growth_pct="100.00",
    )
    linked = assess_dl_sec_handoff(indexed, verdict)
    if not (
        first["new_filings"] == 2 and saved["status"] == "SAVED"
        and repeated["status"] == "REUSED"
        and original == SYNTHETIC_HTML
        and span["status"] == "untrusted_original_span_for_review"
        and linked["status"] == "linked_metadata_only"
        and not span["authenticated_external_source"]
        and not linked["authenticated_external_source"]
    ):
        raise ValueError("KIC DL original-byte synthetic replay integrity failed")
    return {
        "schema": "proofinvest.kic-dl-original-e2e.v1",
        "status": "offline_original_source_path_pass",
        "synthetic_only": True,
        "submissions_index_stored": first["new_filings"],
        "original_file_receipt_status": saved["status"],
        "original_replay_receipt_status": repeated["status"],
        "original_filing_sha256": saved["filing_sha256"],
        "submissions_sha256": indexed["source_sha256"],
        "original_bytes_match": original == SYNTHETIC_HTML,
        "source_byte_start": span["start_byte"],
        "source_byte_end": span["end_byte_exclusive"],
        "escaped_context": span["context_escaped_html"],
        "source_span_status": span["status"],
        "kic_metadata_link": linked["status"],
        "authenticated_external_source": False,
        "real_sec_network_called": False,
        "real_filing_retrieved": False,
        "official_submission_made": False,
        "numeric_facts_authenticated": False,
    }


def main() -> None:
    print(json.dumps(replay_original(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
