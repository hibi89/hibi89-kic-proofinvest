"""P146: one illustrative same-industry issuer from independently gated API.

This is a peer-only, same-fiscal-period DESCRIPTIVE revenue comparison.
A single alphabetical issuer selected from an industry mapping is NOT a
representative cohort or an independently verified industry benchmark.
No HTTP or license claim occurs inside these parsing functions.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from typing import Any
from urllib.parse import quote

from .sec_companyfacts import verify_sec_annual_revenue
from .ticker_research_intake import _TICKER
from .ticker_provider_sec_api import (
    _MAP_HOST, _MAX_MAP, _MAX_QUERY, _MAX_XBRL,
    _object, _cik, _filing, _facts_from_xbrl,
)


def _industry(value: Any) -> str:
    if (type(value) is not str or not 3 <= len(value) <= 100
            or any(ord(c) < 32 or ord(c) > 126 for c in value)
            or value.strip() != value):
        raise ValueError("VENDOR_PEER_INDUSTRY_INVALID")
    return value


def extract_target_industry(mapping_raw: bytes, *, target_cik: str,
                            ticker: str) -> str:
    rows = _object(mapping_raw, _MAX_MAP)
    if type(rows) is not list:
        raise ValueError("VENDOR_PEER_TARGET_MAPPING_INVALID")
    matches = [r for r in rows if type(r) is dict
               and r.get("ticker") == ticker
               and _cik(r.get("cik")) == target_cik
               and r.get("isDelisted") is not True]
    if len(matches) != 1:
        raise ValueError("VENDOR_PEER_TARGET_AMBIGUOUS")
    target = matches[0]
    if (target.get("currency") != "USD"
            or target.get("category") != "Domestic Common Stock"):
        raise ValueError("VENDOR_PEER_TARGET_CLASS_OR_CURRENCY")
    return _industry(target.get("industry"))


def industry_mapping_url(industry: str) -> str:
    return _MAP_HOST + "/mapping/industry/" + quote(_industry(industry), safe="")


def choose_one_peer(mapping_raw: bytes, *, target_cik: str,
                    target_ticker: str, industry: str) -> tuple[str, str]:
    """One deterministic exploratory name, no market-wide stock ranking."""
    rows = _object(mapping_raw, _MAX_MAP)
    if type(rows) is not list or not 1 <= len(rows) <= 300:
        raise ValueError("VENDOR_PEER_MAPPING_SIZE_INVALID")
    candidates = []
    seen = set()
    for row in rows:
        if type(row) is not dict or row.get("isDelisted") is not False:
            continue
        if (row.get("category") != "Domestic Common Stock"
                or row.get("currency") != "USD"
                or row.get("industry") != industry):
            continue
        ticker = row.get("ticker")
        if type(ticker) is not str or not _TICKER.fullmatch(ticker):
            continue
        cik = _cik(row.get("cik"))
        if cik == target_cik or ticker == target_ticker:
            continue
        if cik in seen:
            raise ValueError("VENDOR_PEER_DUPLICATE_CIK")
        seen.add(cik)
        candidates.append((ticker, cik))
    if not candidates:
        raise ValueError("VENDOR_PEER_CANDIDATE_UNAVAILABLE")
    ticker, cik = min(candidates)
    return ticker, cik


def build_peer_comparison(
    *, peer_ticker: str, peer_cik: str, peer_accession: str,
    peer_filing_date: str, peer_period_end: str,
    peer_mapping_raw: bytes, peer_query_raw: bytes, peer_xbrl_raw: bytes,
    industry: str, target_cik: str, target_ticker: str,
    target_prior_revenue_usd: str, target_current_revenue_usd: str,
    target_prior_end: str, target_current_end: str, as_of: str,
) -> dict[str, Any]:
    """Use exact annual periods and USD, refuse arbitrary fiscal alignment."""
    if (peer_cik == target_cik or peer_ticker == target_ticker
            or peer_period_end != target_current_end):
        raise ValueError("VENDOR_PEER_PERIOD_OR_IDENTITY_DIFFERENT")
    peer_cf = _facts_from_xbrl(
        peer_xbrl_raw, cik=peer_cik, accession=peer_accession,
        filed=peer_filing_date, fiscal_end=peer_period_end,
    )
    from .ticker_provider_sec_api import _object as parse_json
    verdict = verify_sec_annual_revenue(
        parse_json(peer_cf, _MAX_XBRL),
        cik=peer_cik, accession=peer_accession,
        current_end=target_current_end, prior_end=target_prior_end,
        as_of=as_of,
    )
    if (verdict.get("status") != "calculated_unverified"
            or verdict.get("source_rights_verified") is not False
            or verdict.get("authenticated_external_source") is not False
            or verdict.get("live_api_called") is not False):
        raise ValueError("VENDOR_PEER_10K_REVENUE_PERIOD_UNAVAILABLE")
    base = Decimal(target_prior_revenue_usd)
    present = Decimal(target_current_revenue_usd)
    if base <= 0 or present < 0:
        raise ValueError("VENDOR_TARGET_REVENUE_INVALID")
    target_pct = (present / base - 1) * Decimal(100)
    peer_pct = Decimal(verdict["growth_pct"])
    gap = (target_pct - peer_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "schema": "kuodra.vendor-exploratory-one-peer-revenue.v1",
        "status": "PEER_ONE_PERIOD_ALIGNED_UNVERIFIED",
        "peer_ticker": peer_ticker, "peer_cik": peer_cik,
        "target_ticker": target_ticker, "target_cik": target_cik,
        "industry_provider_label_unverified": industry,
        "peer_selection": "LEXICOGRAPHIC_SINGLE_LISTED_COMMON_SHARE_NOT_REPRESENTATIVE",
        "prior_period_end": target_prior_end,
        "current_period_end": target_current_end, "as_of": as_of,
        "prior_revenue_usd": verdict["prior_usd"],
        "current_revenue_usd": verdict["current_usd"],
        "target_growth_pct": str(target_pct.quantize(Decimal("0.01"))),
        "peer_growth_pct": verdict["growth_pct"],
        "growth_gap_to_one_peer_pp": str(gap),
        "peer_filing_accession": peer_accession,
        "peer_filing_date_self_reported": peer_filing_date,
        "provider_response_sha256": {
            "industry_mapping": sha256(peer_mapping_raw).hexdigest(),
            "filing_search": sha256(peer_query_raw).hexdigest(),
            "xbrl": sha256(peer_xbrl_raw).hexdigest(),
            "derived_companyfacts": sha256(peer_cf).hexdigest(),
        },
        "single_peer_not_industry_cohort": True,
        "industry_series_status": "UNAVAILABLE",
        "industry_growth_pct": None,
        "full_engine_c_ready": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "historical_vintage_verified": False,
        "redistribution_allowed": False,
        "guard_policy_modified": False,
        "trade_executed": False,
    }


def fetch_one_peer_using_vendor(
    *, target_mapping_raw: bytes, target_cik: str, target_ticker: str,
    target_revenue: dict[str, Any], as_of: str,
    read, cutoff,
) -> dict[str, Any]:
    """Consumes up to three additional operator-authorized vendor requests.

    Caller owns the total request budget, key and real-network approvals.
    Errors are reported as unavailable and never forge an industry metric.
    """
    industry = extract_target_industry(target_mapping_raw,
                                       target_cik=target_cik,
                                       ticker=target_ticker)
    m_raw = read("GET", industry_mapping_url(industry), None, _MAX_MAP)
    peer_ticker, peer_cik = choose_one_peer(
        m_raw, target_cik=target_cik, target_ticker=target_ticker,
        industry=industry,
    )
    import json
    query = {
        "query": f'cik:{int(peer_cik)} AND formType:"10-K" AND filedAt:[1993-01-01 TO {as_of}]',
        "from": "0", "size": "10", "sort": [{"filedAt": {"order": "desc"}}],
    }
    q_raw = read("POST", _MAP_HOST,
                 json.dumps(query, separators=(",", ":")).encode(), _MAX_QUERY)
    from .ticker_provider_sec_api import _filing
    filed, acc, period_end, _filename = _filing(
        q_raw, ticker=peer_ticker, cik=peer_cik, cutoff=cutoff,
    )
    if period_end != target_revenue["current_end"]:
        raise ValueError("VENDOR_PEER_FISCAL_PERIOD_MISMATCH")
    x_raw = read("GET", _MAP_HOST + "/xbrl-to-json?accession-no=" + acc,
                 None, _MAX_XBRL)
    return build_peer_comparison(
        peer_ticker=peer_ticker, peer_cik=peer_cik,
        peer_accession=acc, peer_filing_date=filed,
        peer_period_end=period_end, peer_mapping_raw=m_raw,
        peer_query_raw=q_raw, peer_xbrl_raw=x_raw, industry=industry,
        target_cik=target_cik, target_ticker=target_ticker,
        target_prior_revenue_usd=target_revenue["prior_usd"],
        target_current_revenue_usd=target_revenue["current_usd"],
        target_prior_end=target_revenue["prior_end"],
        target_current_end=target_revenue["current_end"], as_of=as_of,
    )
