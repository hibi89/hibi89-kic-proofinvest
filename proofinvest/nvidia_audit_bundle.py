"""P212: source-pinned, offline NVIDIA Guard audit report bundle.

Owner-local inspection only. No publisher/SEC byte equivalence, market license,
LLM accuracy, redistribution right, or trade authorization is asserted.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZipInfo, ZIP_STORED, BadZipFile

from .guard_agent import evaluate_guard
from .guard_audit import _canonical, _digest
from .nvidia_real_guard_audit import _POLICY
from .nvidia_real_issuer_review import actual_nvidia_issuer_receipt, review_nvidia_actual_release

_MAX_ARCHIVE = 80000
_MAX_PART = 20000
_FILES = {"review.json", "review.html", "manifest.json"}
_SCHEMA = "kuodra.p212-nvda-offline-guard-bundle.v1"


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def _expected() -> tuple[dict[str, Any], dict[str, Any]]:
    review = review_nvidia_actual_release(
        as_of="2026-11-05", receipt=actual_nvidia_issuer_receipt())
    if (review.get("status") != "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
            or review.get("issuer_original_publisher_seen") is not True
            or review.get("sec_original_identical") is not False
            or review.get("commercial_ai_rights_verified") is not False
            or review.get("full_abc_ready") is not False
            or type(review.get("evidence")) is not dict):
        raise ValueError("NVDA_SOURCE_UNVERIFIED")
    e = review["evidence"]
    m = e["metrics"]
    evidence = {
        "issuer": "NVDA", "fy2026": e["fiscal_2026_end"],
        "fy2025": e["fiscal_2025_end"],
        "p209_issuer_original_sha256": e["issuer_source_sha256"],
        "p209_one_shot_ci": e["source_ci_run"],
        "source_is_unaudited": True,
        "revenue_growth_pct": m["revenue_growth_pct"],
        "ar_growth_pct": m["ar_growth_pct"],
        "inventory_growth_pct": m["inventory_growth_pct"],
        "ar_growth_minus_revenue_pp": m["ar_growth_minus_revenue_pp"],
        "inventory_growth_minus_revenue_pp": m["inventory_growth_minus_revenue_pp"],
        "cfo_to_net_income_2026": m["cfo_to_net_income_2026"],
        "source_commercial_ai_rights_verified": False,
        "sec_edgar_original_byte_identity": False,
        "issuer_accounting_misconduct_proven": False,
    }
    evidence_sha = sha256(_canonical(evidence)).hexdigest()
    decision = evaluate_guard(
        [{"status": "UNAVAILABLE", "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
        policy=_POLICY, risk=None)
    if (decision.get("decision") != "HOLD"
            or decision.get("source_authenticated") is not False
            or decision.get("trade_executed") is not False
            or decision.get("human_approved") is not False):
        raise ValueError("NVDA_GUARD_CHANGED")
    request = {
        "schema": "kuodra.p211-nvda-derived-human-review-request.v1",
        "evidence": evidence, "evidence_digest": evidence_sha,
        "source_approved_for_external_use": False,
        "risk_authenticated": False, "trade_executed": False,
    }
    request_sha = sha256(_canonical(request)).hexdigest()
    event_hash = _digest(
        "0" * 64, _canonical({"request_hash": request_sha, "decision": decision}))
    export = {
        "schema": _SCHEMA, "status": "LOCAL_REPLAY_ONLY_UNLICENSED",
        "ticker": "NVDA",
        "source": {
            "official_issuer_url": e["issuer_source_url"],
            "issuer_original_sha256": e["issuer_source_sha256"],
            "original_one_shot_ci": e["source_ci_run"],
            "fiscal_latest_end": e["fiscal_2026_end"],
            "fiscal_prior_end": e["fiscal_2025_end"],
            "unaudited": True,
            "sec_edgar_original_identical": False,
            "commercial_ai_rights_verified": False,
        },
        "metrics": {
            "revenue_growth_pct": m["revenue_growth_pct"],
            "receivables_minus_revenue_pp": m["ar_growth_minus_revenue_pp"],
            "inventory_minus_revenue_pp": m["inventory_growth_minus_revenue_pp"],
            "cfo_to_net_income": m["cfo_to_net_income_2026"],
        },
        "audit": {
            "guard_decision": "HOLD", "reason_codes": decision["reason_codes"],
            "financial_evidence_sha256": evidence_sha,
            "initial_local_sqlite_event_hash": event_hash,
        },
        "limitations": {
            "sec_original_authenticated": False,
            "commercial_ai_rights_verified": False,
            "licensed_market_ndx_peer": False,
            "real_financial_ai_verified": False,
            "full_abc_ready": False, "financial_misconduct_proven": False,
            "public_redistribution_authorized": False,
            "raw_issuer_html_included": False, "trade_executed": False,
            "external_http_during_export": False,
        },
    }
    return export, decision


def _render_html(report: dict[str, Any]) -> bytes:
    metrics = report["metrics"]
    source = report["source"]
    rows = "".join("<tr><th>"+escape(label)+"</th><td>"+
                   escape(metrics[key])+"</td></tr>"
                   for label, key in (
                       ("Revenue growth (%)", "revenue_growth_pct"),
                       ("Receivables vs sales (pp)", "receivables_minus_revenue_pp"),
                       ("Inventory vs sales (pp)", "inventory_minus_revenue_pp"),
                       ("CFO / net income", "cfo_to_net_income")))
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<title>KUODRA local NVIDIA review</title></head><body>'
            '<h1>NVIDIA source-derived offline review</h1>'
            '<p>Guard HOLD · Not investment advice. Publisher unaudited. '
            'Not SEC-authenticated, licensed for redistribution or public Production.</p>'
            '<table>'+rows+'</table><p>Issuer source: <a href="'+
            escape(source["official_issuer_url"], quote=True)+'">Official source</a></p>'
            '<p>Issuer SHA-256: '+escape(source["issuer_original_sha256"])+'</p>'
            '<p>Evidence SHA-256: '+escape(report["audit"]["financial_evidence_sha256"])+'</p>'
            '<p>Local audit event hash: '+
            escape(report["audit"]["initial_local_sqlite_event_hash"])+'</p>'
            '<p>SEC original, data rights, true Nasdaq-100/peer, real financial AI '
            'and trading are NOT verified or authorized.</p></body></html>').encode("utf-8")


def _manifest(parts: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": "kuodra.p212-nvda-audit-archive-manifest.v1",
        "status": "LOCAL_OWNER_REVIEW_ONLY",
        "source_rights_verified": False,
        "sec_original_authenticated": False,
        "public_redistribution_authorized": False,
        "trade_executed": False,
        "files": {
            name: {"sha256": sha256(parts[name]).hexdigest(),
                   "bytes": len(parts[name])}
            for name in ("review.json", "review.html")
        },
    }


def _zip(parts: dict[str, bytes]) -> bytes:
    memory = BytesIO()
    with ZipFile(memory, "w", compression=ZIP_STORED) as archive:
        for name in ("review.json", "review.html", "manifest.json"):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, parts[name])
    return memory.getvalue()


def build_nvidia_audit_bundle(result: dict[str, Any]) -> tuple[bytes, str]:
    """Requires user-consented first SQLite event, not a forged report."""
    if (type(result) is not dict
            or result.get("status") != "REAL_NVDA_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED"
            or result.get("audit_written") is not True
            or result.get("audit_chain_valid") is not True
            or result.get("issuer_publisher_original_seen") is not True
            or result.get("sec_original_authenticated") is not False
            or result.get("source_commercial_ai_rights_verified") is not False
            or result.get("full_abc_ready") is not False
            or result.get("trade_executed") is not False
            or result.get("network_requests") != 0
            or type(result.get("report")) is not dict):
        raise ValueError("NVDA_CONSENTED_AUDIT_NOT_VERIFIED")
    expected, decision = _expected()
    report = result["report"]
    if (report.get("schema") != "kuodra.p211-nvda-real-guard-audit-report.v1"
            or report.get("source_sha256") != expected["source"]["issuer_original_sha256"]
            or report.get("source_ci_run") != expected["source"]["original_one_shot_ci"]
            or report.get("financial_evidence_sha256") !=
                    expected["audit"]["financial_evidence_sha256"]
            or report.get("guard") != decision
            or report.get("audit") != {
                "event_id": 1,
                "event_hash": expected["audit"]["initial_local_sqlite_event_hash"],
                "replayed": False,
            }
            or report.get("source_rights_verified") is not False
            or report.get("sec_original_authenticated") is not False
            or report.get("full_abc_ready") is not False
            or report.get("financial_misconduct_proven") is not False
            or report.get("trade_executed") is not False):
        raise ValueError("NVDA_LOCAL_AUDIT_SOURCE_OR_CHAIN_MISMATCH")
    parts = {"review.json": _json(expected),
             "review.html": _render_html(expected)}
    parts["manifest.json"] = _json(_manifest(parts))
    if any(not 0 < len(item) <= _MAX_PART for item in parts.values()):
        raise ValueError("NVDA_EXPORT_PART_TOO_LARGE")
    archive = _zip(parts)
    if not 0 < len(archive) <= _MAX_ARCHIVE:
        raise ValueError("NVDA_EXPORT_ZIP_TOO_LARGE")
    digest = sha256(archive).hexdigest()
    verify_nvidia_audit_bundle(archive, expected_sha256=digest)
    return archive, digest


def verify_nvidia_audit_bundle(
    archive: bytes, *, expected_sha256: str,
) -> dict[str, Any]:
    """Read-only pinned byte + canonical source/Guard replay; no extraction."""
    if (type(archive) is not bytes or not 0 < len(archive) <= _MAX_ARCHIVE
            or type(expected_sha256) is not str or len(expected_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_sha256)
            or sha256(archive).hexdigest() != expected_sha256):
        raise ValueError("NVDA_ZIP_RECEIPT_DIGEST_INVALID")
    with ZipFile(BytesIO(archive), "r") as zipped:
        entries = zipped.infolist()
        if (len(entries) != 3
                or set(item.filename for item in entries) != _FILES
                or any(item.is_dir() or item.flag_bits != 0
                       or item.compress_type != ZIP_STORED
                       or item.file_size <= 0 or item.file_size > _MAX_PART
                       or ((item.external_attr >> 16) & 0o170000) == 0o120000
                       for item in entries)):
            raise ValueError("NVDA_ZIP_STRUCTURE_DENIED")
        parts = {item.filename: zipped.read(item) for item in entries}
    try:
        report = json.loads(parts["review.json"].decode("utf-8"))
        manifest = json.loads(parts["manifest.json"].decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError("NVDA_ZIP_JSON_DENIED") from None
    expected, _ = _expected()
    if (type(report) is not dict or report != expected
            or parts["review.json"] != _json(expected)
            or parts["review.html"] != _render_html(expected)
            or type(manifest) is not dict
            or manifest != _manifest(parts)
            or parts["manifest.json"] != _json(_manifest(parts))):
        raise ValueError("NVDA_ZIP_PINNED_REPLAY_DENIED")
    return {
        "status": "LOCAL_NVDA_BUNDLE_DIGEST_AND_REPLAY_PASS",
        "bundle_sha256": expected_sha256,
        "issuer_original_sha256": report["source"]["issuer_original_sha256"],
        "financial_evidence_sha256": report["audit"]["financial_evidence_sha256"],
        "audit_event_hash": report["audit"]["initial_local_sqlite_event_hash"],
        "guard_decision": "HOLD",
        "sec_original_authenticated": False, "source_rights_verified": False,
        "market_ndx_peer_licensed": False, "public_distribution_authorized": False,
        "trade_executed": False, "external_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    from .local_report_bundle_verify import _read_original_file
    parser = argparse.ArgumentParser(description="Offline NVDA ZIP replay (no network)")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        out = verify_nvidia_audit_bundle(
            _read_original_file(args.archive),
            expected_sha256=args.expected_sha256)
    except (OSError, ValueError, TypeError, BadZipFile, RuntimeError,
            OverflowError, UnicodeError):
        print(json.dumps({"status": "BLOCKED",
                          "reason_code": "NVDA_ZIP_REPLAY_INVALID",
                          "trade_executed": False}, sort_keys=True))
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
