"""KUODRA bounded offline industry/macro context for a saved SEC original.

No feeds, provider trust, rights clearance, causal inference or trading.
Issuer exposure must match an exact byte span in the supplied original filing.
Provider release/collection metadata is caller supplied and UNAUTHENTICATED.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
import json
from hashlib import sha256
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from .visible_text_evidence import confirm_filing_exposure_text_node

# Eleven approved CANDIDATES, not eleven downloaded feeds.
CANDIDATES = {
    "SP500": "index_points",
    "NASDAQ100": "index_points",
    "DJIA": "index_points",
    "US_CPI_YOY": "percent_yoy",
    "CN_CPI_YOY": "percent_yoy",
    "EA_HICP_YOY": "percent_yoy",
    "JP_CPI_YOY": "percent_yoy",
    "KR_CPI_YOY": "percent_yoy",
    "US10Y": "percent_yield",
    "GOLD_USD_OZ": "usd_per_troy_ounce",
    "WTI_USD_BBL": "usd_per_barrel",
}
MAX_EXPOSURES = 11
MAX_OBSERVATIONS = 32
MAX_CARDS = 3
MAX_RAW_BYTES = 65_536


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("MACRO_RAW_DUPLICATE_JSON_KEY")
        out[key] = value
    return out


def _verify_raw_observations(
    observations: list[dict[str, Any]],
    raw_observations: Mapping[str, bytes] | None,
) -> set[str]:
    """Cryptographically bind exact local JSON bytes to metadata observations.

    This only proves bytes equal caller-supplied metadata. It does NOT prove
    that a publisher produced them, that the rights assertion is true, or
    that a website's current value has ever been fetched.
    """
    if raw_observations is None:
        return set()
    if not isinstance(raw_observations, Mapping) or len(raw_observations) > MAX_OBSERVATIONS:
        raise ValueError("MACRO_RAW_INPUT_INVALID")
    if any(not isinstance(row, dict) or row.get("series_id") not in CANDIDATES
           for row in observations):
        raise ValueError("MACRO_RAW_OBSERVATION_SCHEMA_INVALID")
    ids = [row["series_id"] for row in observations]
    if (len(ids) != len(set(ids)) or set(ids) != set(raw_observations)
            or any(k not in CANDIDATES for k in raw_observations)):
        raise ValueError("MACRO_RAW_SERIES_SET_MISMATCH")
    for sid, raw in raw_observations.items():
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_RAW_BYTES:
            raise ValueError("MACRO_RAW_INPUT_INVALID")
        row = next(row for row in observations if row["series_id"] == sid)
        if sha256(raw).hexdigest() != row.get("payload_sha256"):
            raise ValueError("MACRO_RAW_SHA256_MISMATCH")
        try:
            parsed = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("MACRO_RAW_INVALID_CONSTANT")
                ),
            )
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ValueError("MACRO_RAW_JSON_INVALID") from None
        # No mutable canonicalization: raw file must contain exactly the
        # observation fields being claimed, excluding self-referential SHA.
        declared = {k: v for k, v in row.items() if k != "payload_sha256"}
        if not isinstance(parsed, dict) or parsed != declared:
            raise ValueError("MACRO_RAW_FIELDS_MISMATCH")
    return set(raw_observations)



def _https(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 1000 or any(x.isspace() for x in value):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and bool(u.hostname) and "." in u.hostname
                and not u.username and not u.password and u.port in (None, 443))
    except ValueError:
        return False


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or "T" not in value or len(value) > 48:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo is None or d.utcoffset() is None:
            return None
        return d.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _bounded_text(value: Any, low: int, high: int) -> bool:
    return isinstance(value, str) and low <= len(value.strip()) <= high


def _validate_observation(row: Mapping[str, Any], cutoff: datetime) -> str | None:
    if row.get("unit") != CANDIDATES[row["series_id"]]:
        return "UNIT_OR_BENCHMARK_MISMATCH"
    s = row.get("value")
    if not isinstance(s, str) or re.fullmatch(r"-?\d{1,12}(?:\.\d{1,8})?", s) is None:
        return "INVALID_DECIMAL_VALUE"
    try:
        n = Decimal(s)
        if not n.is_finite() or abs(n) > Decimal("1000000000000"):
            return "INVALID_DECIMAL_VALUE"
    except InvalidOperation:
        return "INVALID_DECIMAL_VALUE"
    period = _day(row.get("period_end"))
    released, vintage, collected = (_utc(row.get(k)) for k in
                                    ("released_at", "vintage_at", "collected_at"))
    if period is None or None in (released, vintage, collected):
        return "MISSING_OR_NAIVE_CHRONOLOGY"
    if (period > released.date() or not released <= vintage <= collected
            or collected > cutoff or period > cutoff.date()):
        return "FUTURE_OR_OUT_OF_ORDER_VINTAGE"
    if not _https(row.get("source_url")) or not _https(row.get("rights_basis_url")):
        return "SOURCE_OR_RIGHTS_LINK_INVALID"
    if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("payload_sha256", ""))):
        return "SOURCE_PAYLOAD_DIGEST_MISSING"
    if (row.get("rights_review") != "LOCAL_ANALYSIS_PERMITTED_ATTESTED"
            or not _bounded_text(row.get("rights_note"), 8, 300)):
        return "LOCAL_ANALYSIS_RIGHTS_NOT_ATTESTED"
    if not _bounded_text(row.get("benchmark"), 3, 120):
        return "BENCHMARK_UNSPECIFIED"
    return None


def review_macro_context(
    *, original_filing: bytes, issuer_cik: str, as_of: str,
    exposures: list[dict[str, Any]], observations: list[dict[str, Any]],
    raw_observations: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Rank up to three metadata-eligible local context cards.

    This is a downstream *supplement* to the SEC -> Guard result, never Guard
    input. Validated exact bytes are not proof of HTML visibility or SEC origin.
    Caller rights attestations are not independently verified licenses.
    """
    day = _day(as_of)
    if (not isinstance(original_filing, bytes) or len(original_filing) > 20_000_000
            or not re.fullmatch(r"\d{10}", str(issuer_cik))
            or day is None or not isinstance(exposures, list)
            or not isinstance(observations, list)
            or len(exposures) > MAX_EXPOSURES or len(observations) > MAX_OBSERVATIONS):
        raise ValueError("MACRO_CONTEXT_INVALID_INPUT")
    verified_raw_ids = _verify_raw_observations(observations, raw_observations)
    cutoff = datetime.combine(day, time.max, timezone.utc)
    eligible_exposures: dict[str, dict[str, Any]] = {}
    exposure_count: dict[str, int] = {}
    text_node_rejected: set[str] = set()
    quote_review_cache: dict[tuple[str, int, int], bool] = {}
    for row in exposures:
        if not isinstance(row, dict) or row.get("series_id") not in CANDIDATES:
            raise ValueError("MACRO_EXPOSURE_UNKNOWN_SERIES")
        sid = row["series_id"]
        exposure_count[sid] = exposure_count.get(sid, 0) + 1
        start, end = row.get("start_byte"), row.get("end_byte_exclusive")
        quote = row.get("literal")
        if (type(start) is not int or type(end) is not int
                or start < 0 or end > len(original_filing) or not 8 <= end - start <= 1024
                or not _bounded_text(quote, 8, 1024)
                or not _bounded_text(row.get("rationale"), 8, 300)):
            continue
        try:
            literal_bytes = quote.encode("utf-8")
        except UnicodeEncodeError:
            continue
        if original_filing[start:end] != literal_bytes:
            continue
        # Exact bytes alone may be a script, comment, attribute, head or
        # hidden ix:nonFraction. Reuse the conservative P16 text-node parser.
        key = (quote, start, end)
        if key not in quote_review_cache:
            checked = confirm_filing_exposure_text_node(
                original_filing, needle=quote, expected_start=start,
                expected_end=end,
            )
            quote_review_cache[key] = (
                checked.get("status") == "untrusted_html_text_node_literal_located"
                and checked.get("exact_raw_byte_span_verified") is True
                and checked.get("source_authenticated") is False
                and checked.get("rendered_visibility_verified") is False
            )
        if not quote_review_cache[key]:
            text_node_rejected.add(sid)
            continue
        eligible_exposures[sid] = row

    observations_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        if not isinstance(row, dict) or row.get("series_id") not in CANDIDATES:
            raise ValueError("MACRO_OBSERVATION_UNKNOWN_SERIES")
        observations_by_id.setdefault(row["series_id"], []).append(row)

    cards: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []
    for sid in CANDIDATES:
        ex = eligible_exposures.get(sid)
        rows = observations_by_id.get(sid, [])
        if exposure_count.get(sid, 0) > 1:
            reason = "DUPLICATE_EXPOSURE"
        elif ex is None:
            reason = ("EXPOSURE_NOT_IN_ELIGIBLE_HTML_TEXT_NODE"
                      if sid in text_node_rejected
                      else "NO_EXACT_FILING_EXPOSURE")
        elif len(rows) > 1:
            reason = "AMBIGUOUS_OBSERVATION_VINTAGES"
        elif not rows:
            reason = "NO_LOCAL_OBSERVATION"
        else:
            reason = _validate_observation(rows[0], cutoff)
            if reason is None and len(cards) == MAX_CARDS:
                reason = "CARD_LIMIT"
        if reason is not None:
            checks.append({"series_id": sid, "status": "NOT_CHECKED", "reason_code": reason})
            continue
        row = rows[0]
        cards.append({
            "series_id": sid, "value": row["value"], "unit": row["unit"],
            "benchmark": row["benchmark"], "period_end": row["period_end"],
            "released_at": row["released_at"], "vintage_at": row["vintage_at"],
            "collected_at": row["collected_at"], "source_url": row["source_url"],
            "payload_sha256_self_reported": row["payload_sha256"],
            "original_exposure_span": [ex["start_byte"], ex["end_byte_exclusive"]],
            "exposure_literal": ex["literal"], "review_rationale": ex["rationale"],
            "metadata_eligible_only": True,
            "exposure_exact_html_text_node_verified": True,
            "exposure_browser_visibility_verified": False,
            "raw_observation_sha256_verified": sid in verified_raw_ids,
        })
        checks.append({"series_id": sid, "status": "METADATA_ELIGIBLE_UNVERIFIED",
                       "reason_code": "SOURCE_AND_RIGHTS_NOT_INDEPENDENTLY_VERIFIED"})
    return {
        "schema": "kuodra.macro-context-offline.v1",
        "issuer_cik": issuer_cik, "as_of": as_of,
        "original_filing_sha256": sha256(original_filing).hexdigest(),
        "cards": cards, "candidate_checks": checks,
        "raw_observation_count_verified": len(verified_raw_ids),
        "all_11_feeds_implemented": False, "source_authenticated": False,
        "source_rights_verified": False, "causality_established": False,
        "guard_policy_modified": False, "ai_agent_executed": False,
        "live_api_called": False, "trade_executed": False,
    }
