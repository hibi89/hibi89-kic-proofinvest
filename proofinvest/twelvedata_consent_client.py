"""P110: two-request consent-gated Twelve Data client, completely inert by default.

The use of this client is not a grant of market/index data rights.
No requests in import, plans, CI or normal app operation. This is a
single trigger, no retry/redirect, no disk/cache/LLM/SEC/trade.
"""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
import re
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError

from .twelvedata_offline_adapter import (
    MAX_RESPONSE_BYTES, run_private_twelvedata_p108,
)

_ORIGIN = "https://api.twelvedata.com/time_series"
_KEY = re.compile(r"[A-Za-z0-9_-]{12,128}\Z")
_ACCESS_BLOCKED = "INDEX_ENTITLEMENT_OR_INTERNAL_TEST_RIGHTS_NOT_CONFIRMED"


def _day(value: str) -> date:
    if type(value) is not str or len(value) != 10:
        raise ValueError("INVALID_DATE")
    d = date.fromisoformat(value)
    if d.isoformat() != value:
        raise ValueError("INVALID_DATE")
    return d


def make_request_plan(
    *, start_date: str, end_date: str, as_of: str,
    index_entitlement_confirmed: bool = False,
    internal_test_rights_confirmed: bool = False,
    index_symbol: str = "NDX",
) -> dict[str, Any]:
    """Construct credential-free, fixed-host, bounded requests, *never* fetch.

    Explicit caller assertions are not independently verified licenses.
    An index symbol in a historical plan is not proof of vendor availability.
    """
    base = {
        "schema": "kuodra.twelvedata-consent-request-plan.v1",
        "status": "BLOCKED",
        "reason_code": _ACCESS_BLOCKED,
        "provider": "Twelve Data", "expected_index": "NASDAQ_100",
        "requested_index_symbol": index_symbol,
        "index_symbol_entitlement_independently_verified": False,
        "license_independently_verified": False,
        "operator_eligibility_asserted": False,
        "market_vintage_authenticated": False,
        "planned_gets": 0, "max_gets_per_trigger": 2,
        "estimated_standard_time_series_credits": 0,
        "network_requests_executed": 0, "trading_enabled": False,
        "source_url": _ORIGIN,
        "urls_without_keys": [],
    }
    try:
        start, end, asof = map(_day, (start_date, end_date, as_of))
        # No free-form symbol, ETF substitution or arbitrary-provider URL.
        if (index_symbol != "NDX"
                or not date(2025, 2, 27) <= start <= end <= asof <= date.today()
                or not 45 <= (end - start).days <= 200):
            base["reason_code"] = "INVALID_SESSION_WINDOW_OR_UNVERIFIED_INDEX_SYMBOL"
            return base
        # Historical observations can be accessed today, but current
        # retrieval cannot be backdated to a 2025 as-of vintage.
        if asof != date.today():
            base["reason_code"] = "HISTORICAL_ASOF_CANNOT_BE_AUTHENTICATED_TODAY"
            return base
        if (index_entitlement_confirmed is not True
                or internal_test_rights_confirmed is not True):
            return base
        params = {
            "interval": "1day", "start_date": start_date,
            "end_date": end_date, "format": "JSON",
        }
        urls = [
            _ORIGIN + "?" + urlencode({"symbol": symbol, **params})
            for symbol in ("NVDA", "NDX")
        ]
        base.update(
            status="READY_FOR_SEPARATE_OWNER_NETWORK_APPROVAL",
            reason_code="OPERATOR_ATTESTATION_NOT_VENDOR_VERIFICATION",
            operator_eligibility_asserted=True,
            planned_gets=2, estimated_standard_time_series_credits=2,
            urls_without_keys=urls,
        )
    except (ValueError, OverflowError, TypeError):
        base["reason_code"] = "INVALID_DATE_WINDOW"
    return base


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _default_open(request: Request, timeout: float):
    # Redirects could forward a secret to another host: NEVER follow them.
    return build_opener(_NoRedirects()).open(request, timeout=timeout)


def _precheck_payload(raw: bytes, symbol: str, start: str, end: str) -> bool:
    """A bad/blocked first response consumes at most one GET, never the next."""
    try:
        obj = json.loads(raw.decode("utf-8"))
        if (type(obj) is not dict or obj.get("status") != "ok"
                or type(obj.get("meta")) is not dict
                or obj["meta"].get("symbol") != symbol
                or type(obj.get("values")) is not list
                or not 31 <= len(obj["values"]) <= 501):
            return False
        for row in obj["values"]:
            if type(row) is not dict or type(row.get("datetime")) is not str:
                return False
            dt = _day(row["datetime"])
            if not start <= dt.isoformat() <= end:
                return False
        return True
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        return False


def run_approved_internal_pair(
    *, start_date: str, end_date: str, as_of: str,
    index_entitlement_confirmed: bool = False,
    internal_test_rights_confirmed: bool = False,
    allow_network: bool = False,
    acknowledge_exactly_two_gets: bool = False,
    api_key: str | None = None,
    opener: Callable[[Request, float], Any] | None = None,
) -> dict[str, Any]:
    """Bounded one-off owner-approved market read; NOT used in this build.

    A real user must separately authorize network/credits and confirm both
    vendor index entitlement and internal-use rights. Never accept an API key
    in URL/CLI; caller may provide secure memory value or dedicated env var.
    """
    plan = make_request_plan(
        start_date=start_date, end_date=end_date, as_of=as_of,
        index_entitlement_confirmed=index_entitlement_confirmed,
        internal_test_rights_confirmed=internal_test_rights_confirmed,
    )
    receipt = {
        "schema": "kuodra.twelvedata-once-execution-receipt.v1",
        "status": "BLOCKED", "reason_code": plan["reason_code"],
        "requests_attempted": 0, "max_requests": 2,
        "source_authenticated": False, "provider_index_entitlement_verified": False,
        "public_display_authorized": False, "commercial_use_authorized": False,
        "point_in_time_backtest_verified": False,
        "trade_executed": False, "guard_decision": "HOLD",
        "analysis": None,
    }
    if (plan["status"] != "READY_FOR_SEPARATE_OWNER_NETWORK_APPROVAL"
            or allow_network is not True
            or acknowledge_exactly_two_gets is not True):
        receipt["reason_code"] = "EXPLICIT_OWNER_TWO_REQUEST_APPROVAL_REQUIRED"
        return receipt
    secret = api_key if api_key is not None else os.environ.get("KUODRA_TWELVEDATA_API_KEY")
    if type(secret) is not str or _KEY.fullmatch(secret) is None:
        receipt["reason_code"] = "LOCAL_API_KEY_MISSING_OR_INVALID"
        return receipt

    # No retries; any response failure blocks the whole pair.
    transport = opener if opener is not None else _default_open
    bodies = []
    for symbol, url in zip(("NVDA", "NDX"), plan["urls_without_keys"]):
        request = Request(
            url, headers={"Authorization": "apikey " + secret,
                          "Accept": "application/json"},
            method="GET",
        )
        receipt["requests_attempted"] += 1
        try:
            with transport(request, 8.0) as response:
                if response.status != 200:
                    receipt["reason_code"] = "PROVIDER_HTTP_STATUS_NOT_200"
                    return receipt
                remaining = response.headers.get("api-credits-left")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if not 0 < len(raw) <= MAX_RESPONSE_BYTES:
                    receipt["reason_code"] = "PROVIDER_BODY_SIZE_REJECTED"
                    return receipt
                if not _precheck_payload(raw, symbol, start_date, end_date):
                    receipt["reason_code"] = "PROVIDER_RESPONSE_IDENTITY_OR_WINDOW_REJECTED"
                    return receipt
                if remaining is not None:
                    if not remaining.isdecimal() or int(remaining) < 0:
                        receipt["reason_code"] = "PROVIDER_CREDITS_HEADER_UNTRUSTWORTHY"
                        return receipt
                    if int(remaining) == 0 and symbol == "NVDA":
                        receipt["reason_code"] = "PROVIDER_CREDIT_BUDGET_EXHAUSTED"
                        return receipt
                bodies.append(raw)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError,
                UnicodeError, TypeError, AttributeError):
            receipt["reason_code"] = "PROVIDER_HTTP_STOP_NO_RETRY"
            return receipt

    try:
        output = run_private_twelvedata_p108(
            bodies[0], bodies[1], as_of=as_of, retrieved_at=as_of,
            acknowledged_internal_test=True,
        )
        # Never return raw market data; P109 output excludes raw bytes.
        if (output["guard_decision"] != "HOLD"
                or output["full_real_data_pipeline_verified"] is not False
                or output["external_requests_executed"] != 0
                or output["analysis"]["engine_a"]["status"] != "REPORTED_UNVERIFIED"):
            raise ValueError("UNTRUSTED_PROVIDER_ANALYSIS")
        receipt.update(status="INTERNAL_OFFLINE_ARITHMETIC_UNVERIFIED",
                       reason_code="OPERATOR_LICENSE_ASSERTION_NOT_PROVIDER_PROOF",
                       analysis=output)
    except (KeyError, ValueError, OSError, TypeError, OverflowError):
        receipt["reason_code"] = "PROVIDER_PAIR_OR_ENGINE_A_VALIDATION_BLOCKED"
    return receipt
