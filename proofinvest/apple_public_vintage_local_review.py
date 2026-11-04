"""P189: explicit Apple filing-vintage gate before full offline ticker review.

Only a separately invoked operator path. Never downloads SEC/market data,
authenticates caller bytes, grants redistribution/AI rights, or trades.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .apple_public_filing_vintage import check_apple_public_filing_vintage
from .ticker_research_intake import build_ticker_source_plan, _read_bounded
from .ticker_local_workflow import run_local_ticker_workflow
from .ticker_sec_financial_bridge import _KEYS, _LIMITS


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.apple-public-vintage-local-review.v1",
        "status": "BLOCKED",
        "reason_code": reason,
        "filing": None,
        "report": None,
        "source_authenticated": False,
        "source_rights_verified": False,
        "source_filing_bytes_authenticated": False,
        "ai_agent_executed": False,
        "external_network_requests": 0,
        "guard_executed": False,
        "trade_executed": False,
        "official_contest_submission": False,
    }


def review_apple_public_vintage_local_sources(
    *, as_of: str, sources: dict[str, bytes],
) -> dict[str, Any]:
    """Require the checked public AAPL 10-K vintage before local seven-tool replay.

    It is an EXTRA gate around the old workflow, not a replacement for its
    source hashes, numeric calculations, replay or Guard checks.
    """
    if (type(sources) is not dict or set(sources) != set(_KEYS)
            or any(type(sources[k]) is not bytes
                   or not 0 < len(sources[k]) <= _LIMITS[k] for k in _KEYS)):
        return _blocked("FOUR_BOUNDED_LOCAL_SOURCES_REQUIRED")
    plan = build_ticker_source_plan(
        ticker="AAPL", ticker_map=sources["ticker_map"],
        submissions=sources["submissions"], as_of=as_of)
    if (plan.get("status") != "10k_source_plan_unverified"
            or plan.get("cik") != "0000320193"
            or plan.get("source_authenticated") is not False):
        return _blocked("APPLE_ISSUER_SOURCE_PLAN_UNAVAILABLE")
    filing = plan.get("latest_10k")
    if type(filing) is not dict:
        return _blocked("APPLE_10K_SELECTION_UNAVAILABLE")
    vintage = check_apple_public_filing_vintage(
        ticker=plan["ticker"], as_of=as_of,
        accession=filing.get("accession"),
        fiscal_period_end=filing.get("report_date"))
    if (vintage.get("status") !=
            "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED"
            or vintage.get("filing_date") != filing.get("filing_date")
            or vintage.get("source_authenticated") is not False
            or vintage.get("source_rights_verified") is not False):
        return _blocked("PUBLIC_FILING_VINTAGE_MISMATCH_OR_CATALOG_EXPIRED")
    reviewed = run_local_ticker_workflow(
        ticker="AAPL", as_of=as_of, sources=sources)
    receipt = reviewed.get("receipt")
    report = reviewed.get("report")
    trace = reviewed.get("tool_trace")
    if (reviewed.get("status") != "READY_FOR_HUMAN_REVIEW_UNVERIFIED"
            or reviewed.get("tool_calls_executed") != 7
            or type(trace) is not list or len(trace) != 7
            or any(type(x) is not dict or x.get("accepted") is not True
                   or x.get("network_requests") != 0 for x in trace)
            or type(receipt) is not dict or type(report) is not dict
            or receipt.get("selected_10k_accession") != filing["accession"]
            or receipt.get("selected_10k_filing_date") != filing["filing_date"]
            or receipt.get("requested_as_of") != as_of
            or receipt.get("source_authenticated") is not False
            or receipt.get("source_rights_verified") is not False
            or report.get("guard_policy_preview") not in ("HOLD", "REJECT")
            or type(report.get("source_rights_ledger")) is not dict
            or report["source_rights_ledger"].get("external_sharing_allowed") is not False
            or any(reviewed.get(k) is not False for k in (
                "source_authenticated", "source_rights_verified",
                "ai_agent_executed", "guard_executed", "trade_executed"))):
        return _blocked("SEVEN_STAGE_OFFLINE_REPLAY_OR_TRUST_CONTRACT_BLOCKED")
    return {
        **_blocked(""),
        "status": "LOCAL_HUMAN_REVIEW_PUBLIC_VINTAGE_MATCHED_UNAUTHENTICATED",
        "reason_code": "PUBLIC_CATALOG_AND_LOCAL_REPLAY_ONLY_NOT_ORIGIN_OR_LICENSE",
        "filing": {
            "ticker": "AAPL", "cik": "0000320193",
            "accession": filing["accession"],
            "filing_date": filing["filing_date"],
            "fiscal_period_end": filing["report_date"],
            "public_catalog_checked_through": vintage["catalog_checked_through"],
        },
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="Offline AAPL public-vintage + local A/B/C review (no HTTP)")
    p.add_argument("--as-of", required=True)
    for name in _KEYS:
        p.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = p.parse_args(argv)
    try:
        sources = {
            name: _read_bounded(getattr(args, name), _LIMITS[name])
            for name in _KEYS
        }
        result = review_apple_public_vintage_local_sources(
            as_of=args.as_of, sources=sources)
    except (OSError, TypeError, ValueError):
        result = _blocked("LOCAL_SOURCE_FILE_UNAVAILABLE")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    return 0 if result["status"].startswith("LOCAL_HUMAN_REVIEW_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
