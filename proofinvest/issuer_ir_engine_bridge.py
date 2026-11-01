"""P108: bounded historical issuer-IR -> existing offline A/B/C engines.

Never fetch SEC, prices or peer data. A/C are optional operator-provided
unverified sources. The vetted P106 *historical* issuer-IR manual reference
is NOT a replacement for independently authenticated SEC financials.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .industry_vision import (
    MAX_UPLOAD_BYTES as INDUSTRY_MAX, analyze_industry_vision,
    parse_industry_vision_json,
)
from .issuer_ir_replay import ISSUER_URL, replay
from .local_sec_packet import _read_regular_local
from .market_price_csv import market_price_csv_to_json
from .market_reality import (
    MAX_UPLOAD_BYTES as MARKET_MAX, analyze_market_reality,
    parse_market_reality_json,
)

CIK = "0001045810"  # NVDA CIK as recorded; not independently certified here
IR_RELEASE = "2025-02-26"
PRIOR_END = "2024-01-28"
CURRENT_END = "2025-01-26"


def _slot(code: str) -> dict:
    return {"status": "UNAVAILABLE", "reason_code": code,
            "source_authenticated": False, "rights_verified": False,
            "input_sha256": None}


def _empty() -> dict[str, Any]:
    return {
        "schema": "kuodra.historical-ir-three-engine-bridge.v1",
        "status": "UNAVAILABLE",
        "reason_code": "HISTORICAL_ISSUER_EVIDENCE_REQUIRED",
        "issuer": {"ticker": "NVDA", "cik_reported": CIK},
        "as_of": None, "source": {"kind": "HISTORICAL_MANUAL_ISSUER_IR",
                                 "url": ISSUER_URL, "published_at": IR_RELEASE,
                                 "evidence_sha256": None,
                                 "origin_authenticated": False,
                                 "redistribution_rights_verified": False},
        "engine_a": _slot("MARKET_CSV_NOT_PROVIDED"),
        "engine_b": _slot("ISSUER_IR_EVIDENCE_UNAVAILABLE"),
        "engine_c": _slot("PEER_AND_SECTOR_JSON_NOT_PROVIDED"),
        "guard": {"decision": "HOLD", "human_approval_granted": False},
        "full_abc_authenticated": False, "live_data_retrieved": False,
        "sec_accessed": False, "network_requests": 0, "llm_called": False,
        "audit_written": False, "trade_executed": False,
    }


def _asof(value: str) -> str | None:
    if type(value) is not str or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value or parsed < date.fromisoformat(IR_RELEASE) or parsed > date.today():
            return None
        return value
    except ValueError:
        return None


def _match_ir(receipt: dict) -> bool:
    if (type(receipt) is not dict
            or receipt.get("schema") != "kuodra.issuer-ir-replay.v1"
            or receipt.get("mode") != "HISTORICAL_MANUAL_ISSUER_IR_OFFLINE"
            or receipt.get("ticker") != "NVDA"
            or receipt.get("source_url") != ISSUER_URL
            or receipt.get("source_publication_date") != IR_RELEASE
            or receipt.get("unit") != "USD_MILLIONS"
            or receipt.get("external_network_requests") != 0
            or receipt.get("source_authenticated") is not False
            or receipt.get("rights_to_redistribute_verified") is not False
            or receipt.get("sec_accessed") is not False
            or receipt.get("ai_agent_executed") is not False
            or receipt.get("trade_executed") is not False
            or receipt.get("guard_decision") != "HOLD"):
        return False
    digest = receipt.get("evidence_sha256")
    metrics = receipt.get("metrics")
    if (type(digest) is not str or len(digest) != 64
            or any(x not in "0123456789abcdef" for x in digest)
            or type(metrics) is not dict
            or receipt.get("arithmetic_state") not in ("verified", "conflict", "unavailable")):
        return False
    try:
        return (Decimal(metrics["fy2025_revenue"]) == Decimal("130497")
                and Decimal(metrics["fy2024_revenue"]) == Decimal("60922")
                and Decimal(metrics["revenue_yoy_pct"]) == Decimal("114.20")
                and Decimal(metrics["fy2025_cash_conversion_pct"]) == Decimal("87.94"))
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False


def analyze_historical_ir_engines(
    *, as_of: str = "2025-10-16", claim_pct: str = "114.20",
    price_csv: bytes | None = None, price_source_url: str | None = None,
    price_published_at: str | None = None, benchmark: str = "NASDAQ_100",
    return_basis: str = "PRICE_ONLY_CLOSE",
    industry_json: bytes | None = None,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """One historical issuer, optional A/C. Failure never grants Guard approval.

    The only issuer financials are pinned P106 manually transcribed figures.
    A/C inputs must match issuer, as-of and fiscal/release boundaries.
    No arbitrary ticker accepts the NVDA data; no price/peer vendor connected.
    """
    out = _empty()
    valid_asof = _asof(as_of)
    if valid_asof is None:
        out["reason_code"] = "AS_OF_OUTSIDE_HISTORICAL_EVIDENCE_WINDOW"
        return out
    out["as_of"] = valid_asof
    receipt = replay(claim_pct) if evidence_path is None else replay(claim_pct, evidence_path)
    if not _match_ir(receipt):
        return out

    data = receipt["metrics"]
    out["source"]["evidence_sha256"] = receipt["evidence_sha256"]
    out["engine_b"] = {
        "status": "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY",
        "reason_code": "ISSUER_IR_NOT_SEC_OR_FRAUD_VERDICT",
        "input_sha256": receipt["evidence_sha256"],
        "published_at": IR_RELEASE, "fy2025_end": CURRENT_END,
        "fy2024_end": PRIOR_END,
        "revenue_yoy_pct": data["revenue_yoy_pct"],
        "cash_conversion_pct": data["fy2025_cash_conversion_pct"],
        "receivables_yoy_pct": data["accounts_receivable_yoy_pct"],
        "claim_status": receipt["arithmetic_state"],
        "source_authenticated": False, "rights_verified": False,
        "misconduct_proven": False,
    }
    out["status"] = "HISTORICAL_PARTIAL_UNAUTHENTICATED"
    out["reason_code"] = "OPTIONAL_A_C_OPERATOR_INPUTS_NOT_AUTHENTICATED"

    if price_csv is not None:
        try:
            if (type(price_source_url) is not str
                    or type(price_published_at) is not str):
                raise ValueError("PRICE_PROVENANCE_METADATA_REQUIRED")
            normalized = market_price_csv_to_json(
                price_csv, issuer_cik=CIK, as_of=valid_asof,
                symbol="NVDA", benchmark=benchmark, return_basis=return_basis,
                source_url=price_source_url, published_at=price_published_at,
            )
            parsed = parse_market_reality_json(normalized)
            report = analyze_market_reality(
                parsed, expected_issuer_cik=CIK,
                analysis_as_of=valid_asof,
                uploaded_sha256=sha256(price_csv).hexdigest(),
            )
            if (report["status"] not in (
                    "REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                    or date.fromisoformat(report["period_start"]) <=
                    date.fromisoformat(IR_RELEASE)
                    or report["sec_revenue_context"] is not None
                    or report["source_authenticated"] is not False
                    or report["audit_included"] is not False
                    or report["market_bubble_proven"] is not False
                    or report["guard_policy_modified"] is not False
                    or report["trade_signal"] is not False):
                raise ValueError("PRICE_IR_COHORT_OR_TRUST_MISMATCH")
            out["engine_a"] = {
                "status": report["status"],
                "reason_code": "DESCRIPTIVE_PRICE_OLS_NOT_BUBBLE_SCORE",
                "input_sha256": sha256(price_csv).hexdigest(),
                "period_start": report["period_start"],
                "period_end": report["period_end"],
                "benchmark": report["benchmark"],
                "return_basis": report["return_basis"],
                "observations": report["observation_count"],
                "security_return_pct": report["security_return_pct"],
                "benchmark_return_pct": report["benchmark_return_pct"],
                "beta": report["beta"], "r_squared": report["r_squared"],
                "source_authenticated": False, "rights_verified": False,
                "price_vintage_authenticated": False,
            }
        except (ValueError, TypeError, KeyError, OSError, OverflowError,
                RecursionError, InvalidOperation):
            out["engine_a"] = _slot("MARKET_CSV_OR_IR_PUBLICATION_COHORT_INVALID")

    if industry_json is not None:
        try:
            raw = parse_industry_vision_json(industry_json)
            industry = analyze_industry_vision(
                raw, expected_issuer_cik=CIK, analysis_as_of=valid_asof)
            target = industry["target"]
            periods = industry["periods"]
            if (industry["status"] not in
                    ("OBSERVED_COMPARISON_UNVERIFIED", "INSUFFICIENT_EVIDENCE")
                    or periods != {"prior_end": PRIOR_END, "current_end": CURRENT_END}
                    or target["cik"] != CIK
                    or target["name"] != "NVIDIA Corporation"
                    or Decimal(target["prior_revenue_usd"]) !=
                    Decimal(data["fy2024_revenue"]) * 1000000
                    or Decimal(target["current_revenue_usd"]) !=
                    Decimal(data["fy2025_revenue"]) * 1000000
                    or Decimal(target["growth_pct_reported_input"]) !=
                    Decimal(data["revenue_yoy_pct"])
                    or len(industry["peers"]) < 1
                    or industry["source_authenticated"] is not False
                    or industry["industry_outlook_verified"] is not False
                    or industry["guard_decision_changed"] is not False
                    or industry["trade_signal"] is not False):
                raise ValueError("INDUSTRY_FISCAL_OR_TRUST_MISMATCH")
            sources = {x["id"]: x for x in industry["sources"]}
            for src_id in target["source_ids"]:
                record = sources[src_id]
                if (record["sha256"] != receipt["evidence_sha256"]
                        or record["url"] != ISSUER_URL
                        or record["published_at"] != IR_RELEASE):
                    raise ValueError("INDUSTRY_TARGET_SOURCE_NOT_PINNED_TO_IR")
            out["engine_c"] = {
                "status": industry["status"],
                "reason_code": "USER_SUPPLIED_PEERS_SECTOR_NOT_VERIFIED",
                "input_sha256": sha256(industry_json).hexdigest(),
                "industry": industry["industry"],
                "peer_count": len(industry["peers"]),
                "peer_median_growth_pct": industry["peer_median_growth_pct"],
                "gap_to_industry_pp": industry["growth_gap_to_industry_pp"],
                "gap_to_peer_median_pp": industry["growth_gap_to_peer_median_pp"],
                "source_authenticated": False, "rights_verified": False,
                "outlook_verified": False,
            }
        except (ValueError, TypeError, KeyError, OSError, OverflowError,
                RecursionError, InvalidOperation, AttributeError):
            out["engine_c"] = _slot("INDUSTRY_SOURCE_OR_IR_FISCAL_COHORT_INVALID")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NVIDIA historical IR + local A/C, zero external requests")
    parser.add_argument("--as-of", default="2025-10-16")
    parser.add_argument("--claim", default="114.20")
    parser.add_argument("--market-csv", type=Path)
    parser.add_argument("--market-source-url")
    parser.add_argument("--market-published-at")
    parser.add_argument("--benchmark", default="NASDAQ_100")
    parser.add_argument("--return-basis", default="PRICE_ONLY_CLOSE")
    parser.add_argument("--industry-json", type=Path)
    args = parser.parse_args(argv)
    try:
        market = (_read_regular_local(args.market_csv, MARKET_MAX)
                  if args.market_csv is not None else None)
        industry = (_read_regular_local(args.industry_json, INDUSTRY_MAX)
                    if args.industry_json is not None else None)
        result = analyze_historical_ir_engines(
            as_of=args.as_of, claim_pct=args.claim, price_csv=market,
            price_source_url=args.market_source_url,
            price_published_at=args.market_published_at,
            benchmark=args.benchmark, return_basis=args.return_basis,
            industry_json=industry,
        )
        print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0 if result["status"] == "HISTORICAL_PARTIAL_UNAUTHENTICATED" else 2
    except (OSError, ValueError, TypeError):
        print(json.dumps({"status": "UNAVAILABLE",
                          "reason_code": "LOCAL_SOURCE_FILE_INVALID",
                          "network_requests": 0, "trade_executed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
