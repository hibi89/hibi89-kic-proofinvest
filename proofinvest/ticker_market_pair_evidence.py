"""P143: exact local seven-stage replay plus in-memory stock/real-index Engine A.

This is a redacted *local* evidence wrapper, not a publisher signature,
licensed display grant, authenticated market timestamp or trading authorization.
The unchanged P117 report remains independently replayable as before.
No HTTP, storage, account change or SEC requests are performed here.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import json
from typing import Any


_SCHEMA = "kuodra.local-seven-step-market-pair-evidence.v1"
_STATUS = "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED"


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "source_authenticated": False, "source_rights_verified": False,
        "guard_executed": False, "audit_written": False,
        "ai_agent_executed": False, "trade_executed": False,
        "external_sharing_allowed": False, "full_a_b_c_ready": False,
    }


def _canonical(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def build_linked_market_evidence(
    *, workflow: Any, sources: Any, stock: Any, index: Any,
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Compute a new derived receipt from the same original in-memory inputs.

    Local financials and optional A/C are independently replayed with their
    exact bytes; the P141 stock/NDX observations are re-fed to Decimal OLS.
    Their claimed vendor hashes are carried as identifiers only: callers
    cannot prove publisher origin or market rights from these receipts alone.
    """
    if (type(workflow) is not dict or type(sources) is not dict
            or type(stock) is not dict or type(index) is not dict):
        return _hold("EVIDENCE_INPUTS_REQUIRED")
    try:
        from .ticker_local_dashboard import summarize_local_ticker_dashboard
        from .ticker_local_report import verify_local_report
        from .market_pair_engine_a import analyze_price_index_pair

        panel = summarize_local_ticker_dashboard(workflow)
        if (panel.get("status") != "LOCAL_SOURCE_REPLAYED_UNVERIFIED"
                or panel.get("guard_policy") != "HOLD"
                or workflow.get("network_requests") != 0
                or workflow.get("tool_calls_executed") != 7
                or workflow.get("guard_executed") is not False):
            return _hold("LOCAL_WORKFLOW_OR_GUARD_NOT_ELIGIBLE")
        check = verify_local_report(
            workflow["report"], sources=sources,
            market_json=market_json, industry_json=industry_json,
        )
        if check.get("status") != "PASS":
            return _hold("INDEPENDENT_LOCAL_REPLAY_FAILED")
        issuer = workflow["report"]["issuer"]
        revenue = workflow["revenue"]
        if (issuer.get("ticker") != panel["ticker"]
                or issuer.get("cik") != panel["cik"]
                or issuer.get("as_of") != panel["as_of"]
                or issuer.get("filing_date") != revenue.get("filing_date")
                or workflow["report"].get("guard_policy_preview") != "HOLD"):
            return _hold("ISSUER_FILING_OR_GUARD_MISMATCH")
        market = analyze_price_index_pair(
            stock=stock, index=index,
            ticker=issuer["ticker"], issuer_cik=issuer["cik"],
            filing_date=issuer["filing_date"], as_of=issuer["as_of"],
            benchmark="NASDAQ_100",
        )
        if (market.get("status") != "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED"
                or market.get("source_authenticated") is not False
                or market.get("source_rights_verified") is not False
                or market.get("guard_executed") is not False
                or market.get("full_a_b_c_ready") is not False
                or market.get("trade_executed") is not False
                or type(market.get("market_analysis")) is not dict):
            return _hold("PRICE_INDEX_REPLAY_OR_TRUST_INVALID")
        facts = market["market_analysis"]
        if facts.get("status") not in ("REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE"):
            return _hold("ENGINE_A_MATH_NOT_ELIGIBLE")
        result = {
            "schema": _SCHEMA,
            "status": _STATUS,
            "reason_code": "REPLAY_IS_NOT_PUBLISHER_AUTHENTICATION",
            "issuer": {
                "ticker": issuer["ticker"], "cik": issuer["cik"],
                "accession": issuer["accession"],
                "as_of": issuer["as_of"],
                "filing_date": issuer["filing_date"],
            },
            "local_report_sha256": workflow["report"]["report_sha256"],
            "four_source_sha256": dict(workflow["report"]["source_sha256"]),
            "local_engine_a": {
                "status": panel["engine_a"]["status"],
                "input_sha256": workflow["report"]["engine_a_input_sha256"],
            },
            "engine_b": {
                "status": panel["engine_b"]["status"],
                "companyfacts_sha256": workflow["engine_b"]["companyfacts_sha256"],
            },
            "engine_c": {
                "status": panel["engine_c"]["status"],
                "input_sha256": workflow["report"]["engine_c_input_sha256"],
            },
            "premium_engine_a": {
                "status": facts["status"], "benchmark": "NASDAQ_100",
                "basis": "PRICE_ONLY_CLOSE",
                "stock_response_sha256": market["stock_response_sha256"],
                "index_response_sha256": market["index_response_sha256"],
                "analysis_payload_sha256": market["source_payload_sha256"],
                "matched_observation_count": market["matched_observation_count"],
                "security_return_pct": facts["security_return_pct"],
                "benchmark_return_pct": facts["benchmark_return_pct"],
                "beta": facts["beta"],
                "regression_intercept_daily_pct": facts["regression_intercept_daily_pct"],
                "r_squared": facts["r_squared"],
            },
            "guard_policy_preview": "HOLD",
            "local_seven_step_replay_passed": True,
            "local_market_pair_math_recomputed": True,
            "provider_response_origin_authenticated": False,
            "market_vintage_authenticated": False,
            "source_authenticated": False,
            "source_rights_verified": False,
            "guard_executed": False, "audit_written": False,
            "ai_agent_executed": False, "trade_executed": False,
            "external_sharing_allowed": False,
            "full_a_b_c_ready": False,
        }
        result["evidence_sha256"] = sha256(_canonical(result)).hexdigest()
        if len(_canonical(result)) > 16384:
            return _hold("EVIDENCE_OUTPUT_TOO_LARGE")
        return result
    except (ValueError, TypeError, KeyError, AttributeError,
            OverflowError, RecursionError, UnicodeError):
        return _hold("EVIDENCE_REPLAY_INPUT_INVALID")


def verify_linked_market_evidence(
    report: Any, *, workflow: Any, sources: Any, stock: Any, index: Any,
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Independently recompute both the original report and market pair.

    Requires the original local bytes and in-memory price receipts. It never
    certifies a vendor-provided hash, contract rights or paid entitlement.
    """
    result = {"schema": "kuodra.local-market-evidence-verification.v1",
              "status": "FAIL", "reason_code": "EVIDENCE_OR_SOURCES_INVALID",
              "local_replay_verified": False, "market_math_recomputed": False,
              "source_authenticated": False, "source_rights_verified": False,
              "network_requests": 0, "trade_executed": False}
    if type(report) is not dict or report.get("schema") != _SCHEMA:
        return result
    try:
        digest = report.get("evidence_sha256")
        if type(digest) is not str or len(digest) != 64:
            return result
        claimed = {k: v for k, v in report.items() if k != "evidence_sha256"}
        if not compare_digest(digest, sha256(_canonical(claimed)).hexdigest()):
            return result
        rebuilt = build_linked_market_evidence(
            workflow=workflow, sources=sources, stock=stock, index=index,
            market_json=market_json, industry_json=industry_json,
        )
        if rebuilt.get("status") != _STATUS or rebuilt != report:
            return result
        result.update(status="PASS", reason_code="EXACT_LOCAL_AND_MARKET_MATH_REPLAY",
                      local_replay_verified=True, market_math_recomputed=True)
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError, UnicodeError):
        pass
    return result


def linked_evidence_json_bytes(report: dict) -> bytes:
    """Export only the exact redacted A/B/C receipt, never caller-added bytes.

    The digest detects inadvertent/tampered output. It is NOT a vendor
    signature or a substitute for verify_linked_market_evidence with inputs.
    """
    import re

    fields = {
        "schema", "status", "reason_code", "issuer", "local_report_sha256",
        "four_source_sha256", "local_engine_a", "engine_b", "engine_c",
        "premium_engine_a", "guard_policy_preview",
        "local_seven_step_replay_passed", "local_market_pair_math_recomputed",
        "provider_response_origin_authenticated", "market_vintage_authenticated",
        "source_authenticated", "source_rights_verified", "guard_executed",
        "audit_written", "ai_agent_executed", "trade_executed",
        "external_sharing_allowed", "full_a_b_c_ready", "evidence_sha256",
    }
    nested = {
        "issuer": {"ticker", "cik", "accession", "as_of", "filing_date"},
        "four_source_sha256": {
            "ticker_map", "submissions", "companyfacts", "original_10k",
        },
        "local_engine_a": {"status", "input_sha256"},
        "engine_b": {"status", "companyfacts_sha256"},
        "engine_c": {"status", "input_sha256"},
        "premium_engine_a": {
            "status", "benchmark", "basis", "stock_response_sha256",
            "index_response_sha256", "analysis_payload_sha256",
            "matched_observation_count", "security_return_pct",
            "benchmark_return_pct", "beta",
            "regression_intercept_daily_pct", "r_squared",
        },
    }
    if (type(report) is not dict or set(report) != fields
            or report.get("schema") != _SCHEMA
            or report.get("status") != _STATUS
            or report.get("reason_code") != "REPLAY_IS_NOT_PUBLISHER_AUTHENTICATION"
            or report.get("guard_policy_preview") != "HOLD"
            or any(type(report.get(k)) is not dict or set(report[k]) != keys
                   for k, keys in nested.items())
            or any(report.get(k) is not False for k in (
                "provider_response_origin_authenticated",
                "market_vintage_authenticated", "source_authenticated",
                "source_rights_verified", "guard_executed", "audit_written",
                "ai_agent_executed", "trade_executed",
                "external_sharing_allowed", "full_a_b_c_ready"))
            or report.get("local_seven_step_replay_passed") is not True
            or report.get("local_market_pair_math_recomputed") is not True
            or report["premium_engine_a"].get("benchmark") != "NASDAQ_100"
            or report["premium_engine_a"].get("basis") != "PRICE_ONLY_CLOSE"):
        raise ValueError("LINKED_EVIDENCE_EXPORT_CONTRACT_INVALID")

    def digest(value: Any) -> bool:
        return (type(value) is str
                and re.fullmatch(r"[0-9a-f]{64}", value) is not None)

    hashed = [report["local_report_sha256"]]
    hashed.extend(report["four_source_sha256"].values())
    hashed.append(report["engine_b"]["companyfacts_sha256"])
    hashed.extend(report["premium_engine_a"][k] for k in (
        "stock_response_sha256", "index_response_sha256",
        "analysis_payload_sha256"))
    if not all(digest(value) for value in hashed):
        raise ValueError("LINKED_EVIDENCE_EXPORT_DIGEST_INVALID")
    for name, allowed in (
        ("local_engine_a", ("REPORTED_UNVERIFIED",
                            "INSUFFICIENT_MARKET_VARIANCE", "UNAVAILABLE")),
        ("engine_c", ("OBSERVED_COMPARISON_UNVERIFIED",
                       "INSUFFICIENT_EVIDENCE", "UNAVAILABLE")),
    ):
        item = report[name]
        if item.get("status") not in allowed:
            raise ValueError("LINKED_EVIDENCE_EXPORT_ENGINE_STATUS_INVALID")
        if ((item["input_sha256"] is not None)
                if item["status"] == "UNAVAILABLE"
                else (not digest(item["input_sha256"]))):
            raise ValueError("LINKED_EVIDENCE_EXPORT_ENGINE_DIGEST_INVALID")
    if report["engine_b"].get("status") not in ("REVIEWED_UNVERIFIED", "UNAVAILABLE"):
        raise ValueError("LINKED_EVIDENCE_EXPORT_ENGINE_B_INVALID")
    issuer = report["issuer"]
    if (type(issuer["ticker"]) is not str
            or re.fullmatch(r"[A-Z0-9.^_-]{1,20}", issuer["ticker"]) is None
            or type(issuer["cik"]) is not str
            or re.fullmatch(r"[0-9]{10}", issuer["cik"]) is None
            or type(issuer["accession"]) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", issuer["accession"]) is None
            or any(type(issuer[k]) is not str
                   or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", issuer[k]) is None
                   for k in ("as_of", "filing_date"))):
        raise ValueError("LINKED_EVIDENCE_EXPORT_ISSUER_INVALID")
    p = report["premium_engine_a"]
    if (p.get("status") not in (
            "REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
            or type(p.get("matched_observation_count")) is not int
            or not 31 <= p["matched_observation_count"] <= 100):
        raise ValueError("LINKED_EVIDENCE_EXPORT_MARKET_INVALID")
    metric = re.compile(r"-?(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,24})?\Z")
    if any(value is not None and (
            type(value) is not str or metric.fullmatch(value) is None)
           for value in (p[k] for k in (
               "security_return_pct", "benchmark_return_pct", "beta",
               "regression_intercept_daily_pct", "r_squared"))):
        raise ValueError("LINKED_EVIDENCE_EXPORT_METRIC_INVALID")
    if (not digest(report.get("evidence_sha256"))
            or not compare_digest(
                report["evidence_sha256"],
                sha256(_canonical({k: v for k, v in report.items()
                                   if k != "evidence_sha256"})).hexdigest())):
        raise ValueError("LINKED_EVIDENCE_EXPORT_HASH_MISMATCH")
    raw = _canonical(report)
    if len(raw) > 16384:
        raise ValueError("LINKED_EVIDENCE_TOO_LARGE")
    return raw
