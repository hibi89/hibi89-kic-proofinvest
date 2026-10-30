"""KUODRA P5: explicit operator request + untrusted proposal -> saved SEC Guard.

This offline connector cannot contact a model or SEC. A proposal is never
authorization: operator-selected issuer, period, input ZIP and persistence
consent are independent, checked AGAIN at the point of ZIP replay. Exactly
one local deterministic SEC verification/Guard/SQLite tool is available.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from .kuodra_capture_replay import replay_saved_capture
from .llm_proposal_gate import PlannerGateError, _strict_proposal
from .local_sec_packet import _read_regular_local

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
_DECIMAL = re.compile(r"[+-]?\d{1,5}(?:\.\d{1,4})?\Z", re.ASCII)
_REQUIRED = frozenset({
    "issuer_cik", "accession", "as_of", "requested_intent", "capture_zip",
    "audit_db", "run_id", "current_end", "prior_end", "needle",
})
_OPTIONAL = frozenset({"claimed_growth_pct"})
_INTENTS = frozenset(("GROWTH_CHECK", "SOURCE_REVIEW", "RISK_CHECK"))



def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for key, value in pairs:
        if key in d:
            raise ValueError("DUPLICATE_JSON_KEY")
        d[key] = value
    return d


def _parse_proposal(proposed: Any) -> tuple[str, str | None]:
    if isinstance(proposed, str):
        if len(proposed.encode("utf-8")) > 2048:
            raise PlannerGateError("MODEL_RESPONSE_TOO_LARGE")
        try:
            proposed = json.loads(proposed, object_pairs_hook=_unique_json_object)
        except (ValueError, UnicodeError, RecursionError):
            raise PlannerGateError("MODEL_RESPONSE_INVALID_JSON") from None
    return _strict_proposal(proposed)


def _calendar_day(s: Any) -> date | None:
    if type(s) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) is None:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _valid_request(req: Any) -> bool:
    if not isinstance(req, Mapping) or set(req) - _OPTIONAL != _REQUIRED:
        return False
    cik = req.get("issuer_cik")
    acc = req.get("accession")
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or cik == "0000000000"
            or type(acc) is not str or _ACCESSION.fullmatch(acc) is None
            or not acc.startswith(cik + "-")
            or req.get("requested_intent") not in _INTENTS):
        return False
    d, current, prior = (_calendar_day(req.get(k)) for k in
                         ("as_of", "current_end", "prior_end"))
    if d is None or current is None or prior is None or not prior < current <= d:
        return False
    rid = req.get("run_id")
    if type(rid) is not str or _RUN_ID.fullmatch(rid) is None:
        return False
    needle = req.get("needle")
    if (type(needle) is not str or not 8 <= len(needle) <= 240
            or any(ord(c) < 32 or ord(c) == 127 for c in needle)):
        return False
    for name in ("capture_zip", "audit_db"):
        value = req.get(name)
        if (type(value) is not str or not 1 <= len(value) <= 1024
                or "\x00" in value):
            return False
    claim = req.get("claimed_growth_pct")
    if req["requested_intent"] != "GROWTH_CHECK" and claim is not None:
        # A source or risk request must not hide a growth-claim contradiction
        # that changes the Guard decision under a separate requested intent.
        return False
    if claim is not None and (type(claim) is not str or
                              _DECIMAL.fullmatch(claim) is None):
        return False
    return True


def _result(reason: str, *, status: str = "blocked") -> dict[str, Any]:
    return {
        "schema": "kuodra.operator-gated-offline-proposal.v1",
        "mode": "EXPLICIT_OPERATOR_REQUEST_UNTRUSTED_PROPOSAL_NOT_LIVE_AI",
        "status": status, "reason_code": reason,
        "selected_intent": None, "model_proposal_accepted": False,
        "local_tool_attempts": 0, "max_local_tool_attempts": 1,
        "external_tool_calls": 0, "network_calls": 0,
        "guard": None, "verification": None, "balance_sheet": None,
        "source_review": None, "audit": None,
        "audit_written": False, "source_authenticated": False,
        "source_rights_verified": False, "ai_agent_executed": False,
        "live_model_called": False, "live_sec_called": False,
        "trade_executed": False, "official_contest_submission": False,
    }


def run_offline_proposal_replay(
    operator_request: Any, proposed: Any, *,
    acknowledge_local_audit_persistence: bool = False,
) -> dict[str, Any]:
    """One local replay at most, never using model-supplied tool parameters."""
    result = _result("INVALID_OPERATOR_REQUEST")
    if not _valid_request(operator_request):
        return result
    try:
        action, intent = _parse_proposal(proposed)
    except (PlannerGateError, UnicodeError) as exc:
        # Strict errors are static codes; never expose model response text.
        result["reason_code"] = (
            str(exc) if isinstance(exc, PlannerGateError)
            else "MODEL_RESPONSE_INVALID_UNICODE"
        )
        return result
    if action == "ASK":
        result.update(status="needs_clarification",
                      reason_code="MODEL_REQUESTS_CLARIFICATION")
        return result
    if intent != operator_request["requested_intent"]:
        result["reason_code"] = "MODEL_INTENT_MISMATCH_OR_UNSUPPORTED"
        return result
    if acknowledge_local_audit_persistence is not True:
        result["reason_code"] = "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED"
        return result
    # Reuse the tested ZIP/Decimal/Guard/SQLite pipeline. The ZIP loader
    # matches the issuer/accession/as_of during the final read, BEFORE write.
    result["selected_intent"] = intent
    result["model_proposal_accepted"] = True
    result["local_tool_attempts"] = 1
    result["audit_written"] = None  # unknown if a local failure occurs
    try:
        report = replay_saved_capture(
            bundle_path=operator_request["capture_zip"],
            audit_db=operator_request["audit_db"],
            run_id=operator_request["run_id"],
            current_end=operator_request["current_end"],
            prior_end=operator_request["prior_end"],
            needle=operator_request["needle"],
            claimed_growth_pct=operator_request.get("claimed_growth_pct"),
            acknowledge_local_audit_persistence=True,
            expected_issuer_cik=operator_request["issuer_cik"],
            expected_accession=operator_request["accession"],
            expected_as_of=operator_request["as_of"],
            required_review_intent=intent if intent != "GROWTH_CHECK" else None,
        )
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error,
            OverflowError, RecursionError):
        result.update(reason_code="OFFLINE_REPLAY_FAILED_CHECK_AUDIT_STATE",
                      model_proposal_accepted=False)
        return result
    if (report.get("status") != "OFFLINE_CAPTURE_REVIEW_RECORDED"
            or report.get("issuer", {}).get("cik") != operator_request["issuer_cik"]
            or report.get("guard", {}).get("decision") not in ("HOLD", "REJECT")
            or report.get("audit_chain_valid") is not True):
        result.update(reason_code="OFFLINE_RESULT_CONTRACT_INVALID",
                      model_proposal_accepted=False)
        return result
    if (intent == "RISK_CHECK" and
            report["balance_sheet"].get("status") != "reviewed_unverified"):
        result.update(reason_code="RISK_REVIEW_RESULT_UNAVAILABLE",
                      model_proposal_accepted=False)
        return result
    if (intent == "SOURCE_REVIEW" and
            report["source_review"].get("exact_raw_byte_span_verified") is not True):
        result.update(reason_code="SOURCE_REVIEW_RESULT_UNAVAILABLE",
                      model_proposal_accepted=False)
        return result
    reason = {
        "GROWTH_CHECK": "OFFLINE_GUARD_AUDIT_RECORDED",
        "SOURCE_REVIEW": "LOCAL_SOURCE_SPAN_REVIEW_UNVERIFIED",
        "RISK_CHECK": "LOCAL_BALANCE_RISK_REVIEW_UNVERIFIED",
    }[intent]
    result.update(status="completed", reason_code=reason,
                  verification=report["verification"], guard=report["guard"],
                  balance_sheet=report["balance_sheet"],
                  source_review=report["source_review"],
                  audit=report["audit"], audit_written=True)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Offline operator-approved proposal -> saved SEC Guard audit. NO model/network.")
    p.add_argument("--operator-request-json", type=Path, required=True)
    p.add_argument("--proposal-json", type=Path, required=True)
    p.add_argument("--acknowledge-local-audit-persistence", action="store_true")
    args = p.parse_args(argv)
    try:
        request = json.loads(
            _read_regular_local(args.operator_request_json, 16_384).decode("utf-8"),
            object_pairs_hook=_unique_json_object,
        )
        proposal = _read_regular_local(args.proposal_json, 2_048).decode("utf-8")
        report = run_offline_proposal_replay(
            request, proposal,
            acknowledge_local_audit_persistence=args.acknowledge_local_audit_persistence,
        )
    except (ValueError, UnicodeError, TypeError, OSError, RecursionError):
        report = _result("INVALID_LOCAL_OPERATOR_OR_PROPOSAL_FILE")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] in ("completed", "needs_clarification") else 2


if __name__ == "__main__":
    raise SystemExit(main())
