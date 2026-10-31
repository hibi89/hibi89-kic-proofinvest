"""Read-only converter for user-supplied paired price/index CSV into Engine A.

This is an intake-format adapter, not a data vendor or provenance authenticator.
The raw CSV SHA256 is computed from actual uploaded bytes, never asserted by
the operator. No HTTP, filesystem writes, market adjustment, AI or trading.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json

from .market_reality import MAX_UPLOAD_BYTES, analyze_market_reality

_EXPECTED_HEADER = ["date", "security_close", "benchmark_close"]
_PROVIDER = "LOCAL_OPERATOR_SUPPLIED_PAIRED_CSV"


def market_price_csv_to_json(
    raw: bytes, *, issuer_cik: str, as_of: str, symbol: str,
    benchmark: str, return_basis: str, source_url: str,
    published_at: str,
) -> bytes:
    """Normalize strict, aligned daily series with its *actual byte digest*.

    No fill-forward, deduplication, interpolation, implicit column choice, FX
    conversion, dividend handling, corporate action repair or silent sorting.
    Raw source URL and publication date remain operator-reported metadata.
    """
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_UPLOAD_BYTES:
        raise ValueError("CSV_NOT_REGULAR_BOUNDED_BYTES")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("CSV_NOT_UTF8") from exc
    if "\0" in decoded:
        raise ValueError("CSV_NUL_FORBIDDEN")
    try:
        reader = csv.reader(StringIO(decoded, newline=""), strict=True)
        if next(reader, None) != _EXPECTED_HEADER:
            raise ValueError("CSV_EXACT_HEADER_REQUIRED")
        rows = []
        for values in reader:
            if len(values) != 3:
                raise ValueError("CSV_EXACT_ROW_REQUIRED")
            if len(rows) >= 501:
                raise ValueError("CSV_TOO_MANY_OBSERVATIONS")
            if any(value != value.strip() or not value for value in values):
                raise ValueError("CSV_EMPTY_OR_PADDED_FIELD")
            day, stock, index = values
            rows.append((day, stock, index))
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("CSV_INVALID_QUOTES_OR_STRUCTURE") from exc
    if len(rows) < 31:
        raise ValueError("CSV_AT_LEAST_31_OBSERVATIONS_REQUIRED")
    actual_digest = sha256(raw).hexdigest()
    source = {
        "provider": _PROVIDER,
        "url": source_url,
        "published_at": published_at,
        "sha256": actual_digest,
    }
    payload = {
        "schema": "kuodra.market-reality.v1",
        "issuer_cik": issuer_cik,
        "as_of": as_of,
        "symbol": symbol,
        "benchmark": benchmark,
        "return_basis": return_basis,
        "security": {
            "source": dict(source),
            "observations": [{"date": row[0], "value": row[1]} for row in rows],
        },
        "index": {
            "source": dict(source),
            "observations": [{"date": row[0], "value": row[2]} for row in rows],
        },
    }
    # All existing date, day-of-week, as-of, URL, positive Decimal, and
    # regression correctness checks are reused verbatim before serialization.
    analyze_market_reality(
        payload, expected_issuer_cik=issuer_cik, analysis_as_of=as_of,
    )
    normalized = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(normalized) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV_NORMALIZED_JSON_TOO_LARGE")
    return normalized
