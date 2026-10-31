"""P50 locally pinned, operator-declared market-data provenance and adjustments.

This validates consistency between a bounded user-supplied metadata JSON and
the actual uploaded price CSV. It cannot certify an exchange, licensing,
market data vintage, dividends, split events or vendor historic revisions.
No network, no persistence, no secrets, no investment recommendations.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

_MAX_METADATA_BYTES = 8_192
_SHA = re.compile(r"[0-9a-f]{64}\Z", flags=re.ASCII)
_ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", flags=re.ASCII)
_TIME_UTC = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z",
    flags=re.ASCII,
)
_ALLOWED_RIGHTS = {
    "UNKNOWN", "LOCAL_RESEARCH_CLAIMED", "REDISTRIBUTION_CLAIMED",
}
_ALLOWED_REVISION = {
    "UNKNOWN", "RETROSPECTIVE_UNVERSIONED",
    "VERSIONED_SNAPSHOT_CLAIMED",
}
_ALLOWED_SPLITS = {"UNKNOWN", "UNADJUSTED", "ADJUSTED_CLAIMED"}
_ALLOWED_DIVIDENDS = {"UNKNOWN", "EXCLUDED", "INCLUDED_CLAIMED"}
_FIELDS = {
    "schema", "issuer_cik", "as_of", "symbol", "benchmark", "return_basis",
    "market_csv_sha256", "price_first_date", "price_last_date",
    "claimed_source_url", "claimed_published_at", "captured_at_utc",
    "price_provider", "rights_scope", "revision_policy",
    "stock_split_treatment", "stock_dividend_treatment",
    "benchmark_total_return_claimed",
}


def _invalid(reason: str):
    raise ValueError(reason)


def _no_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            _invalid("MARKET_EVIDENCE_DUPLICATE_JSON_KEY")
        obj[k] = v
    return obj


def _required_string(v: Any, name: str, limit: int = 400) -> str:
    if (type(v) is not str or not 0 < len(v) <= limit
            or any(ord(c) < 32 or ord(c) == 127 for c in v)):
        _invalid("MARKET_EVIDENCE_INVALID_" + name)
    return v


def _day(v: Any, name: str) -> date:
    s = _required_string(v, name, 10)
    if not _ISO_DAY.fullmatch(s):
        _invalid("MARKET_EVIDENCE_INVALID_" + name)
    try:
        return date.fromisoformat(s)
    except ValueError:
        _invalid("MARKET_EVIDENCE_INVALID_" + name)


def validate_market_evidence(
    metadata_bytes: bytes, *,
    csv_bytes: bytes,
    normalized_market_payload: dict,
) -> dict:
    """Compare a local metadata document with actual price input bytes.

    Even a consistent 'versioned' snapshot is SELF-REPORTED. The result
    deliberately does not contain a right-to-distribute or PIT certificate.
    """
    if (type(metadata_bytes) is not bytes
            or not 0 < len(metadata_bytes) <= _MAX_METADATA_BYTES):
        _invalid("MARKET_EVIDENCE_BYTES_MISSING_OR_OVERSIZED")
    if type(csv_bytes) is not bytes or type(normalized_market_payload) is not dict:
        _invalid("MARKET_EVIDENCE_INVALID_INPUT")
    try:
        meta = json.loads(
            metadata_bytes.decode("utf-8"), object_pairs_hook=_no_duplicates,
            parse_constant=lambda _: _invalid("MARKET_EVIDENCE_NONFINITE"),
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _invalid("MARKET_EVIDENCE_NOT_JSON")
    if type(meta) is not dict or set(meta) != _FIELDS:
        _invalid("MARKET_EVIDENCE_EXACT_SCHEMA_FIELDS_REQUIRED")
    if meta["schema"] != "kuodra.market-data-evidence.v1":
        _invalid("MARKET_EVIDENCE_SCHEMA_UNSUPPORTED")

    # Bind EVERY selection and byte checksum to the actual, previously
    # validated market CSV, not to an unrelated issuer or index.
    for field in ("issuer_cik", "as_of", "symbol", "benchmark", "return_basis"):
        if meta[field] != normalized_market_payload.get(field):
            _invalid("MARKET_EVIDENCE_CONTEXT_MISMATCH")
    digest = meta["market_csv_sha256"]
    if (type(digest) is not str or not _SHA.fullmatch(digest)
            or digest != sha256(csv_bytes).hexdigest()):
        _invalid("MARKET_EVIDENCE_RAW_CSV_SHA_MISMATCH")
    security = normalized_market_payload.get("security")
    index = normalized_market_payload.get("index")
    if not (type(security) is dict and type(index) is dict
            and type(security.get("source")) is dict
            and type(index.get("source")) is dict
            and type(security.get("observations")) is list
            and type(index.get("observations")) is list
            and security["observations"] and index["observations"]):
        _invalid("MARKET_EVIDENCE_INVALID_PRICE_PAYLOAD")
    source = security["source"]
    if (meta["claimed_source_url"] != source.get("url")
            or meta["claimed_published_at"] != source.get("published_at")
            or index["source"].get("url") != source.get("url")
            or index["source"].get("sha256") != digest
            or source.get("sha256") != digest):
        _invalid("MARKET_EVIDENCE_SOURCE_METADATA_MISMATCH")
    first = _day(meta["price_first_date"], "FIRST_DATE")
    last = _day(meta["price_last_date"], "LAST_DATE")
    as_of = _day(meta["as_of"], "ASOF")
    published = _day(meta["claimed_published_at"], "PUBLICATION_DAY")
    if (first > last or last > as_of or published < last
            or published > as_of
            or first.isoformat() != security["observations"][0].get("date")
            or last.isoformat() != security["observations"][-1].get("date")
            or first.isoformat() != index["observations"][0].get("date")
            or last.isoformat() != index["observations"][-1].get("date")):
        _invalid("MARKET_EVIDENCE_PRICE_DATE_OR_RELEASE_MISMATCH")

    _required_string(meta["price_provider"], "PROVIDER", 80)
    for field, allowed in (
        ("rights_scope", _ALLOWED_RIGHTS),
        ("revision_policy", _ALLOWED_REVISION),
        ("stock_split_treatment", _ALLOWED_SPLITS),
        ("stock_dividend_treatment", _ALLOWED_DIVIDENDS),
    ):
        if type(meta[field]) is not str or meta[field] not in allowed:
            _invalid("MARKET_EVIDENCE_INVALID_" + field.upper())
    if type(meta["benchmark_total_return_claimed"]) is not bool:
        _invalid("MARKET_EVIDENCE_INVALID_BENCHMARK_RETURN_FLAG")

    if (type(meta["captured_at_utc"]) is not str
            or not _TIME_UTC.fullmatch(meta["captured_at_utc"])):
        _invalid("MARKET_EVIDENCE_INVALID_UTC_CAPTURE")
    try:
        captured = datetime.strptime(
            meta["captured_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        _invalid("MARKET_EVIDENCE_INVALID_UTC_CAPTURE")
    if captured.date() < published:
        _invalid("MARKET_EVIDENCE_CAPTURE_BEFORE_REPORTED_RELEASE")

    basis = meta["return_basis"]
    if basis == "PRICE_ONLY_CLOSE":
        if (meta["stock_dividend_treatment"] != "EXCLUDED"
                or meta["benchmark_total_return_claimed"]):
            _invalid("MARKET_EVIDENCE_PRICE_RETURN_DEFINITION_CONFLICT")
    elif basis == "ADJUSTED_CLOSE_TOTAL_RETURN_PROXY":
        if (meta["stock_split_treatment"] != "ADJUSTED_CLAIMED"
                or meta["stock_dividend_treatment"] != "INCLUDED_CLAIMED"
                or meta["benchmark_total_return_claimed"] is not True):
            _invalid("MARKET_EVIDENCE_ADJUSTED_RETURN_DEFINITION_CONFLICT")
    else:
        _invalid("MARKET_EVIDENCE_RETURN_BASIS_UNSUPPORTED")

    # The before/after as-of distinction is descriptive ONLY: these UTC
    # strings and alleged revisions can be fabricated or retrospectively made.
    claimed_vintage_status = (
        "RETROSPECTIVE_CAPTURE_NOT_POINT_IN_TIME"
        if captured.date() > as_of
        else "PRE_ASOF_CAPTURE_CLAIMED_UNAUTHENTICATED"
    )
    return {
        "schema": "kuodra.market-data-evidence-check.v1",
        "status": "LOCAL_DECLARATIONS_CONSISTENT_UNVERIFIED",
        "metadata_sha256": sha256(metadata_bytes).hexdigest(),
        "market_csv_sha256": digest,
        "issuer_cik": meta["issuer_cik"],
        "as_of": meta["as_of"],
        "symbol": meta["symbol"],
        "benchmark": meta["benchmark"],
        "return_basis": basis,
        "price_first_date": first.isoformat(),
        "price_last_date": last.isoformat(),
        "claimed_published_at": published.isoformat(),
        "claimed_capture_at_utc": meta["captured_at_utc"],
        "claimed_vintage_status": claimed_vintage_status,
        "rights_scope_operator_claim": meta["rights_scope"],
        "revision_policy_operator_claim": meta["revision_policy"],
        "stock_split_treatment_operator_claim": meta["stock_split_treatment"],
        "stock_dividend_treatment_operator_claim": meta["stock_dividend_treatment"],
        "benchmark_total_return_operator_claim": meta["benchmark_total_return_claimed"],
        "source_authenticated": False,
        "data_rights_verified": False,
        "corporate_actions_verified": False,
        "historical_market_vintage_authenticated": False,
        "point_in_time_backtest_verified": False,
        "trade_signal": False,
        "external_http_called": False,
    }
