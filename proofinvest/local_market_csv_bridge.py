"""P169: strict local CSV -> untrusted price / *actual index symbol* JSON.

For lawful caller-held CSV sources only. The input column `symbol` must say
NDX for the real Nasdaq-100 benchmark, NOT QQQ or SPY. Conversion cannot
prove who created the CSV, data vintage, index licensing or redistribution.
No HTTPS, API key, persistent storage, trade, network access or dataset
discovery is done here.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from hmac import compare_digest
from io import StringIO
import json
import re
from typing import Any

from .market_provider_alpha_vantage import parse_daily_close_bytes
from .market_provider_alpha_vantage_index import parse_index_daily_bytes
from .ticker_review_packet import inspect_review_packet_bytes

_MAX_CSV = 32_768
_MAX_LINEAGE = 3_072
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z", re.ASCII)
_CLOSE = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?\Z", re.ASCII)


def _encode(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def normalize_market_csv(
    raw: bytes, *, symbol: str, as_of: str, is_index: bool,
) -> dict:
    """Normalize exact CSV `symbol,date,close` into existing strict JSON parser.

    Requires ascending weekdays, 31..100 rows, no duplicate date, future day,
    unexpected symbol, adjusted close, forward-filled value or hidden columns.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_CSV
            or type(symbol) is not str or _SYMBOL.fullmatch(symbol) is None
            or type(is_index) is not bool
            or (is_index and symbol != "NDX")
            or type(as_of) is not str):
        raise ValueError("CSV_SOURCE_METADATA_OR_SIZE_INVALID")
    try:
        cutoff = date.fromisoformat(as_of)
        if cutoff.isoformat() != as_of:
            raise ValueError("CSV_ASOF_NONCANONICAL")
        text = raw.decode("utf-8")
        if "\0" in text or "\r" in text.replace("\r\n", ""):
            raise ValueError("CSV_INVALID_LINE_ENDINGS")
        rows = list(csv.reader(StringIO(text, newline=""), strict=True))
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise ValueError("CSV_PARSE_INVALID") from exc
    if (not 32 <= len(rows) <= 101
            or rows[0] != ["symbol", "date", "close"]):
        raise ValueError("CSV_HEADER_OR_COUNT_INVALID")
    observations = {}
    previous = None
    for row in rows[1:]:
        if len(row) != 3 or row[0] != symbol or not _CLOSE.fullmatch(row[2]):
            raise ValueError("CSV_SYMBOL_OR_CLOSE_INVALID")
        try:
            day = date.fromisoformat(row[1])
            price = Decimal(row[2])
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("CSV_DATE_OR_CLOSE_INVALID") from exc
        if (day.isoformat() != row[1] or day.weekday() >= 5
                or day > cutoff or not price.is_finite() or price <= 0
                or (previous is not None
                    and not 1 <= (day - previous).days <= 7)):
            raise ValueError("CSV_DUPLICATE_FUTURE_OR_GAP_INVALID")
        previous = day
        observations[row[1]] = {"4. close": row[2]}
    transformed = _encode({
        "Meta Data": {"2. Symbol": symbol},
        "Time Series (Daily)": observations,
    })
    try:
        parsed = (parse_index_daily_bytes(
            transformed, benchmark="NASDAQ_100", as_of=as_of)
            if is_index else parse_daily_close_bytes(
                transformed, ticker=symbol, as_of=as_of))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("CSV_NORMALIZED_MARKET_INPUT_INVALID") from exc
    if (parsed["point_count"] != len(observations)
            or parsed["first_date"] != next(iter(observations))
            or parsed["last_date"] != next(reversed(observations))):
        raise ValueError("CSV_NORMALIZED_DATE_MISMATCH")
    return {
        "schema": "kuodra.local-market-csv-normalization.v1",
        "status": "EXACT_LOCAL_CSV_NORMALIZED_ORIGIN_UNVERIFIED",
        "symbol": symbol,
        "is_index": is_index,
        "as_of": as_of,
        "rows": len(observations),
        "first_date": parsed["first_date"],
        "last_date": parsed["last_date"],
        "raw_csv_sha256": sha256(raw).hexdigest(),
        "normalized_json_sha256": sha256(transformed).hexdigest(),
        "normalized_json": transformed,
        "publisher_origin_authenticated": False,
        "rights_verified": False,
        "vintage_authenticated": False,
        "network_requests": 0,
    }


def _lineage_values(stock: dict, index: dict, *, packet: bytes) -> dict:
    inspected = inspect_review_packet_bytes(packet)
    p = json.loads(packet.decode("utf-8"))["linked_evidence"]["premium_engine_a"]
    for item, expected_sha, sym, index_bool in (
        (stock, p["stock_response_sha256"], inspected["ticker"], False),
        (index, p["index_response_sha256"], "NDX", True),
    ):
        if (type(item) is not dict
                or item.get("status") != "EXACT_LOCAL_CSV_NORMALIZED_ORIGIN_UNVERIFIED"
                or item.get("symbol") != sym or item.get("is_index") is not index_bool
                or item.get("as_of") !=
                    json.loads(packet.decode("utf-8"))["issuer"]["as_of"]
                or type(item.get("raw_csv_sha256")) is not str
                or not re.fullmatch(r"[a-f0-9]{64}", item["raw_csv_sha256"])
                or type(item.get("normalized_json_sha256")) is not str
                or not compare_digest(item["normalized_json_sha256"], expected_sha)
                or type(item.get("normalized_json")) is not bytes
                or not compare_digest(sha256(item["normalized_json"]).hexdigest(),
                                      expected_sha)
                or item.get("rights_verified") is not False
                or item.get("publisher_origin_authenticated") is not False):
            raise ValueError("CSV_LINEAGE_OR_REVIEW_PACKET_MISMATCH")
    return {
        "schema": "kuodra.local-market-csv-lineage.v1",
        "status": "CSV_BYTES_TRANSFORMED_AND_PACKET_LINKED_UNVERIFIED",
        "review_packet_sha256": sha256(packet).hexdigest(),
        "ticker": inspected["ticker"],
        "as_of": json.loads(packet.decode("utf-8"))["issuer"]["as_of"],
        "stock_original_csv_sha256": stock["raw_csv_sha256"],
        "index_original_csv_sha256": index["raw_csv_sha256"],
        "stock_normalized_json_sha256": stock["normalized_json_sha256"],
        "index_normalized_json_sha256": index["normalized_json_sha256"],
        "row_counts": {"stock": stock["rows"], "NDX": index["rows"]},
        "source_authenticated": False,
        "source_rights_verified": False,
        "index_entitlement_verified": False,
        "historical_vintage_authenticated": False,
        "public_submission_allowed": False,
        "trade_executed": False,
        "network_requests": 0,
    }


def build_csv_lineage_receipt(*, stock: dict, index: dict, packet: bytes) -> bytes:
    obj = _lineage_values(stock, index, packet=packet)
    obj["receipt_sha256"] = sha256(_encode(obj)).hexdigest()
    data = _encode(obj)
    if len(data) > _MAX_LINEAGE:
        raise ValueError("CSV_LINEAGE_TOO_LARGE")
    return data


def inspect_csv_lineage_receipt(raw: bytes, *, packet: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_LINEAGE:
        raise ValueError("CSV_LINEAGE_SIZE_INVALID")
    def no_duplicate(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("CSV_LINEAGE_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             ValueError("CSV_LINEAGE_NONFINITE")))
        digest = obj.pop("receipt_sha256")
        if (type(digest) is not str or len(digest) != 64
                or not compare_digest(digest, sha256(_encode(obj)).hexdigest())):
            raise ValueError("CSV_LINEAGE_CHECKSUM_INVALID")
        obj["receipt_sha256"] = digest
        if raw != _encode(obj):
            raise ValueError("CSV_LINEAGE_NONCANONICAL")
        packet_data = json.loads(packet.decode("utf-8"))
        p = packet_data["linked_evidence"]["premium_engine_a"]
        schema_fields = {
            "schema", "status", "review_packet_sha256", "ticker", "as_of",
            "stock_original_csv_sha256", "index_original_csv_sha256",
            "stock_normalized_json_sha256", "index_normalized_json_sha256",
            "row_counts", "source_authenticated", "source_rights_verified",
            "index_entitlement_verified", "historical_vintage_authenticated",
            "public_submission_allowed", "trade_executed", "network_requests",
            "receipt_sha256",
        }
        if (set(obj) != schema_fields
                or obj["schema"] != "kuodra.local-market-csv-lineage.v1"
                or obj["status"] != "CSV_BYTES_TRANSFORMED_AND_PACKET_LINKED_UNVERIFIED"
                or obj["review_packet_sha256"] != sha256(packet).hexdigest()
                or obj["ticker"] != packet_data["issuer"]["ticker"]
                or obj["as_of"] != packet_data["issuer"]["as_of"]
                or obj["stock_normalized_json_sha256"] != p["stock_response_sha256"]
                or obj["index_normalized_json_sha256"] != p["index_response_sha256"]
                or type(obj["row_counts"]) is not dict
                or set(obj["row_counts"]) != {"stock", "NDX"}
                or any(type(v) is not int or not 31 <= v <= 100
                       for v in obj["row_counts"].values())
                or any(type(obj[k]) is not str
                       or not re.fullmatch(r"[a-f0-9]{64}", obj[k])
                       for k in ("stock_original_csv_sha256",
                                 "index_original_csv_sha256"))
                or any(obj.get(k) is not False for k in (
                    "source_authenticated", "source_rights_verified",
                    "index_entitlement_verified",
                    "historical_vintage_authenticated",
                    "public_submission_allowed", "trade_executed"))
                or obj["network_requests"] != 0):
            raise ValueError("CSV_LINEAGE_TRUST_CONTRACT_INVALID")
        inspect_review_packet_bytes(packet)
        return {
            "status": "CSV_LINEAGE_MATCHED_RIGHTS_PENDING",
            "review_packet_sha256": obj["review_packet_sha256"],
            "source_rights_verified": False,
            "source_authenticated": False,
        }
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError,
            RecursionError) as exc:
        raise ValueError("CSV_LINEAGE_INVALID") from exc
