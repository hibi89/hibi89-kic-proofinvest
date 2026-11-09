"""Offline, restricted co-review of the existing SEC Guard and KUODRA ML report.

This is an EVIDENCE AGGREGATOR, not an issuer-level merge or security boundary.
The SEC and ML source sets are NOT proved to describe the same company. No
network, storage, inference, authentication, public export, or trading actions.
Pass only reports produced within the same trusted local review process.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
import math
import re
from typing import Any

from .kuodra_review_report import _canonical

_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_SHA_KEYS = ("submissions_sha256", "history_page_sha256",
             "companyfacts_sha256", "archived_original_sha256")
_SEC_STATES = frozenset(("calculated_unverified", "conflict", "unavailable"))
_ML_STATES = frozenset(("EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED", "NO_TRAIN"))


def _sha(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _nonnegative_count(value: Any) -> int:
    if type(value) is not int or value < 0 or value > 1_000_000:
        raise ValueError("BRIDGE_UNSAFE_ML_SUMMARY")
    return value


def _safe_metric(value: Any) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1_000_000:
        raise ValueError("BRIDGE_UNSAFE_ML_SUMMARY")
    return float(value)


def build_local_sec_ml_review(sec_report: dict[str, Any], ml_packet: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed source/audit/receipt checks; co-review ONLY, never silent join.

    SEC numeric verification never authenticates the origin, and ML model scores
    do not supersede an existing deterministic Guard REJECT. A trusted operator
    must separately attest the cross-source issuer map before any real joined
    assertion can be built. This function intentionally offers no such override.
    """
    if type(sec_report) is not dict or type(ml_packet) is not dict:
        raise ValueError("BRIDGE_REPORT_CONTRACT_INVALID")
    if (sec_report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or sec_report.get("mode") != "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED"
            or sec_report.get("audit_chain_valid") is not True
            or sec_report.get("human_review_integrity_valid") is not True):
        raise ValueError("BRIDGE_SEC_AUDIT_OR_SOURCE_INVALID")
    flags = sec_report.get("limits")
    if (type(flags) is not dict or not flags
            or any(value is not False for value in flags.values())
            or any(key not in flags for key in (
                "external_source_authenticated", "source_rights_verified",
                "live_api_called", "ai_agent_executed", "trade_executed",
                "simulation_authorized", "official_contest_submission"))):
        raise ValueError("BRIDGE_SEC_UNTRUSTED_POLICY")
    sec_guard = sec_report.get("guard")
    source = sec_report.get("source")
    verification = sec_report.get("verification")
    if (type(sec_guard) is not dict or type(source) is not dict
            or type(verification) is not dict
            or sec_guard.get("decision") not in ("HOLD", "REJECT")
            or sec_guard.get("source_authenticated") is not False
            or verification.get("status") not in _SEC_STATES
            or source.get("source_index_kind") not in ("RECENT", "PINNED_HISTORY")
            or not all(_sha(source.get(key)) for key in _SHA_KEYS
                       if key != "history_page_sha256")
            or (source["source_index_kind"] == "RECENT"
                and source.get("history_page_sha256") is not None)
            or (source["source_index_kind"] == "PINNED_HISTORY"
                and not _sha(source.get("history_page_sha256")))
            or type(source.get("exact_raw_byte_span_verified")) is not bool):
        raise ValueError("BRIDGE_SEC_EVIDENCE_INVALID")
    # A source-numeric conflict cannot be laundered as a HOLD via a forged
    # report or a more optimistic regression result.
    if verification["status"] == "conflict" and sec_guard["decision"] != "REJECT":
        raise ValueError("BRIDGE_SEC_CONFLICT_DOWNGRADED")

    if (ml_packet.get("schema") != "kuodra.local-restricted-review.v1"
            or ml_packet.get("status") != "HUMAN_REVIEW_REQUIRED"
            or ml_packet.get("scope") not in ("PRIVATE", "LOCAL_HYBRID")
            or ml_packet.get("decision") != "HOLD"
            or ml_packet.get("public_export_allowed") is not False
            or ml_packet.get("external_llm_allowed") is not False
            or ml_packet.get("host_egress_verified") is not False
            or ml_packet.get("origin_verified") is not False
            or ml_packet.get("calibrated_probability") is not None
            or ml_packet.get("data_rows_disclosed") is not False):
        raise ValueError("BRIDGE_ML_RESTRICTION_INVALID")
    original_hash = ml_packet.get("receipt_sha256")
    unhashed = dict(ml_packet)
    unhashed.pop("receipt_sha256", None)
    if not _sha(original_hash) or sha256(_canonical(unhashed)).hexdigest() != original_hash:
        raise ValueError("BRIDGE_ML_RECEIPT_INVALID")
    evidence = ml_packet.get("evidence")
    if (type(evidence) is not list or len(evidence) not in (1, 2)
            or (ml_packet["scope"] == "PRIVATE" and len(evidence) != 1)
            or (ml_packet["scope"] == "LOCAL_HYBRID" and len(evidence) != 2)):
        raise ValueError("BRIDGE_ML_LINEAGE_INVALID")
    hashes = []
    for item in evidence:
        if (type(item) is not dict or not _sha(item.get("raw_source_sha256"))
                or item.get("access_level") not in ("PRIVATE", "PUBLIC")
                or item.get("publisher_authenticated") is not False
                or item.get("source_rights_verified") is not False):
            raise ValueError("BRIDGE_ML_LINEAGE_INVALID")
        hashes.append({"source_sha256": item["raw_source_sha256"],
                       "zone": item["access_level"],
                       "rows": _nonnegative_count(item.get("row_count"))})
    expected_zones = ["PRIVATE"] if ml_packet["scope"] == "PRIVATE" else ["PUBLIC", "PRIVATE"]
    if [e["zone"] for e in hashes] != expected_zones:
        raise ValueError("BRIDGE_ML_ZONE_INVALID")
    analysis = ml_packet.get("analysis")
    if type(analysis) is not dict or analysis.get("status") not in _ML_STATES:
        raise ValueError("BRIDGE_ML_ANALYSIS_INVALID")
    summary = {"status": analysis["status"],
               "train_n": _nonnegative_count(analysis.get("train_n", 0)),
               "holdout_n": _nonnegative_count(analysis.get("holdout_n", 0)),
               "holdout_improvement_pct": _safe_metric(analysis.get("holdout_improvement_pct"))}
    if "time_trend_warning" in analysis:
        warning = analysis["time_trend_warning"]
        if warning not in (
                "FEATURE_MODEL_NOT_SELECTED",
                "TIME_ONLY_BASELINE_AS_GOOD_OR_BETTER",
                "FEATURE_INCREMENTAL_HOLDOUT_OBSERVED_NOT_VALIDATED"):
            raise ValueError("BRIDGE_UNSAFE_TIME_TREND_DIAGNOSTIC")
        summary["time_trend_warning"] = warning
        summary["holdout_time_only_mae"] = _safe_metric(analysis.get("holdout_time_only_mae"))
        summary["incremental_vs_time_only_pct"] = _safe_metric(
            analysis.get("incremental_vs_time_only_pct"))
    # All output keys are hand-authored. Raw SEC/ML nested strings, names,
    # issuer ids and model features do not cross this allowlisted boundary.
    packet = {
        "schema": "kuodra.local-sec-ml-co-review.v1",
        "status": "LOCAL_HUMAN_REVIEW_REQUIRED",
        "scope": "RESTRICTED_LOCAL_ONLY",
        "sec": {"numeric_status": verification["status"],
                "decision": sec_guard["decision"],
                "source_hashes": {key: source[key] for key in _SHA_KEYS
                                  if key != "history_page_sha256"
                                  or source["source_index_kind"] == "PINNED_HISTORY"},
                "exact_raw_byte_span_verified": source["exact_raw_byte_span_verified"],
                "offline_audit_chain_verified": True},
        "ml": {"scope": ml_packet["scope"], "summary": summary,
               "source_hashes": hashes, "receipt_sha256": original_hash},
        "decision": "REJECT" if sec_guard["decision"] == "REJECT" else "HOLD",
        "cross_source_entity_link": "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS",
        "provenance": "HASHED_INPUTS_ONLY_NOT_PUBLISHER_AUTHENTICATION",
        "independent_finance_validation": False,
        "trade_authorized": False,
        "public_export_allowed": False,
        "external_llm_allowed": False,
        "institution_host_egress_verified": False,
        "human_review_required": True,
    }
    packet["receipt_sha256"] = sha256(_canonical(packet)).hexdigest()
    return packet


def render_local_sec_ml_review_html(packet: dict[str, Any]) -> str:
    """No JavaScript, active content, network links or external dependencies."""
    if (type(packet) is not dict or packet.get("schema") != "kuodra.local-sec-ml-co-review.v1"
            or packet.get("decision") not in ("HOLD", "REJECT")
            or packet.get("cross_source_entity_link") != "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS"
            or packet.get("trade_authorized") is not False
            or packet.get("public_export_allowed") is not False
            or packet.get("external_llm_allowed") is not False):
        raise ValueError("BRIDGE_RENDER_POLICY_INVALID")
    content = dict(packet)
    digest = content.pop("receipt_sha256", None)
    if not _sha(digest) or sha256(_canonical(content)).hexdigest() != digest:
        raise ValueError("BRIDGE_RENDER_RECEIPT_INVALID")
    # Explicit no-script CSP; escape any future textual extension safely.
    escaped = escape(json.dumps(packet, ensure_ascii=True, sort_keys=True,
                                indent=2, allow_nan=False))
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            '<meta http-equiv="Content-Security-Policy" '
            'content="default-src \'none\'; style-src \'unsafe-inline\'; form-action \'none\'; base-uri \'none\'">'
            '<title>KUODRA offline SEC + ML review</title>'
            '<style>body{max-width:960px;margin:2rem auto;font:14px/1.5 system-ui;'
            'background:#151515;color:#eee}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            '</style></head><body><h1>KUODRA offline SEC + ML co-review</h1>'
            '<p>Independent evidence only; issuer-level cross-source linkage NOT established.</p>'
            '<pre>' + escaped + '</pre></body></html>')
