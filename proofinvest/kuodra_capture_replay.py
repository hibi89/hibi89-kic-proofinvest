"""KUODRA offline replay of a previously saved SEC three-source capture ZIP.

Do not equate self-reported HTTPS provenance and local SHA integrity with SEC
authenticity or independent finance attestation. This module does NO network.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .local_sec_guard_report import _check_audit_path, review_local_sec_with_guard
from .sec_capture_bundle import _read_checked_capture_bundle


def _capture_instant(value: Any, day: str) -> datetime | None:
    if not isinstance(value, str) or "T" not in value or not 10 < len(value) <= 60:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None or d.utcoffset() is None:
        return None
    utc = d.astimezone(timezone.utc)
    return utc if utc.date().isoformat() == day else None


def replay_saved_capture(
    *, bundle_path: str | Path, audit_db: str | Path, run_id: str,
    current_end: str, prior_end: str, needle: str,
    claimed_growth_pct: str | None = None,
    acknowledge_local_audit_persistence: bool = False,
) -> dict[str, Any]:
    """Replay a bounded, previously captured ZIP with no HTTP or model.

    Validate every receipt/clock before writing. Old source remains read-only,
    and the resulting SQLite Guard audit stores only evidence fingerprints.
    """
    if acknowledge_local_audit_persistence is not True:
        raise ValueError("EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
    source = Path(bundle_path).expanduser()
    dest = _check_audit_path(audit_db)
    if source.resolve(strict=False) == dest.resolve(strict=False):
        raise ValueError("AUDIT_CAPTURE_INPUT_COLLISION")
    verdict, raws, receipt = _read_checked_capture_bundle(source)
    if (verdict.get("status") != "bundle_integrity_pass_origin_unverified"
            or verdict.get("local_bytes_and_manifest_match") is not True
            or not isinstance(raws, Mapping)
            or not isinstance(receipt, Mapping)
            or receipt.get("capture_bytes_persisted") is not False):
        # Bundle manifest is validated but not independently authenticated.
        raise ValueError("CAPTURE_BUNDLE_INTEGRITY_UNVERIFIED")
    day = receipt.get("observed_utc_day")
    instants = [
        _capture_instant(receipt.get(k), day)
        for k in ("submissions_observed_at_utc",
                  "companyfacts_observed_at_utc",
                  "original_observed_at_utc")
    ]
    if (not isinstance(day, str) or len(day) != 10
            or any(x is None for x in instants)
            or instants != sorted(instants)):
        raise ValueError("CAPTURE_RECEIPT_CHRONOLOGY_INVALID")
    # Use the recorded ORIGINAL observation time. Not today's time and
    # never an invented historical backdating certificate.
    report = review_local_sec_with_guard(
        submissions_json=raws["submissions"],
        companyfacts_json=raws["companyfacts"],
        original_filing=raws["original_filing"],
        cik=receipt["issuer_cik"], accession=receipt["accession"],
        as_of=day, collected_at=receipt["submissions_observed_at_utc"],
        current_end=current_end, prior_end=prior_end, needle=needle,
        claimed_growth_pct=claimed_growth_pct,
        audit_db_path=dest, run_id=run_id,
    )
    actual = report["source"]
    sha = receipt["raw_response_sha256"]
    if (actual["submissions_sha256"] != sha["submissions"]
            or actual["companyfacts_sha256"] != sha["companyfacts"]
            or actual["archived_original_sha256"] != sha["original_filing"]
            or not report["audit_chain_valid"]
            or report["guard"]["decision"] not in ("HOLD", "REJECT")):
        # An inconsistent post-write report MUST NOT be marked successful.
        raise ValueError("CAPTURE_REPLAY_POSTWRITE_INTEGRITY_FAILURE")
    return {
        "schema": "kuodra.offline-captured-sec-replay.v1",
        "status": "OFFLINE_CAPTURE_REVIEW_RECORDED",
        "run_id": run_id,
        "issuer": report["issuer"],
        "observed_utc_day_self_reported": day,
        "original_capture_hashes_match": True,
        "verification": report["verification"],
        "risk": report["risk"],
        "guard": report["guard"],
        "audit": report["audit"],
        "audit_chain_valid": report["audit_chain_valid"],
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "live_api_called": False,
        "ai_agent_executed": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="KUODRA offline saved SEC capture → Decimal → Guard → SQLite; no network."
    )
    p.add_argument("--capture-zip", required=True, type=Path)
    p.add_argument("--audit-db", required=True, type=Path)
    for key in ("run-id", "current-end", "prior-end", "needle"):
        p.add_argument("--" + key, required=True)
    p.add_argument("--claimed-growth-pct")
    p.add_argument("--acknowledge-local-audit-persistence", action="store_true")
    args = p.parse_args(argv)
    try:
        result = replay_saved_capture(
            bundle_path=args.capture_zip, audit_db=args.audit_db,
            run_id=args.run_id, current_end=args.current_end,
            prior_end=args.prior_end, needle=args.needle,
            claimed_growth_pct=args.claimed_growth_pct,
            acknowledge_local_audit_persistence=args.acknowledge_local_audit_persistence,
        )
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
        p.exit(2, "KUODRA offline capture replay blocked\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
