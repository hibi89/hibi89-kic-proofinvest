"""Offline read-only reanalysis of a locally retained SEC-shaped evidence ZIP.

The manifest is caller-controlled and not authenticated SEC provenance.
The same source bytes are loaded once, checked before any numeric review,
and never uploaded, executed, written back or reported as raw HTML.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from proofinvest.local_sec_packet import build_local_sec_review_packet
from proofinvest.offline_evidence_triage import triage_offline_replay
from proofinvest.offline_review_summary import build_offline_review_summary
from proofinvest.local_risk_screen import screen_local_evidence
from proofinvest.sec_capture_bundle import _read_checked_capture_bundle


def _failure(reason: str) -> dict[str, Any]:
    return {
        "schema": "proofinvest.sec-offline-bundle-replay.v1",
        "status": "unavailable",
        "reason_code": reason,
        "source_authenticated": False,
        "financial_values_authenticated": False,
        "source_rights_verified": False,
        "external_http_called": False,
        "official_contest_submission": False,
    }


def _receipt_capture_clock(receipt: dict[str, Any]) -> str | None:
    """Reject backdated/cross-day/naive or unordered untrusted clock strings."""
    day = receipt.get("observed_utc_day")
    if not isinstance(day, str) or len(day) != 10:
        return None
    try:
        times = []
        for field in (
            "submissions_observed_at_utc",
            "companyfacts_observed_at_utc",
            "original_observed_at_utc",
        ):
            raw = receipt.get(field)
            if not isinstance(raw, str) or "T" not in raw:
                return None
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                return None
            times.append(dt.astimezone(timezone.utc))
        if not all(instant.date().isoformat() == day for instant in times):
            return None
        if times != sorted(times):
            return None
        return times[0].isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def replay_local_capture(
    path: Path, *, current_end: str, prior_end: str, needle: str,
    claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Re-evaluate bounded original archive with no new network or writes."""
    integrity, raw, receipt = _read_checked_capture_bundle(path)
    if (integrity.get("status") != "bundle_integrity_pass_origin_unverified"
            or raw is None or receipt is None):
        return _failure("ARCHIVED_BYTES_OR_MANIFEST_INVALID")
    collected_at = _receipt_capture_clock(receipt)
    if collected_at is None:
        return _failure("UNTRUSTED_OR_INCONSISTENT_ARCHIVED_CLOCK")
    try:
        review = build_local_sec_review_packet(
            submissions_json=raw["submissions"],
            companyfacts_json=raw["companyfacts"],
            original_filing=raw["original_filing"],
            cik=receipt["issuer_cik"], accession=receipt["accession"],
            as_of=receipt["observed_utc_day"], collected_at=collected_at,
            current_end=current_end, prior_end=prior_end,
            needle=needle, claimed_growth_pct=claimed_growth_pct,
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, OSError):
        return _failure("ARCHIVED_DISCLOSURE_CANNOT_BE_REANALYZED")
    source = review["source"]
    if any(source[dkey] != integrity["sha256"][ikey] for dkey, ikey in (
        ("submissions_sha256", "submissions"),
        ("companyfacts_sha256", "companyfacts"),
        ("archived_filing_sha256", "original_filing"),
    )):
        return _failure("REPLAY_DIGEST_CONFLICT")
    if not all(v is False for v in review["attestations"].values()):
        return _failure("REPLAY_TRUST_BOUNDARY_FAILED")
    result = {
        **_failure("LOCAL_BYTES_AND_MATH_ONLY"),
        "status": "offline_capture_replayed_unverified",
        "issuer_cik": receipt["issuer_cik"],
        "accession": receipt["accession"],
        "as_of_self_reported": receipt["observed_utc_day"],
        "local_integrity": integrity,
        "offline_financial_review": review["financial"],
        "source_span": {
            "original_sha256": source["archived_filing_sha256"],
            "start_byte": source["span_start_byte"],
            "end_byte_exclusive": source["span_end_byte_exclusive"],
            "numeric_literals": source["numeric_literal_crosscheck"],
            "ixbrl_context": source["ixbrl_revenue_context_review"],
        },
        "risk": review["risk"],
        "limitations": [
            "Stored captured-at timestamps and source URLs are self-reported, not externally authenticated.",
            "Byte digest match and growth calculations do not prove SEC issuer identity, filing truth, or source rights.",
            "No actual provider HTTP, agent execution, investment recommendation, or DAKER submission occurs.",
        ],
    }
    result["risk"] = screen_local_evidence(result["offline_financial_review"], result["source_span"])
    result["human_review_triage"] = triage_offline_replay(result)
    result["review_summary"] = build_offline_review_summary(result)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="NO NETWORK: audit a stored SEC capture ZIP")
    p.add_argument("bundle", type=Path, help="Local read-only archived bundle ZIP")
    p.add_argument("--current-end", required=True)
    p.add_argument("--prior-end", required=True)
    p.add_argument("--needle", required=True,
                   help="A unique ASCII literal 4-128 characters in the original")
    p.add_argument("--claimed-growth-pct")
    args = p.parse_args(argv)
    result = replay_local_capture(
        args.bundle, current_end=args.current_end, prior_end=args.prior_end,
        needle=args.needle, claimed_growth_pct=args.claimed_growth_pct,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "offline_capture_replayed_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
