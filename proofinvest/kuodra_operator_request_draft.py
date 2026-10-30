"""KUODRA P15: offline, operator-selected P13 -> P14 pinned request draft.

A DRAFT is not permission to run Guard, persist audit, call an LLM or SEC,
or certify the SEC origin.  An independently supplied model proposal and
explicit local-audit consent are still required by kuodra_operator_replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .kuodra_offline_preflight import inspect_saved_capture_periods
from .kuodra_operator_replay import _valid_request
from .sec_capture_bundle import _read_checked_capture_bundle
from .visible_text_evidence import confirm_html_text_node_literal


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.operator-request-draft.v1",
        "status": "blocked",
        "reason_code": reason,
        "operator_request": None,
        "audit_written": False,
        "audit_consent_granted": False,
        "network_calls": 0,
        "live_model_called": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "trade_executed": False,
    }


def build_operator_request_draft(
    bundle_path: str | Path, *, requested_intent: str,
    current_end: str, prior_end: str, needle: str,
    audit_db: str | Path, run_id: str,
    claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Generate a *non-executing* operator request after explicit selections.

    Never select a period or original-filing quote on the user's behalf.
    Read the ZIP again after P13 preview, compare actual decoded source
    fingerprints and pin all three digests into the future P14 request.
    """
    if (type(bundle_path) not in (str, Path)
            or type(audit_db) not in (str, Path)
            or type(needle) is not str or not 8 <= len(needle) <= 128
            or not needle.isascii()
            or any(ord(ch) < 32 or ord(ch) > 126 for ch in needle)):
        return _blocked("INVALID_OPERATOR_DRAFT_INPUT")
    try:
        source = Path(bundle_path).expanduser().resolve(strict=False)
        audit = Path(audit_db).expanduser().resolve(strict=False)
        if source == audit:
            return _blocked("AUDIT_CAPTURE_INPUT_COLLISION")
        preview = inspect_saved_capture_periods(source)
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError):
        return _blocked("CAPTURE_PREFLIGHT_FAILED")
    if preview.get("status") != "review_candidates_available":
        return _blocked("CAPTURE_PREFLIGHT_BLOCKED")
    if not any(
        item.get("current_end") == current_end
        and item.get("prior_end") == prior_end
        for item in preview["period_candidates"]
    ):
        return _blocked("OPERATOR_PERIOD_NOT_IN_VERIFIED_PREVIEW")
    request = {
        "issuer_cik": preview["issuer_cik_self_reported"],
        "accession": preview["accession_self_reported"],
        "as_of": preview["as_of_self_reported"],
        "requested_intent": requested_intent,
        "capture_zip": str(source),
        "audit_db": str(audit),
        "run_id": run_id,
        "current_end": current_end,
        "prior_end": prior_end,
        "needle": needle,
        "expected_source_sha256": preview["source_sha256"],
    }
    if claimed_growth_pct is not None:
        request["claimed_growth_pct"] = claimed_growth_pct
    if not _valid_request(request):
        return _blocked("INVALID_OPERATOR_REQUEST")
    try:
        verdict, raws, receipt = _read_checked_capture_bundle(source)
    except (OSError, ValueError, KeyError, TypeError, OverflowError,
            RecursionError):
        return _blocked("CAPTURE_CHANGED_SINCE_PREFLIGHT")
    if (verdict.get("status") != "bundle_integrity_pass_origin_unverified"
            or not isinstance(raws, Mapping) or not isinstance(receipt, Mapping)
            or receipt.get("issuer_cik") != request["issuer_cik"]
            or receipt.get("accession") != request["accession"]
            or receipt.get("observed_utc_day") != request["as_of"]
            or any(hashlib.sha256(raws[k]).hexdigest()
                   != request["expected_source_sha256"][k]
                   for k in ("submissions", "companyfacts", "original_filing"))):
        return _blocked("CAPTURE_CHANGED_SINCE_PREFLIGHT")
    original = raws["original_filing"]
    raw_needle = needle.encode("ascii")
    offset = original.find(raw_needle)
    if (offset < 0 or original.find(raw_needle, offset + 1) != -1
            or confirm_html_text_node_literal(
                original, needle=needle,
                expected_start=offset, expected_end=offset + len(raw_needle),
            ).get("exact_raw_byte_span_verified") is not True):
        return _blocked("OPERATOR_NEEDLE_NOT_UNIQUE_TEXT_NODE")
    return {
        **_blocked("DRAFT_ONLY_REQUIRES_SEPARATE_APPROVAL"),
        "status": "ready_for_operator_review",
        "operator_request": request,
        "source_fingerprints_match_preview": True,
        "selected_original_text_node_verified": True,
    }


def _publish_draft_only(path: Path, request: dict[str, Any]) -> None:
    """User-requested new JSON file only. Never overwrite/symlink or audit."""
    dest = path.expanduser()
    source = Path(request["capture_zip"])
    audit = Path(request["audit_db"])
    if (dest.suffix.lower() != ".json"
            or dest.exists() or dest.is_symlink()
            or not dest.parent.is_dir() or dest.parent.is_symlink()
            or dest.resolve(strict=False) in
                (source.resolve(strict=False), audit.resolve(strict=False))):
        raise ValueError("REQUEST_DRAFT_DESTINATION_UNAVAILABLE")
    payload = (json.dumps(request, ensure_ascii=False, sort_keys=True,
                          indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > 16_384:
        raise ValueError("REQUEST_DRAFT_TOO_LARGE")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", dir=dest.parent, prefix=".kuodra-draft-",
            suffix=".part", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, dest)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline P13 -> P14 pinned request draft only; NEVER runs Guard."
    )
    parser.add_argument("--capture-zip", required=True, type=Path)
    parser.add_argument("--requested-intent", required=True,
                        choices=("GROWTH_CHECK", "SOURCE_REVIEW", "RISK_CHECK"))
    for name in ("current-end", "prior-end", "needle", "run-id"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--audit-db", required=True, type=Path)
    parser.add_argument("--claimed-growth-pct")
    parser.add_argument("--output-request-json", type=Path,
                        help="Explicit NEW JSON draft path, never overwrite")
    args = parser.parse_args(argv)
    result = build_operator_request_draft(
        args.capture_zip, requested_intent=args.requested_intent,
        current_end=args.current_end, prior_end=args.prior_end,
        needle=args.needle, audit_db=args.audit_db, run_id=args.run_id,
        claimed_growth_pct=args.claimed_growth_pct,
    )
    if args.output_request_json is not None and result["status"] == "ready_for_operator_review":
        try:
            _publish_draft_only(args.output_request_json, result["operator_request"])
            result["request_file_written"] = True
        except (ValueError, OSError, TypeError, RecursionError):
            result = _blocked("REQUEST_DRAFT_EXPORT_FAILED_NO_AUDIT")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "ready_for_operator_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
