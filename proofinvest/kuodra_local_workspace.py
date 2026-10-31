"""Explicit localhost-only, in-memory SEC-shaped triplet review workflow.

Raw uploaded bytes are never persisted here; the existing packet checker
creates only a disposable temporary SQLite for source-span verification.
An explicit second click runs the existing Guard/SQLite workflow inside a
different disposable directory. Self-reported input is NEVER SEC-authenticated.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES

from .local_sec_packet import _MAX_FILE_BYTES, build_local_sec_review_packet
from .local_sec_guard_report import review_local_sec_with_guard
from .local_sec_html_report import render_local_sec_html
from .kuodra_loose_sec_compatibility import inspect_loose_sec_bytes

_KEYS = frozenset(("submissions", "companyfacts", "original_filing"))
_FIELDS = frozenset((
    "cik", "accession", "as_of", "collected_at", "current_end",
    "prior_end", "needle", "claimed_growth_pct",
))
_LIMITS = {
    "submissions": MAX_JSON_BYTES,
    "companyfacts": _MAX_FILE_BYTES,
    "original_filing": MAX_FILING_BYTES,
}


def _check_bytes(raw: Any) -> dict[str, str]:
    if (not isinstance(raw, Mapping) or set(raw) != _KEYS
            or any(type(raw[k]) is not bytes
                   or not 0 < len(raw[k]) <= _LIMITS[k] for k in _KEYS)):
        raise ValueError("INVALID_OR_OVERSIZED_LOCAL_UPLOAD")
    return {k: hashlib.sha256(raw[k]).hexdigest() for k in sorted(_KEYS)}


def _review_request(request: Any) -> dict[str, Any]:
    if (not isinstance(request, Mapping) or set(request) != _FIELDS
            or any(type(request[k]) is not str for k in _FIELDS - {"claimed_growth_pct"})
            or not (request["claimed_growth_pct"] is None
                    or type(request["claimed_growth_pct"]) is str)
            or any(not 0 < len(request[k]) <= 240 for k in _FIELDS - {"claimed_growth_pct"})
            or any(any(ord(c) < 32 or ord(c) == 127 for c in request[k])
                   for k in _FIELDS - {"claimed_growth_pct"})
            or request["claimed_growth_pct"] is not None
            and len(request["claimed_growth_pct"]) > 100):
        raise ValueError("INVALID_LOCAL_REVIEW_REQUEST")
    return dict(request)


def _request_sha256(request: dict[str, Any]) -> str:
    # Keep operator-entered raw literal out of UI session state.
    return hashlib.sha256(json.dumps(
        request, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def discover_uploaded_periods(
    raw: Mapping[str, bytes], *, cik: str, accession: str,
    as_of: str, collected_at: str,
    show_local_needle_candidates: bool = False,
) -> dict[str, Any]:
    """No Guard, audit, network or raw-original persistence; human choice only."""
    if type(show_local_needle_candidates) is not bool:
        raise ValueError("EXPLICIT_LOCAL_TEXT_DISCLOSURE_FLAG_REQUIRED")
    pins = _check_bytes(raw)
    found = inspect_loose_sec_bytes(
        submissions_json=raw["submissions"],
        companyfacts_json=raw["companyfacts"],
        original_filing=raw["original_filing"],
        cik=cik, accession=accession, as_of=as_of,
        collected_at=collected_at,
        show_local_needle_candidates=show_local_needle_candidates,
    )
    if (found.get("status") != "operator_review_required"
            or found.get("source_sha256") != pins
            or found.get("source_authenticated") is not False
            or found.get("audit_written") is not False
            or found.get("network_calls") != 0):
        raise ValueError("LOCAL_PERIOD_CANDIDATES_UNAVAILABLE")
    return {
        "schema": "kuodra.local-upload-period-candidates.v1",
        "status": "periods_require_operator_selection",
        "issuer_cik": cik, "accession": accession, "as_of": as_of,
        "collected_at": collected_at, "source_sha256": pins,
        "period_candidates": found["period_candidates"],
        "candidate_count_truncated": found["candidates_truncated"],
        "local_needle_candidates": (
            found.get("local_needle_candidates", [])
            if show_local_needle_candidates else []
        ),
        "source_authenticated": False, "audit_written": False,
        "external_http_called": False, "original_text_disclosed": show_local_needle_candidates,
    }


def preview_uploaded_triplet(
    raw: Mapping[str, bytes], request: Mapping[str, Any],
) -> dict[str, Any]:
    """Read-only human checkpoint, no persistent audit or network calls."""
    pins = _check_bytes(raw)
    req = _review_request(request)
    packet = build_local_sec_review_packet(
        submissions_json=raw["submissions"],
        companyfacts_json=raw["companyfacts"],
        original_filing=raw["original_filing"],
        **req,
    )
    if (packet.get("schema") != "proofinvest.offline-local-sec-review.v1"
            or packet.get("mode") != "LOCAL_FILES_OFFLINE_UNAUTHENTICATED"
            or packet.get("status") != "reviewable_untrusted_local_evidence"
            or any(value is not False for value in packet["attestations"].values())
            or packet["source"].get("submissions_sha256") != pins["submissions"]
            or packet["source"].get("companyfacts_sha256") != pins["companyfacts"]
            or packet["source"].get("archived_filing_sha256") != pins["original_filing"]):
        raise ValueError("LOCAL_PREVIEW_PROVENANCE_OR_PIN_FAILURE")
    return {
        "schema": "kuodra.local-memory-workspace-preview.v1",
        "status": "requires_explicit_ephemeral_audit_consent",
        "source_sha256": pins,
        "operator_request_sha256": _request_sha256(req),
        "issuer_cik_operator_supplied": req["cik"],
        "accession_operator_supplied": req["accession"],
        "as_of_operator_supplied": req["as_of"],
        "verification_status": packet["financial"]["status"],
        "growth_pct_unverified": packet["financial"]["growth_pct"],
        "text_node_status": packet["source"]["html_text_node_literal_check"]["status"],
        "source_authenticated": False,
        "rights_verified": False,
        "audit_written": False,
        "external_http_called": False,
    }


def review_uploaded_triplet(
    raw: Mapping[str, bytes], request: Mapping[str, Any],
    *, expected_preview: Any, consent: bool = False,
) -> tuple[dict[str, Any], bytes]:
    """Execute Guard only for a byte-identical preview plus explicit consent.

    The local SQLite database is destroyed on return; the caller receives the
    signed-looking but NEVER authenticated audit hash as a local consistency
    receipt, not a retained persistent audit trail.
    """
    if consent is not True:
        raise ValueError("EXPLICIT_EPHEMERAL_AUDIT_CONSENT_REQUIRED")
    pins = _check_bytes(raw)
    req = _review_request(request)
    if (type(expected_preview) is not dict
            or expected_preview.get("schema") != "kuodra.local-memory-workspace-preview.v1"
            or expected_preview.get("status") != "requires_explicit_ephemeral_audit_consent"
            or expected_preview.get("source_sha256") != pins
            or expected_preview.get("operator_request_sha256") != _request_sha256(req)
            or expected_preview.get("source_authenticated") is not False
            or expected_preview.get("audit_written") is not False
            or expected_preview.get("external_http_called") is not False):
        raise ValueError("OPERATOR_PREVIEW_OR_UPLOADED_BYTES_CHANGED")
    with TemporaryDirectory(prefix="kuodra-temporary-local-audit-") as temp:
        report = review_local_sec_with_guard(
            submissions_json=raw["submissions"],
            companyfacts_json=raw["companyfacts"],
            original_filing=raw["original_filing"],
            audit_db_path=Path(temp) / "audit.sqlite",
            run_id="local-memory-review",
            expected_source_sha256=pins,
            **req,
        )
        if (report.get("audit_chain_valid") is not True
                or report.get("human_review_integrity_valid") is not True
                or report.get("operator_reviewed_source_digests_matched") is not True
                or report.get("guard", {}).get("decision") not in ("HOLD", "REJECT")
                or any(value is not False for value in report["limits"].values())):
            raise ValueError("EPHEMERAL_GUARD_TRUST_OR_AUDIT_FAILED")
        html = render_local_sec_html(report)
    return report, html
