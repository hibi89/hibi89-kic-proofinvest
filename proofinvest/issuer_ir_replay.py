"""Bounded historical issuer-IR arithmetic replay; never SEC, live API or trade.

The issuer IR numbers were manually transcribed from a public Feb-2025 issuer
press release. The file and its SHA256 prove only local byte consistency;
neither authenticates the publisher nor certifies redistribution rights.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from typing import Any

EVIDENCE_PATH = (Path(__file__).resolve().parents[1] / "docs" / "evidence" /
                 "nvda_fy2025_issuer_ir.json")
ISSUER_URL = ("https://investor.nvidia.com/news/press-release-details/2025/"
              "NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2025/")
EXPECTED = {
    "schema": "kuodra.issuer-ir-manual-financials.v1",
    "ticker": "NVDA",
    "issuer": "NVIDIA Corporation",
    "source_type": "ISSUER_IR_PRESS_RELEASE_UNAUDITED",
    "source_url": ISSUER_URL,
    "publication_date": "2025-02-26",
    "source_review_date": "2026-11-02",
    "source_review_method": "manual_web_review_not_authenticated_live_fetch",
    "unit": "USD_MILLIONS",
    "basis": "GAAP_CONSOLIDATED",
}
DATES = {"FY2025": "2025-01-26", "FY2024": "2024-01-28"}
METRICS = ("revenue", "net_income", "operating_cash_flow", "accounts_receivable_net")
TWO_DP = Decimal("0.01")
# Exact manually reviewed FY25/FY24 values, not issuer-site authentication.
REVIEWED_AMOUNTS = {
    "FY2025": ("130497", "72880", "64089", "23065"),
    "FY2024": ("60922", "29760", "28090", "9999"),
}


def _parse_claim(value: Any) -> Decimal | None:
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        out = Decimal(value)
        return out if out.is_finite() and abs(out) <= Decimal("1000000") else None
    except InvalidOperation:
        return None


def _read_checked(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    if len(raw) > 8192:
        raise ValueError("Evidence exceeds 8192 bytes")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Evidence is not valid UTF-8 JSON") from exc
    if not isinstance(record, dict) or set(record) != set(EXPECTED) | {"periods"}:
        raise ValueError("Unexpected issuer-IR evidence schema")
    if any(record[key] != expected for key, expected in EXPECTED.items()):
        raise ValueError("Issuer, publication, basis, or source metadata mismatch")
    periods = record["periods"]
    if not isinstance(periods, dict) or set(periods) != set(DATES):
        raise ValueError("Expected exactly FY2024/FY2025")
    for period, end in DATES.items():
        row = periods[period]
        if not isinstance(row, dict) or set(row) != set(METRICS) | {"fiscal_end"}:
            raise ValueError("Unexpected financial metrics")
        if row["fiscal_end"] != end or not date.fromisoformat(end) < date.fromisoformat(EXPECTED["publication_date"]):
            raise ValueError("Inconsistent fiscal dates")
        for key in METRICS:
            value = row[key]
            if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
                raise ValueError("Financial value must be nonnegative integer USD millions")
            if len(value) > 12 or Decimal(value) <= 0:
                raise ValueError("Unrepresentable or nonpositive financial amount")
        if tuple(row[key] for key in METRICS) != REVIEWED_AMOUNTS[period]:
            raise ValueError("Manual issuer facts differ from reviewed reference")
    return record, digest


def _pct(numerator: Decimal, denominator: Decimal) -> str:
    return str(((numerator / denominator) * Decimal("100")).quantize(TWO_DP, rounding=ROUND_HALF_UP))


def replay(claim_pct: str = "114.20", evidence_path: Path = EVIDENCE_PATH) -> dict[str, Any]:
    """Compute bounded historic GAAP indicators; fail closed on altered inputs."""
    result: dict[str, Any] = {
        "schema": "kuodra.issuer-ir-replay.v1",
        "mode": "HISTORICAL_MANUAL_ISSUER_IR_OFFLINE",
        "ticker": "NVDA",
        "fiscal_year": "FY2025",
        "source_url": ISSUER_URL,
        "source_kind": EXPECTED["source_type"],
        "source_publication_date": EXPECTED["publication_date"],
        "unit": "USD_MILLIONS",
        "arithmetic_state": "unavailable",
        "claim_pct": claim_pct,
        "source_authenticated": False,
        "sec_accessed": False,
        "external_network_requests": 0,
        "rights_to_redistribute_verified": False,
        "original_filing_verified": False,
        "full_engine_abc_executed": False,
        "ai_agent_executed": False,
        "guard_decision": "HOLD",
        "trade_executed": False,
        "risk_of_misconduct_concluded": False,
        "evidence_sha256": None,
        "metrics": None,
        "reason": "Historical issuer IR evidence not validated",
    }
    try:
        record, digest = _read_checked(evidence_path)
        rows = record["periods"]
        curr, prev = ({key: Decimal(rows[period][key]) for key in METRICS}
                      for period in ("FY2025", "FY2024"))
        revenue_growth = Decimal(_pct(curr["revenue"] - prev["revenue"], prev["revenue"]))
        result["evidence_sha256"] = digest
        result["metrics"] = {
            "fy2025_revenue": str(curr["revenue"]),
            "fy2024_revenue": str(prev["revenue"]),
            "revenue_yoy_pct": str(revenue_growth),
            "fy2025_operating_cash_flow": str(curr["operating_cash_flow"]),
            "fy2025_net_income": str(curr["net_income"]),
            "fy2025_cash_conversion_pct": _pct(curr["operating_cash_flow"], curr["net_income"]),
            "fy2024_cash_conversion_pct": _pct(prev["operating_cash_flow"], prev["net_income"]),
            "accounts_receivable_yoy_pct": _pct(curr["accounts_receivable_net"] - prev["accounts_receivable_net"], prev["accounts_receivable_net"]),
        }
        claim = _parse_claim(claim_pct)
        if claim is None:
            result["reason"] = "Missing or non-finite claim"
        elif abs(claim - revenue_growth) <= Decimal("0.10"):
            result["arithmetic_state"] = "verified"
            result["reason"] = "Claim agrees with transcribed issuer-IR arithmetic; source authentication NOT established"
        else:
            result["arithmetic_state"] = "conflict"
            result["reason"] = "Claim differs from transcribed revenue arithmetic by over 0.10 percentage points"
    except (OSError, ValueError, ArithmeticError, InvalidOperation, TypeError, KeyError):
        result["reason"] = "Missing, malformed or mismatched offline issuer IR evidence"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline historical NVDA IR numbers, no SEC traffic")
    parser.add_argument("--claim", default="114.20", help="Claimed FY2025 revenue growth percent")
    args = parser.parse_args()
    print(json.dumps(replay(args.claim), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
