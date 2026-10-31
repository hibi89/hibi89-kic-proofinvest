"""KUODRA Industry Vision: bounded, source-linked comparative growth.

Read-only supplied facts; no internet access, LLM, forecast, trade or Guard override.
Figures, publisher metadata and source hashes are NOT independently authenticated.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import json
import re
from statistics import median
from urllib.parse import urlsplit
from typing import Any

MAX_UPLOAD_BYTES = 65_536
_CIK = re.compile(r"[0-9]{10}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?\Z")
_ALLOWED_MARKET = {"REAL_GROSS_OUTPUT", "NOMINAL_INDUSTRY_SALES",
                   "PRODUCTION_INDEX", "DEMAND_INDEX"}
_DRIVERS = {"OPPORTUNITY", "RISK", "MIXED"}


def _fail(code: str):
    raise ValueError(code)


def _string(value: Any, name: str, limit: int = 160) -> str:
    if (type(value) is not str or not 0 < len(value) <= limit
            or any(ord(x) < 32 or ord(x) == 127 for x in value)):
        _fail("INVALID_" + name)
    return value


def _date(value: Any, name: str) -> date:
    raw = _string(value, name, 10)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        _fail("INVALID_" + name)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        _fail("INVALID_" + name)


def _exact(value: Any, fields: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != fields:
        _fail("INVALID_" + label + "_FIELDS")
    return value


def _amount(value: Any, label: str) -> Decimal:
    if type(value) is not str or not _NUMBER.fullmatch(value):
        _fail("INVALID_" + label)
    try:
        result = Decimal(value)
    except InvalidOperation:
        _fail("INVALID_" + label)
    if not result.is_finite():
        _fail("INVALID_" + label)
    return result


def _no_dups(pairs):
    data = {}
    for k, v in pairs:
        if k in data:
            _fail("DUPLICATE_JSON_KEY")
        data[k] = v
    return data


def parse_industry_vision_json(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_UPLOAD_BYTES:
        _fail("INVALID_INDUSTRY_JSON_SIZE")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dups,
                           parse_constant=lambda _: _fail("INVALID_JSON_NUMBER"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("INVALID_INDUSTRY_JSON")
    if type(value) is not dict:
        _fail("INVALID_INDUSTRY_JSON_ROOT")
    return value


def _source(value: Any, as_of: date) -> dict:
    row = _exact(value, {"id", "url", "published_at", "sha256"}, "SOURCE")
    sid = _string(row["id"], "SOURCE_ID", 64)
    if not _ID.fullmatch(sid):
        _fail("INVALID_SOURCE_ID")
    url = _string(row["url"], "SOURCE_URL", 350)
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        _fail("INVALID_SOURCE_URL")
    if (parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or port not in (None, 443)
            or parsed.query or parsed.fragment or parsed.hostname.lower() == "localhost"
            or "." not in parsed.hostname or parsed.path.startswith("//")):
        _fail("INVALID_SOURCE_URL")
    published = _date(row["published_at"], "SOURCE_RELEASE")
    if published > as_of:
        _fail("SOURCE_AFTER_RESEARCH_AS_OF")
    if type(row["sha256"]) is not str or not _SHA.fullmatch(row["sha256"]):
        _fail("INVALID_SOURCE_SHA")
    return {"id": sid, "url": url, "published_at": published.isoformat(),
            "sha256": row["sha256"], "authenticated": False}


def _growth(old: Decimal, new: Decimal) -> Decimal | None:
    if old == 0:
        return None
    return ((new - old) / old) * 100


def _fmt(n: Decimal | None) -> str | None:
    if n is None:
        return None
    return format(n.quantize(Decimal("0.01")), "f")


def _company(value: Any, sources: dict, role: str) -> dict:
    row = _exact(value, {"name", "cik", "prior_revenue_usd", "current_revenue_usd",
                         "prior_source_id", "current_source_id"}, "COMPANY")
    cik = _string(row["cik"], "COMPANY_CIK", 10)
    if not _CIK.fullmatch(cik) or cik == "0000000000":
        _fail("INVALID_COMPANY_CIK")
    refs = (row["prior_source_id"], row["current_source_id"])
    if any(type(ref) is not str or ref not in sources for ref in refs):
        _fail("UNKNOWN_COMPANY_SOURCE")
    old = _amount(row["prior_revenue_usd"], "PRIOR_REVENUE")
    new = _amount(row["current_revenue_usd"], "CURRENT_REVENUE")
    return {
        "name": _string(row["name"], "COMPANY_NAME", 90), "cik": cik,
        "role": role, "growth_pct_reported_input": _fmt(_growth(old, new)),
        "prior_revenue_usd": str(old), "current_revenue_usd": str(new),
        "source_ids": list(refs),
    }


def analyze_industry_vision(payload: Any, *, expected_issuer_cik: str | None = None,
                            analysis_as_of: str | None = None) -> dict:
    """Describe observed growth comparisons; conditional future scenarios only.

    All inputs are user assertions. No historical data is fetched or verified.
    """
    top = _exact(payload, {"schema", "issuer_cik", "as_of", "industry",
                          "prior_period_end", "current_period_end", "target",
                          "peers", "industry_series", "drivers", "sources"},
                 "VISION")
    if top["schema"] != "kuodra.industry-vision.v1":
        _fail("INVALID_VISION_SCHEMA")
    issuer = _string(top["issuer_cik"], "ISSUER_CIK", 10)
    if not _CIK.fullmatch(issuer) or issuer == "0000000000":
        _fail("INVALID_ISSUER_CIK")
    if expected_issuer_cik is not None and issuer != expected_issuer_cik:
        _fail("VISION_ISSUER_MISMATCH")
    as_of = _date(top["as_of"], "AS_OF")
    if analysis_as_of is not None and as_of != _date(analysis_as_of, "EXPECTED_AS_OF"):
        _fail("VISION_AS_OF_MISMATCH")
    prior = _date(top["prior_period_end"], "PRIOR_END")
    current = _date(top["current_period_end"], "CURRENT_END")
    if not 330 <= (current - prior).days <= 380 or current > as_of:
        _fail("INVALID_ANNUAL_COMPARISON_PERIOD")
    industry = _string(top["industry"], "INDUSTRY", 100)
    if type(top["sources"]) is not list or not 2 <= len(top["sources"]) <= 24:
        _fail("INVALID_SOURCE_COUNT")
    source_rows = [_source(x, as_of) for x in top["sources"]]
    sources = {x["id"]: x for x in source_rows}
    if len(sources) != len(source_rows):
        _fail("DUPLICATE_SOURCE_ID")
    target = _company(top["target"], sources, "TARGET")
    if target["cik"] != issuer:
        _fail("TARGET_ISSUER_MISMATCH")
    if type(top["peers"]) is not list or len(top["peers"]) > 8:
        _fail("INVALID_PEERS")
    peers = [_company(x, sources, "PEER") for x in top["peers"]]
    ciks = [target["cik"]] + [p["cik"] for p in peers]
    if len(ciks) != len(set(ciks)):
        _fail("DUPLICATE_COMPANY_CIK")
    benchmark = _exact(top["industry_series"],
                       {"name", "kind", "prior_value", "current_value",
                        "prior_source_id", "current_source_id", "unit"},
                       "INDUSTRY_SERIES")
    kind = benchmark["kind"]
    if kind not in _ALLOWED_MARKET:
        _fail("INVALID_INDUSTRY_METRIC")
    refs = (benchmark["prior_source_id"], benchmark["current_source_id"])
    if any(type(ref) is not str or ref not in sources for ref in refs):
        _fail("UNKNOWN_INDUSTRY_SOURCE")
    old = _amount(benchmark["prior_value"], "PRIOR_INDUSTRY")
    new = _amount(benchmark["current_value"], "CURRENT_INDUSTRY")
    market_growth = _growth(old, new)
    target_growth = _growth(_amount(target["prior_revenue_usd"], "TARGET_PRIOR"),
                            _amount(target["current_revenue_usd"], "TARGET_CURRENT"))
    peer_growth = [
        _growth(Decimal(p["prior_revenue_usd"]), Decimal(p["current_revenue_usd"]))
        for p in peers
    ]
    peer_growth = [g for g in peer_growth if g is not None]
    peer_mid = median(peer_growth) if peer_growth else None
    if market_growth is None or target_growth is None:
        status = "INSUFFICIENT_EVIDENCE"
        comparison = "기준 기간의 분모가 0이어서 산업 대비 성장률을 비교하지 않습니다."
    else:
        gap = target_growth - market_growth
        status = "OBSERVED_COMPARISON_UNVERIFIED"
        comparison = ("기업 매출 성장률이 입력된 산업 지표 성장률보다 높습니다."
                      if gap > 0 else
                      "기업 매출 성장률이 입력된 산업 지표 성장률보다 낮습니다."
                      if gap < 0 else
                      "기업 매출과 입력된 산업 지표 성장률이 같습니다.")
    if type(top["drivers"]) is not list or len(top["drivers"]) > 3:
        _fail("INVALID_DRIVERS")
    drivers = []
    for drv in top["drivers"]:
        row = _exact(drv, {"label", "direction", "source_ids"}, "DRIVER")
        if row["direction"] not in _DRIVERS:
            _fail("INVALID_DRIVER_DIRECTION")
        refs = row["source_ids"]
        if (type(refs) is not list or not 1 <= len(refs) <= 8
                or any(type(ref) is not str or ref not in sources for ref in refs)
                or len(set(refs)) != len(refs)):
            _fail("UNKNOWN_DRIVER_SOURCE")
        drivers.append({"label": _string(row["label"], "DRIVER_LABEL", 120),
                        "direction_operator_supplied": row["direction"],
                        "source_ids": list(refs), "verified": False})
    return {
        "schema": "kuodra.industry-vision-explanation.v1", "status": status,
        "industry": industry, "issuer_cik": issuer, "as_of": as_of.isoformat(),
        "periods": {"prior_end": prior.isoformat(), "current_end": current.isoformat()},
        "headline": "산업 성장·기업 경쟁력·시장 전망 근거 비교 (입력 자료 기준)",
        "summary": comparison,
        "target": target, "peers": peers,
        "peer_median_growth_pct": _fmt(peer_mid),
        "industry_series": {
            "name": _string(benchmark["name"], "INDUSTRY_SERIES_NAME", 100),
            "kind": kind, "unit": _string(benchmark["unit"], "INDUSTRY_UNIT", 30),
            "growth_pct_reported_input": _fmt(market_growth),
            "source_ids": [benchmark["prior_source_id"], benchmark["current_source_id"]],
        },
        "growth_gap_to_industry_pp": _fmt(target_growth - market_growth)
        if target_growth is not None and market_growth is not None else None,
        "growth_gap_to_peer_median_pp": _fmt(target_growth - peer_mid)
        if target_growth is not None and peer_mid is not None else None,
        "vision_drivers": drivers,
        "vision_summary": ("시장 비전은 확인된 성장 동력과 위험 요인을 검토할 가설입니다. "
                           "미래 매출·주가·시장점유율을 예측하거나 보증하지 않습니다."),
        "sources": source_rows,
        "caveats": [
            "입력된 공시·산업 시계열·출처 SHA·권리·기업 비교대상은 독립 검증되지 않았습니다.",
            "기업 매출과 산업 생산·총산출은 정의와 모집단이 달라 성장률만 참고 비교하며, 시장점유율을 계산하지 않습니다.",
            "산업 규모(TAM) 추정, CAGR 전망, 시장 주도권 및 인과관계는 도출하지 않았습니다.",
            "서로 다른 회계연도·개정 공시·출처 발표지연·생존기업 편향은 별도 검증 대상입니다.",
        ],
        "source_authenticated": False, "industry_outlook_verified": False,
        "ai_generated": False, "trade_signal": False,
        "guard_decision_changed": False,
    }
