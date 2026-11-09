"""Bounded offline question -> authorized SEC/ML tools -> guarded local review.

Deterministic tool selection, NOT a generative agent or an institution IAM
boundary. Only caller-supplied offline files and an already owner-scoped
in-memory dataset vault are accepted. Audit SQLite is written only with a
separate explicit caller acknowledgment. SEC and ML issuers are NEVER joined.
No cloud calls, live SEC requests, data export, trading or model persistence.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
import re
from typing import Any

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES

from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from .kuodra_review_report import _canonical, build_owner_group_review
from .kuodra_sec_ml_review_bridge import build_local_sec_ml_review
from .local_sec_guard_report import (
    _check_audit_path, _pinned_local_source_match, review_local_sec_with_guard,
)
from .local_sec_packet import _MAX_FILE_BYTES

_SCHEMA = "kuodra.local-question-tool-review.v1"
_SOURCE_KEYS = frozenset(("submissions_json", "companyfacts_json", "original_filing"))
_SEC_REQUIRED = frozenset((
    "cik", "accession", "as_of", "collected_at", "current_end", "prior_end",
    "needle", "audit_db_path", "run_id", "expected_source_sha256",
))
_SEC_OPTIONAL = frozenset(("claimed_growth_pct",))
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_RESTRICTED_POLICY = {
    "public_export_allowed": False, "external_llm_allowed": False,
    "trade_authorized": False, "real_sec_origin_verified": False,
    "source_rights_verified": False, "institution_host_iam_verified": False,
    "os_no_egress_verified": False, "production_ready": False,
}


def _has(q: str, phrases: tuple[str, ...]) -> bool:
    for p in phrases:
        if p.isascii() and p.replace("-", "").replace(" ", "").isalpha():
            if re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", q):
                return True
        elif p in q:
            return True
    return False


def plan_local_question(question: Any) -> dict[str, Any]:
    """Pure side-effect-free tool planning, refusing ambiguity and trade intent."""
    if (type(question) is not str or not 5 <= len(question.strip()) <= 200
            or any(ord(x) < 32 or ord(x) == 127 for x in question)
            or _has(question.casefold(), ("https://", "www.", ".env", "api_key", "<script"))):
        return {"status": "BLOCKED", "reason_code": "QUESTION_INVALID", "mode": None,
                "selected_tools": (), "tool_budget": 2}
    q = question.casefold()
    if _has(q, ("매수", "매도", "자동매매", "매매 실행", "주문", "입금", "buy", "sell",
                "trade", "execute order", "publish", "외부 전송", "외부전송")):
        return {"status": "BLOCKED", "reason_code": "UNAUTHORIZED_ACTION_INTENT",
                "mode": None, "selected_tools": (), "tool_budget": 2}
    sec = _has(q, ("sec", "공시", "원문", "10-k", "filing"))
    ml = _has(q, ("ml", "다변수", "머신러닝", "상관관계", "회귀모델", "모델 분석", "machine learning"))
    if not (sec or ml):
        return {"status": "NEEDS_CLARIFICATION", "reason_code": "TOOL_INTENT_MISSING",
                "mode": None, "selected_tools": (), "tool_budget": 2}
    mode = "SEC_ML" if sec and ml else "SEC_ONLY" if sec else "ML_ONLY"
    tools = (("OWNER_ML", "LOCAL_SEC_GUARD", "RESTRICTED_CO_REVIEW")
             if mode == "SEC_ML" else
             ("OWNER_ML",) if ml else ("LOCAL_SEC_GUARD",))
    return {"status": "READY", "reason_code": "OFFLINE_TOOL_PLAN",
            "mode": mode, "selected_tools": tools, "tool_budget": 2}


def _blocked(reason: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
            "selected_tools": [], "tool_calls": 0, "audit_written": False,
            "network_requests": 0, "llm_agent_executed": False,
            **_RESTRICTED_POLICY}


def _check_local_sec_inputs(raw: Any, options: Any) -> bool:
    """Pin real caller bytes BEFORE any SQLite/ML tool side effect."""
    if (type(raw) is not dict or set(raw) != _SOURCE_KEYS
            or type(options) is not dict
            or not _SEC_REQUIRED.issubset(options)
            or not set(options).issubset(_SEC_REQUIRED | _SEC_OPTIONAL)
            or type(options.get("claimed_growth_pct")) not in (str, type(None))
            or any(type(options.get(k)) is not str or not options[k]
                   for k in _SEC_REQUIRED - {"audit_db_path", "expected_source_sha256"})):
        return False
    if (any(type(raw[k]) is not bytes or not 0 < len(raw[k]) <= limit
            for k, limit in (
                ("submissions_json", MAX_JSON_BYTES),
                ("companyfacts_json", _MAX_FILE_BYTES),
                ("original_filing", MAX_FILING_BYTES),
            ))):
        return False
    pins = options["expected_source_sha256"]
    if (type(pins) is not dict
            or set(pins) != {"submissions", "companyfacts", "original_filing"}
            or any(type(value) is not str or _SHA.fullmatch(value) is None
                   for value in pins.values())):
        return False
    # No self-attestation: operator-supplied SHA pins are checked against
    # raw bytes instead of deriving "expected" hashes from these same bytes.
    if _pinned_local_source_match(
            pins, submissions=raw["submissions_json"],
            companyfacts=raw["companyfacts_json"],
            original=raw["original_filing"]) is not True:
        return False
    _check_audit_path(options["audit_db_path"])
    return True


def _safe_sec_review(report: dict[str, Any]) -> dict[str, Any]:
    """Allowlist signed-audit result fields only; never return raw SEC contents."""
    if (type(report) is not dict
            or report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or report.get("audit_chain_valid") is not True
            or report.get("human_review_integrity_valid") is not True
            or report.get("operator_reviewed_source_digests_matched") is not True
            or type(report.get("guard")) is not dict
            or report["guard"].get("decision") not in ("HOLD", "REJECT")
            or report["guard"].get("source_authenticated") is not False
            or type(report.get("limits")) is not dict
            or any(k not in report["limits"] or report["limits"][k] is not False
                   for k in ("external_source_authenticated", "source_rights_verified",
                             "live_api_called", "ai_agent_executed", "trade_executed",
                             "simulation_authorized", "official_contest_submission"))):
        raise ValueError("LOCAL_AGENT_SEC_TRUST_CONTRACT_INVALID")
    source, verification = report.get("source"), report.get("verification")
    if (type(source) is not dict or type(verification) is not dict
            or verification.get("status") not in
               ("calculated_unverified", "conflict", "unavailable")
            or (verification["status"] == "conflict"
                and report["guard"]["decision"] != "REJECT")):
        raise ValueError("LOCAL_AGENT_SEC_NUMERIC_CONTRACT_INVALID")
    expected = ("submissions_sha256", "companyfacts_sha256", "archived_original_sha256")
    if any(type(source.get(k)) is not str or _SHA.fullmatch(source[k]) is None
           for k in expected):
        raise ValueError("LOCAL_AGENT_SEC_SOURCE_CONTRACT_INVALID")
    if source.get("source_index_kind") == "PINNED_HISTORY":
        if type(source.get("history_page_sha256")) is not str or not _SHA.fullmatch(
                source["history_page_sha256"]):
            raise ValueError("LOCAL_AGENT_SEC_SOURCE_CONTRACT_INVALID")
        expected += ("history_page_sha256",)
    elif (source.get("source_index_kind") != "RECENT"
          or source.get("history_page_sha256") is not None):
        raise ValueError("LOCAL_AGENT_SEC_SOURCE_CONTRACT_INVALID")
    return {"schema": "kuodra.local-sec-minimal-review.v1",
            "decision": report["guard"]["decision"],
            "numeric_status": verification["status"],
            "source_hashes": {k: source[k] for k in expected},
            "audit_chain_valid": True, "source_authenticated": False,
            "rights_verified": False, "cross_source_entity_link_verified": False}


def run_owner_local_question(
    question: Any, *, vault: OwnerLocalGateway, principal: VerifiedPrincipal,
    private_dataset_id: str | None = None, public_dataset_id: str | None = None,
    target_metric: str | None = None, feature_metrics: tuple[str, ...] | None = None,
    ml_as_of: str | None = None,
    sec_bytes: dict[str, bytes] | None = None,
    sec_options: dict[str, Any] | None = None,
    consent_local_sec_audit: bool = False,
) -> dict[str, Any]:
    """Execute a maximum of two existing core tool calls under local policy.

    The restricted cross-source co-review NEVER asserts that SEC CIK matches
    the owner/private ML issuer IDs. A separately authenticated host and
    no-egress worker are required before actual confidential source usage.
    """
    plan = plan_local_question(question)
    if plan["status"] != "READY":
        return _blocked(plan["reason_code"])
    if (type(vault) is not OwnerLocalGateway
            or type(principal) is not VerifiedPrincipal
            or type(consent_local_sec_audit) is not bool):
        return _blocked("LOCAL_ACCESS_OR_CONSENT_INVALID")
    audit_attempted = False
    try:
        vault._check(principal)
        mode = plan["mode"]
        wants_ml, wants_sec = mode in ("ML_ONLY", "SEC_ML"), mode in ("SEC_ONLY", "SEC_ML")
        if wants_ml:
            if (type(private_dataset_id) is not str or type(target_metric) is not str
                    or type(feature_metrics) is not tuple or type(ml_as_of) is not str):
                return _blocked("LOCAL_ML_CONFIGURATION_REQUIRED")
            vault._check(principal, dataset_id=private_dataset_id)
            if public_dataset_id is not None:
                vault._check(principal, dataset_id=public_dataset_id)
        if wants_sec:
            if consent_local_sec_audit is not True:
                return _blocked("EXPLICIT_LOCAL_SEC_AUDIT_CONSENT_REQUIRED")
            if not _check_local_sec_inputs(sec_bytes, sec_options):
                return _blocked("LOCAL_SEC_PINS_OR_AUDIT_PATH_INVALID")
        elif sec_bytes is not None or sec_options is not None or consent_local_sec_audit:
            return _blocked("UNSELECTED_SEC_TOOL_INPUT_DENIED")
        # All access checks, source pin preflights and consent gates precede
        # the first tool; ML evaluation is read-only and happens before audit.
        ml_packet = None
        if wants_ml:
            ml_packet = build_owner_group_review(
                vault, principal, private_dataset_id=private_dataset_id,
                public_dataset_id=public_dataset_id,
                target_metric=target_metric, feature_metrics=feature_metrics,
                as_of=ml_as_of)
            if (ml_packet.get("decision") != "HOLD"
                    or ml_packet.get("public_export_allowed") is not False):
                raise ValueError("LOCAL_AGENT_ML_POLICY_INVALID")
        sec_report = None
        if wants_sec:
            # The SEC function may persist SQLite before an exception.
            # Never return audit_written=False once this call has started.
            audit_attempted = True
            sec_report = review_local_sec_with_guard(
                **sec_bytes, **sec_options)
            sec_small = _safe_sec_review(sec_report)
        if mode == "SEC_ML":
            restricted = build_local_sec_ml_review(sec_report, ml_packet)
            decision = restricted["decision"]
        elif mode == "ML_ONLY":
            restricted, decision = ml_packet, "HOLD"
        else:
            restricted, decision = sec_small, sec_small["decision"]
    except (PermissionError, ValueError, TypeError, KeyError, OSError) as exc:
        # An audit may have been persisted even if the SEC or bridge step
        # then failed. Never claim a failed audit attempt wrote nothing.
        if audit_attempted:
            raise RuntimeError(
                "LOCAL_SEC_AUDIT_OUTCOME_UNKNOWN_INSPECT_LOCAL_DB") from exc
        # Pre-audit failures are side-effect-free and safely redacted.
        return _blocked("LOCAL_SOURCE_ACCESS_OR_TOOL_REVIEW_FAILED")

    tools = list(plan["selected_tools"])
    packet = {
        "schema": _SCHEMA, "status": "LOCAL_HUMAN_REVIEW_REQUIRED",
        "mode": mode, "selected_tools": tools,
        "tool_calls": 2 if mode == "SEC_ML" else 1,
        "question_sha256": sha256(question.encode("utf-8")).hexdigest(),
        "review": restricted, "decision": decision,
        "trace": (["PLAN", "ACCESS_CHECK", "SOURCE_PINS", "ML_REVIEW",
                    "SEC_GUARD_AUDIT", "RESTRICTED_CO_REVIEW", "HUMAN_REVIEW"]
                  if mode == "SEC_ML" else
                  ["PLAN", "ACCESS_CHECK", "ML_REVIEW", "HUMAN_REVIEW"]
                  if mode == "ML_ONLY" else
                  ["PLAN", "ACCESS_CHECK", "SOURCE_PINS",
                   "SEC_GUARD_AUDIT", "HUMAN_REVIEW"]),
        "audit_written": wants_sec,
        "audit_persistence_consented": wants_sec and consent_local_sec_audit,
        "cross_source_entity_link": (
            "NOT_ESTABLISHED_DO_NOT_JOIN_OR_COMPARE_ISSUERS"
            if mode == "SEC_ML" else "NOT_APPLICABLE"),
        "network_requests": 0, "llm_agent_executed": False,
        "deterministic_tool_router_executed": True,
        "official_contest_submission": False,
        **_RESTRICTED_POLICY,
    }
    packet["receipt_sha256"] = sha256(_canonical(packet)).hexdigest()
    return packet


def render_local_question_html(packet: dict[str, Any]) -> str:
    """Inert, CSP-constrained local preview; validates the complete receipt."""
    if (type(packet) is not dict or packet.get("schema") != _SCHEMA
            or packet.get("status") != "LOCAL_HUMAN_REVIEW_REQUIRED"
            or packet.get("decision") not in ("HOLD", "REJECT")
            or packet.get("public_export_allowed") is not False
            or packet.get("external_llm_allowed") is not False
            or packet.get("trade_authorized") is not False):
        raise ValueError("LOCAL_AGENT_HTML_POLICY_DENIED")
    content = dict(packet)
    digest = content.pop("receipt_sha256", None)
    if type(digest) is not str or _SHA.fullmatch(digest) is None:
        raise ValueError("LOCAL_AGENT_HTML_RECEIPT_INVALID")
    if sha256(_canonical(content)).hexdigest() != digest:
        raise ValueError("LOCAL_AGENT_HTML_RECEIPT_INVALID")
    body = escape(json.dumps(packet, sort_keys=True, ensure_ascii=True,
                             indent=2, allow_nan=False))
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            '<meta http-equiv="Content-Security-Policy" '
            'content="default-src \'none\'; style-src \'unsafe-inline\'; form-action \'none\'">'
            "<title>KUODRA local agent review</title>"
            "<style>body{max-width:960px;margin:2rem auto;font:14px/1.5 system-ui}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere}</style></head>"
            "<body><h1>KUODRA offline tool review</h1><pre>"
            + body + "</pre></body></html>")
