"""P105: one approved NVDA SEC verification, executed locally once by owner.

No remote operation at import, --help or preflight. Interactive local-only
masked contact. Maximum four existing SEC HTTPS GETs; no redirects, proxy,
retry, raw persistence, customer data uploads, provider APIs or trades.
Never record the contact or the actual HTTP request headers in output.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import getpass
import json
import re
import sys
from typing import Any

from proofinvest.sec_api_client import _valid_contact
from proofinvest.ticker_research_intake import _date
from proofinvest.ticker_sec_transport import collect_ticker_sec_sources

_APPROVAL = "READ SEC NVDA"
_EMAIL = re.compile(r"[A-Za-z0-9_.+%-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\Z", re.ASCII)


def _failure(code: str, *, attempted: int = 0) -> dict[str, Any]:
    return {
        "schema": "kuodra.owner-authorized-nvda-sec-once.v1",
        "status": "UNAVAILABLE",
        "reason_code": code,
        "ticker": "NVDA",
        "http_requests_attempted": attempted,
        "max_requests": 4,
        "sec_contact_recorded": False,
        "raw_sources_saved": False,
        "external_ai_called": False,
        "trade_executed": False,
        "report_status": "UNAVAILABLE",
    }


def verify_nvda_once(*, as_of: str, user_agent: str, approved: bool) -> dict[str, Any]:
    """Single process, one attempt, verified existing input gates.

    This function accepts contact ONLY in memory; only the interactive CLI
    prompts for it. Intended for local Windows owner use, never CI or GH Actions.
    """
    if approved is not True:
        return _failure("EXPLICIT_LOCAL_APPROVAL_REQUIRED")
    try:
        cutoff = _date(as_of)
        if cutoff > datetime.now(timezone.utc).date():
            return _failure("FUTURE_AS_OF_UNSUPPORTED")
    except (TypeError, ValueError):
        return _failure("INVALID_AS_OF")
    if not _valid_contact(user_agent):
        return _failure("GENUINE_SEC_CONTACT_REQUIRED")

    # No filename, API key, URL, or extra ticker accepted from the terminal.
    try:
        receipt, sources = collect_ticker_sec_sources(
            ticker="NVDA", as_of=as_of, user_agent=user_agent,
            allow_network=True, acknowledge_four_requests=True,
        )
    except (OSError, ValueError, TypeError, RecursionError):
        return _failure("SAFE_COLLECTOR_UNAVAILABLE")

    attempted = receipt.get("http_requests_attempted", 0)
    if type(attempted) is not int or not 0 <= attempted <= 4:
        if type(sources) is dict:
            sources.clear()
        return _failure("REQUEST_LIMIT_CONTRACT_INVALID")
    if receipt.get("status") != "four_sec_responses_in_memory_unverified":
        if type(sources) is dict:
            sources.clear()
        out = _failure(str(receipt.get("reason_code") or "SEC_SOURCE_UNAVAILABLE"),
                       attempted=attempted)
        out["stage"] = str(receipt.get("stage") or "unknown")[:24]
        return out
    # Only report static-redacted fields, never contact, response headers
    # or original raw bytes. The bridge does not alter the chosen Guard.
    try:
        from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
        from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
        from proofinvest.ticker_market_industry_bridge import evaluate_ticker_a_c

        revenue = inspect_collected_annual_revenue(receipt, sources)
        original = inspect_original_guard_preview(
            receipt, sources, expected_revenue=revenue,
        )
        a_c = evaluate_ticker_a_c(receipt, sources)
        return {
            **_failure("NO_PROVIDER_ORIGINAL_AUTHENTICATION", attempted=attempted),
            "status": "SEC_RESPONSES_RECEIVED_UNVERIFIED",
            "stage": "completed",
            "as_of": receipt.get("requested_as_of"),
            "cik": receipt.get("cik"),
            "filing_accession": receipt.get("selected_10k_accession"),
            "filing_date": receipt.get("selected_10k_filing_date"),
            "source_urls": receipt.get("source_urls"),
            "source_sha256": receipt.get("source_sha256"),
            "source_bytes": receipt.get("source_bytes"),
            "annual_revenue": {
                "status": revenue.get("status"),
                "reason_code": revenue.get("reason_code"),
                "current_end": revenue.get("current_end"),
                "prior_end": revenue.get("prior_end"),
                "current_usd": revenue.get("current_usd"),
                "prior_usd": revenue.get("prior_usd"),
                "growth_pct": revenue.get("growth_pct"),
            },
            "original_review": {
                "status": original.get("status"),
                "reason_code": original.get("reason_code"),
                "ixbrl_status": original.get("ixbrl_status"),
                "dei_status": original.get("dei_status"),
                "guard_policy_preview": original.get("guard_preview"),
            },
            "engine_a": a_c["engine_a"]["status"],
            "engine_c": a_c["engine_c"]["status"],
            "source_authenticated": False,
            "source_rights_verified": False,
            "point_in_time_verified": False,
            "full_a_b_c_ready": False,
            "guard_executed": False,
            "audit_written": False,
            "report_status": "PARTIAL_SOURCE_EVIDENCE_UNVERIFIED",
        }
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return _failure("OFFLINE_ANALYSIS_UNAVAILABLE", attempted=attempted)
    finally:
        # Do not persist original SEC response or CompanyFacts beyond this
        # process. In-place clear reduces accidental downstream retention.
        if type(sources) is dict:
            sources.clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        "One bounded, owner-approved NVDA SEC research probe. "
        "Four official GETs MAX, no saves or retries."
    ))
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat(),
                        help="SEC filing cutoff YYYY-MM-DD (default: current UTC date)")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print(json.dumps(_failure("INTERACTIVE_TERMINAL_REQUIRED"), sort_keys=True))
        return 2
    print("SEC NVDA: maximum 4 HTTPS GETs, no retry / trade / raw save.")
    print("A 403 or 429 STOPS the entire chain; do not retry or bypass.")
    try:
        typed = input(f"One-time authorization: type {_APPROVAL}: ").strip()
    except (EOFError, KeyboardInterrupt):
        typed = ""
    if typed != _APPROVAL:
        print(json.dumps(_failure("EXPLICIT_LOCAL_APPROVAL_REQUIRED"), sort_keys=True))
        return 2
    try:
        contact = getpass.getpass(
            "Your real, reachable SEC contact email (hidden; not saved): "
        ).strip()
    except (EOFError, KeyboardInterrupt, OSError):
        contact = ""
    # The caller's email is never echoed, logged, sent to GitHub or written.
    ua = "KUODRA Single-Ticker Research " + contact
    if len(contact) > 120 or not _EMAIL.fullmatch(contact) or not _valid_contact(ua):
        print(json.dumps(_failure("GENUINE_SEC_CONTACT_REQUIRED"), sort_keys=True))
        return 2
    result = verify_nvda_once(as_of=args.as_of, user_agent=ua, approved=True)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "SEC_RESPONSES_RECEIVED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
