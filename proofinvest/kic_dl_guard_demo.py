"""Standalone KIC DL -> Guard -> SQLite audit -> report demo.

Runs exclusively from a synthetic bundled filing and temporary local SQLite.
Never contacts SEC or executes a trade. The databases are discarded on exit.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from integrations.dl_vendor import core, originals
from .dl_vendor_audit_report import render_dl_audit_markdown, run_saved_dl_audit_report


CIK = "0000320193"  # Real-format identifier, NOT real Apple evidence.
ACCESSION = "0000320193-25-000079"
AS_OF = "2025-11-01"
COLLECTED = "2025-11-01T10:30:00Z"
FIXTURE = (Path(__file__).resolve().parents[1] /
           "integrations/dl_vendor/fixtures/kic_apple_handoff_synthetic.json")
SYNTHETIC_HTML = (
    b"<html><body><h1>SYNTHETIC filing, NOT a real SEC report</h1>"
    b"<p>Revenue 100 synthetic units</p>"
    b"<script>INVISIBLE SYNTHETIC SCRIPT</script></body></html>"
)


def run_synthetic_demo() -> dict:
    """Exercise the real offline code paths, not an invented mock outcome."""
    with tempfile.TemporaryDirectory(prefix="kic-dl-guard-synthetic-") as directory:
        dl_db = Path(directory) / "dl.sqlite"
        audit_db = Path(directory) / "audit.sqlite"
        metadata = FIXTURE.read_bytes()
        index = core.index_submissions(
            metadata, cik=CIK, as_of=AS_OF, forms=core.parse_forms("10-K"),
            collected_at=COLLECTED, provenance="OFFLINE_UNVERIFIED",
        )
        core.save_index(dl_db, metadata, index)
        location = originals.locate_original(dl_db, cik=CIK, accession=ACCESSION)
        with patch("integrations.dl_vendor.originals._timestamp",
                   return_value="2025-11-01T10:32:00Z"):
            receipt = originals.persist_original(
                db_path=dl_db, receipt=location, raw=SYNTHETIC_HTML,
                kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
            )
        report = run_saved_dl_audit_report(
            dl_db_path=dl_db, audit_db_path=audit_db, cik=CIK,
            accession=ACCESSION, sha256=receipt["filing_sha256"],
            as_of=AS_OF, term="Revenue", run_id="synthetic-demo",
            reviewer="synthetic-reviewer", action="ACKNOWLEDGE",
            reason="Explicit human acknowledgement in synthetic offline demonstration",
        )
        if (report["guard"]["decision"] != "HOLD"
                or report["evidence"]["candidate_count"] < 1
                or report["audit"]["chain_valid"] is not True
                or report["audit"]["human_review_integrity_valid"] is not True
                or report["trade_executed"] is not False):
            raise ValueError("Synthetic Guard demo integrity failed")
        return {
            "schema": "proofinvest.kic-dl-guard-synthetic-demo.v1",
            "synthetic_only": True,
            "real_sec_source_authenticated": False,
            "database_persisted_after_demo": False,
            "report": report,
            "official_contest_submission": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KIC offline DL/Guard synthetic E2E")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    result = run_synthetic_demo()
    if args.format == "markdown":
        print("# SYNTHETIC DEMONSTRATION — not real SEC evidence or official submission")
        print()
        print(render_dl_audit_markdown(result["report"]), end="")
        print("Temporary SQLite audit database was discarded after validation.")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
