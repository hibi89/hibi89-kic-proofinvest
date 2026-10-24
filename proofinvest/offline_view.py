"""Deterministic, read-only display model for a single bundled SYNTHETIC fixture.

No user-supplied filenames, live adapters, network clients, or API keys here.
This is NOT the verified-only Risk workflow and cannot authenticate filings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .engine import calculate

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_annual.json"


def load_synthetic_snapshot() -> dict[str, Any]:
    """Load only the version-controlled demo file and produce display-safe data."""
    rows = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Synthetic fixture is missing or malformed")
    if any(
        not isinstance(r, dict)
        or r.get("fs_div") not in ("CFS", "OFS")
        or r.get("rcept_no") not in (None, "")
        or r.get("currency") != "KRW"
        for r in rows
    ):
        raise ValueError("Fixture must contain only local synthetic KRW records without filing references")
    report = calculate(rows, 2024, claim_revenue_growth_pct="20", is_demo=True)
    if report.get("source_kind") != "SYNTHETIC_FIXTURE" or report.get("status") != "demo_not_real":
        raise ValueError("Cannot show a non-synthetic calculation in offline demo")
    checks = report.get("checks", [])
    risks = report.get("risk_signals", [])
    if len(checks) != 1 or len(risks) != 1:
        raise ValueError("Unsupported synthetic report structure")
    risk = risks[0]
    signal = risk.get("triggered")
    return {
        "mode": "OFFLINE_SYNTHETIC_READ_ONLY",
        "source_kind": "SYNTHETIC_FIXTURE",
        "year": 2024,
        "authenticated_external_source": False,
        "live_api_called": False,
        "financial_rows": [
            {
                "계정": r["account_nm"],
                "범위": r["fs_div"],
                "당기 금액 (KRW)": r["thstrm_amount"],
                "전기 금액 (KRW)": r["frmtrm_amount"],
            }
            for r in rows
        ],
        "checks": [
            {
                "지표": x["metric"],
                "구조상 상태": x["state"],
                "계산 결과": x.get("value") if x.get("value") is not None else "계산 보류",
                "실제 원문 인증": "아니오",
            }
            for x in checks
        ],
        "risk": {
            "지표": "부채/자본 비율 (탐색)",
            "표시 비율": risk.get("value") if risk.get("value") is not None else "계산 보류",
            "판정": (
                "판정 보류" if signal is None else
                "시연용 임계값 도달" if signal else
                "시연용 임계값 미도달"
            ),
            "보류 사유": risk.get("withheld_reason_code") or "없음",
            "실제 원문 인증": "아니오",
        },
    }
