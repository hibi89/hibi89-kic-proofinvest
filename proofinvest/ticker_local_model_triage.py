"""Opt-in localhost-only model triage over *redacted* KUODRA evidence.

A locally running Ollama-compatible endpoint chooses the review focus engine.
No raw SEC/stock/index/peer originals, source paths, token, private PDF, or
evidence hashes are sent. Only authored status codes and bounded numeric gap
may leave this Python process, to 127.0.0.1 only with two explicit opt-ins.

A local HTTP response cannot authenticate a real model, vendor rights or
data provenance. Human review, Guard HOLD and zero trading remain mandatory.
"""
from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.request
from typing import Any

from .ticker_review_packet import inspect_review_packet_bytes
from .ticker_source_clearance_packet import inspect_source_clearance_packet

_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z", re.ASCII)
_STATUS = "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN"
_TIMEOUT = 8
_MAX_REQUEST = 2048
_MAX_RESPONSE = 8192


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _blocked(reason: str, *, calls: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-model-triage.v1",
        "status": "BLOCKED", "reason_code": reason,
        "loopback_http_attempts": calls,
        "external_network_requests": 0,
        "source_authenticated": False,
        "source_rights_verified": False,
        "model_inference_authenticated": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "human_approved": False,
        "guard_policy_preview": "HOLD", "trade_executed": False,
        "external_sharing_allowed": False,
    }


def _json_no_duplicate(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("MODEL_DUPLICATE_JSON")
            result[key] = value
        return result
    def no_nan(_text):
        raise ValueError("MODEL_NONFINITE")
    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=no_nan,
    )


def _call_loopback(raw: bytes, *, port: int) -> bytes:
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("MODEL_LOCAL_PORT_INVALID")
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_REQUEST:
        raise ValueError("MODEL_REQUEST_TOO_LARGE")
    # No proxy, redirect, DNS, TLS downgrade, arbitrary URL or remote host.
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/generate", data=raw,
        method="POST", headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
    )
    try:
        with opener.open(request, timeout=_TIMEOUT) as response:
            if (response.status != 200 or response.geturl() != request.full_url
                    or response.headers.get("Content-Type", "").split(";", 1)[0]
                    .strip().lower() != "application/json"
                    or response.headers.get("Content-Encoding", "identity").lower()
                    != "identity"):
                raise ValueError("MODEL_HTTP_RESPONSE_INVALID")
            raw_reply = response.read(_MAX_RESPONSE + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            OSError, http.client.HTTPException) as exc:
        raise ValueError("MODEL_LOCAL_HTTP_UNAVAILABLE") from None
    if not 0 < len(raw_reply) <= _MAX_RESPONSE:
        raise ValueError("MODEL_RESPONSE_SIZE_INVALID")
    return raw_reply


def triage_review(
    review_packet: bytes, rights_report: bytes, *,
    model: str = "llama3.2", port: int = 11434,
    allow_local_model: bool = False,
    confirm_local_derivative_processing: bool = False,
) -> dict[str, Any]:
    """Select one independently validated A/B/C review focus, never an advice.

    The caller must manually consent to sending only derived summary data to
    the user-selected local model endpoint. The server may be configured by a
    third party; this function cannot prove what runs behind its loopback port.
    """
    if (allow_local_model is not True
            or confirm_local_derivative_processing is not True):
        return _blocked("EXPLICIT_LOCAL_MODEL_AND_DERIVATIVE_CONSENT_REQUIRED")
    if (type(model) is not str or _MODEL.fullmatch(model) is None
            or type(port) is not int or not 1024 <= port <= 65535):
        return _blocked("MODEL_NAME_OR_LOCAL_PORT_INVALID")
    try:
        checked = inspect_review_packet_bytes(review_packet)
        linked = inspect_source_clearance_packet(
            rights_report, review_packet=review_packet,
        )
        if (checked.get("status")
                != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"
                or linked.get("status")
                != "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING"
                or checked.get("source_rights_verified") is not False
                or linked.get("source_rights_verified") is not False):
            return _blocked("UNVERIFIED_REVIEW_PAIR_REQUIRED")
        packet = _json_no_duplicate(review_packet)
        findings = packet["explanation"]["findings"]
        if (len(findings) != 3
                or [f["engine"] for f in findings] != ["A", "B", "C"]
                or packet["guard_policy_preview"] != "HOLD"):
            return _blocked("REVIEW_FINDINGS_INVALID")
        # Only source-derived *statuses* sent. No ticker, issuer, CIK, filing,
        # source URLs/hashes, market close rows, price/growth, or original text.
        context = {
            "A": findings[0]["status"],
            "B": findings[1]["status"],
            "C": findings[2]["status"],
        }
        instruction = (
            "Choose which of A, B or C a human should inspect first. "
            "These are only UNVERIFIED local status codes, not a certified "
            "SEC/market feed. Return ONLY JSON with exactly "
            '{"focus_engine":"A|B|C","decision":"HUMAN_REVIEW_ONLY"}. '
            "Do not make recommendations, infer missing data or cite originals. "
            "Status codes: " + json.dumps(context, sort_keys=True) + "."
        )
        request = json.dumps({
            "model": model, "prompt": instruction, "stream": False,
            "format": "json", "options": {"temperature": 0, "num_predict": 80},
        }, sort_keys=True, separators=(",", ":")).encode()
        if len(request) > _MAX_REQUEST:
            return _blocked("MODEL_REQUEST_TOO_LARGE")
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError,
            OverflowError, RecursionError):
        return _blocked("REVIEW_PACKET_OR_CLEARANCE_INVALID")
    try:
        response = _json_no_duplicate(_call_loopback(request, port=port))
        if (type(response) is not dict or response.get("done") is not True
                or response.get("model") != model
                or type(response.get("response")) is not str
                or not 0 < len(response["response"]) <= 512):
            raise ValueError("MODEL_ENVELOPE_INVALID")
        proposal = _json_no_duplicate(response["response"].encode())
        if (type(proposal) is not dict
                or set(proposal) != {"focus_engine", "decision"}
                or proposal.get("focus_engine") not in ("A", "B", "C")
                or proposal.get("decision") != "HUMAN_REVIEW_ONLY"):
            raise ValueError("MODEL_FREE_TEXT_OR_ADVICE_REJECTED")
        chosen = next(f for f in findings
                      if f["engine"] == proposal["focus_engine"])
        # Only trusted deterministic authored text, never model free-text.
        return {
            **_blocked("", calls=1),
            "status": _STATUS, "reason_code": "DERIVED_STATUS_TRIAGE_ONLY",
            "review_packet_sha256": checked["packet_sha256"],
            "focus_engine": chosen["engine"],
            "focus_status": chosen["status"],
            "safe_existing_interpretation": chosen["interpretation"],
            "model_protocol_http_verified": True,
            "model_inference_authenticated": False,
        }
    except (ValueError, UnicodeError, TypeError, KeyError, StopIteration,
            OverflowError, RecursionError):
        return _blocked("MODEL_RESPONSE_OR_LOCAL_HTTP_INVALID", calls=1)
