"""Reproducible complete local Research -> Verification -> Risk -> Guard demo.

A synthetic receipt is shaped like an SEC capture receipt but was written
locally by this program. It represents ZERO actual SEC HTTP requests and is
NOT source authentication, financial research, live model inference or trading.

Usage:
    python -m proofinvest.kic_full_backend_demo --format json
    python -m proofinvest.kic_full_backend_demo --format markdown
    python -m proofinvest.kic_full_backend_demo --write-synthetic-zip sample-local.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .archived_sec_guard_report import (
    render_archived_sec_guard_markdown, run_archived_sec_guard_report,
)
from .guard_audit import GuardAuditStore
from .guard_review import GuardReviewStore
from .kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions,
    SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from .kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from .sec_capture_bundle import save_local_capture_bundle


def write_synthetic_review_archive(path: Path) -> None:
    """Explicitly create one self-authored, UNVERIFIED demo ZIP; never overwrite."""
    if not isinstance(path, Path):
        raise TypeError("Local output path must be a Path")
    archive = path
    sources = {
        "submissions": synthetic_submissions(),
        "companyfacts": json.dumps(
            synthetic_companyfacts(), sort_keys=True, ensure_ascii=False,
        ).encode("utf-8"),
        "original_filing": SYNTHETIC_HTML,
    }
    stamp = "2025-10-16T12:00:00+00:00"
    receipt = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3,
        "live_sec_http_called": True,
        "issuer_cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "observed_utc_day": "2025-10-16",
        "submissions_observed_at_utc": stamp,
        "companyfacts_observed_at_utc": stamp,
        "original_observed_at_utc": stamp,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {
            key: hashlib.sha256(data).hexdigest()
            for key, data in sources.items()
        },
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    save_local_capture_bundle(archive, receipt=receipt, **sources)


def run_synthetic_full_backend() -> dict[str, Any]:
    """Execute both signed-offline *simulation* paths, delete temp DB on exit."""
    with TemporaryDirectory(prefix="kic-backend-e2e-synthetic-") as folder:
        base = Path(folder)
        archive = base / "self-authored-synthetic.zip"
        audit = base / "guard.sqlite"
        write_synthetic_review_archive(archive)
        scenarios = []
        reports = []
        for name, claim in (("no-claim", None), ("conflicting-claim", "1.00")):
            result = run_archived_sec_guard_report(
                bundle_path=archive, audit_db_path=audit,
                current_end="2025-09-30", prior_end="2024-09-30",
                needle=PHRASE, run_id="synthetic-" + name,
                claimed_growth_pct=claim,
            )
            report_md = render_archived_sec_guard_markdown(result)
            reports.append(report_md)
            scenarios.append({
                "scenario": name,
                "research_status": result["research"]["status"],
                "verification_status": result["verification"]["status"],
                "risk_status": result["risk"]["status"],
                "guard_decision": result["guard"]["decision"],
                "audit_sha256": result["audit"]["event_hash"],
                "audit_valid": result["audit"]["chain_valid"],
                "source_evidence_digest": result["evidence"]["evidence_chain_sha256"],
                "source_authenticated": False,
                "trade_executed": False,
                "report_markdown": report_md,
            })
        audit_valid = GuardAuditStore(audit).verify_chain()
        review_valid = GuardReviewStore(audit).verify_reviews()
        if (not audit_valid or not review_valid
                or [x["guard_decision"] for x in scenarios] != ["HOLD", "REJECT"]
                or not all(x["audit_valid"] and x["trade_executed"] is False for x in scenarios)):
            raise ValueError("Synthetic full backend failed safety verification")
    # Temp archive and audit DB no longer exist beyond the context.
    return {
        "schema": "proofinvest.synthetic-full-backend-e2e.v1",
        "status": "synthetic_offline_backend_e2e_pass",
        "synthetic_only": True,
        "real_sec_http_requests": 0,
        "models_trained": 0,
        "trade_executed": False,
        "external_source_authenticated": False,
        "official_contest_submission": False,
        "audit_chain_verified": audit_valid,
        "human_review_integrity_verified": review_valid,
        "temporary_databases_discarded": True,
        "audited_run_count": len(scenarios),
        "scenarios": scenarios,
        "limitations": [
            "The apparent three-GET transport receipt is deliberately fabricated test metadata.",
            "No actual SEC response, company history, authenticity, or model evaluation is demonstrated.",
            "No human authorization, order, payment, DAKER submission or browser deployment.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Only synthetic, entirely offline KIC E2E demo")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--write-synthetic-zip", type=Path,
                        help="Explicitly save one self-authored, never-overwrite test ZIP for local UI")
    args = parser.parse_args(argv)
    if args.write_synthetic_zip is not None:
        try:
            write_synthetic_review_archive(args.write_synthetic_zip)
        except (OSError, ValueError, TypeError):
            print(json.dumps({"status": "SYNTHETIC_ARCHIVE_EXPORT_FAILED"}))
            return 2
        print(json.dumps({
            "status": "SYNTHETIC_UNVERIFIED_ZIP_CREATED",
            "local_file": str(args.write_synthetic_zip),
            "source_authenticated": False,
            "real_sec_http_requests": 0,
            "official_contest_submission": False,
        }, ensure_ascii=False))
        return 0
    try:
        result = run_synthetic_full_backend()
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "SYNTHETIC_BACKEND_FAILED"}))
        return 2
    if args.format == "markdown":
        print("# SYNTHETIC ONLY: full KIC backend E2E (NO SEC HTTP)\n\n"
              + "\n---\n\n".join(
                scenario["report_markdown"] for scenario in result["scenarios"]
              ))
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
