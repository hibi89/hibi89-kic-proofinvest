"""P219: a real issuer's independently reviewed metadata -> offline close/NDX math.

The market sources are *operator-supplied*, Alpha Vantage-shaped JSON only.
A well-formed payload or hash is NOT provider-origin verification, a data
license, a real NDX entitlement, or proof of available data. This code never
fetches a source or exports raw prices; the real issuer itself was confirmed
in prior one-shot official-publisher tests.
"""
from __future__ import annotations

import json
from typing import Any

from .real_issuer_ticker_review import review_supported_real_ticker

_AS_OF = "2026-11-05"
_PUBLISHER_AVAILABLE_AFTER = {"NVDA": "2026-02-25", "DELL": "2026-03-16"}
_MAX_STOCK = 262144
_MAX_INDEX = 8388608


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.p219-pinned-issuer-local-stock-ndx.v1",
        "status": "BLOCKED", "reason_code": code,
        "source_authenticated_by_sec": False,
        "stock_provider_authenticated": False,
        "ndx_provider_authenticated": False,
        "market_rights_verified": False,
        "commercial_reuse_allowed": False,
        "full_abc_complete": False, "engine_c_complete": False,
        "guard_policy_preview": "HOLD", "guard_executed": False,
        "ai_agent_executed": False, "investment_recommendation": False,
        "trade_executed": False, "network_requests": 0,
    }


def review_real_issuer_local_market_pair(
    *, ticker: str, stock_json: bytes, ndx_json: bytes,
    as_of: str = _AS_OF,
) -> dict[str, Any]:
    """Rebind exact publisher-backed issuer identity to descriptive OLS Engine A.

    This is a local math review, never a live licensed vendor integration.
    Import or export neither original price rows nor API credentials.
    """
    if (type(ticker) is not str or type(as_of) is not str
            or as_of != _AS_OF
            or type(stock_json) is not bytes
            or not 0 < len(stock_json) <= _MAX_STOCK
            or type(ndx_json) is not bytes
            or not 0 < len(ndx_json) <= _MAX_INDEX):
        return _blocked("BOUNDED_LOCAL_PRICE_INPUT_REQUIRED")
    issuer = review_supported_real_ticker(ticker, as_of=as_of)
    if (issuer.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or issuer.get("ticker") not in _PUBLISHER_AVAILABLE_AFTER
            or issuer.get("source_authenticated_by_sec") is not False
            or issuer.get("source_rights_verified") is not False
            or issuer.get("guard_policy_preview") != "HOLD"
            or issuer.get("trade_executed") is not False
            or issuer.get("publisher_original_observed") is not True
            or type(issuer.get("cik")) is not str
            or len(issuer["cik"]) != 10
            or type(issuer.get("source_sha256")) is not str
            or len(issuer["source_sha256"]) != 64):
        return _blocked("REAL_ISSUER_ORIGINAL_SOURCE_NOT_ATTESTED")
    ticker = issuer["ticker"]
    try:
        from .market_provider_alpha_vantage import parse_daily_close_bytes
        from .market_provider_alpha_vantage_index import parse_index_daily_bytes
        from .market_pair_engine_a import analyze_price_index_pair

        stock = parse_daily_close_bytes(
            stock_json, ticker=ticker, as_of=as_of)
        index = parse_index_daily_bytes(
            ndx_json, benchmark="NASDAQ_100", as_of=as_of)
        if (stock.get("requests_attempted") != 0
                or index.get("requests_attempted") != 0
                or stock.get("market_data_rights_verified") is not False
                or index.get("source_rights_verified") is not False
                or index.get("premium_entitlement_verified") is not False
                or stock.get("issuer_authenticated") is not False
                or index.get("provider_response_authenticated") is not False):
            return _blocked("IMPORTED_PRICE_SOURCE_TRUST_INVALID")
        result = analyze_price_index_pair(
            stock=stock, index=index, ticker=ticker,
            issuer_cik=issuer["cik"],
            filing_date=_PUBLISHER_AVAILABLE_AFTER[ticker],
            as_of=as_of, benchmark="NASDAQ_100")
        if (result.get("status") != "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED"
                or result.get("source_authenticated") is not False
                or result.get("source_rights_verified") is not False
                or result.get("trade_executed") is not False
                or result.get("network_requests") != 0
                or result.get("benchmark") != "NASDAQ_100"
                or result.get("issuer_cik") != issuer["cik"]
                or result.get("ticker") != ticker
                or not 31 <= result.get("matched_observation_count", 0) <= 100
                or type(result.get("market_analysis")) is not dict):
            return _blocked("MISMATCHED_STOCK_NDX_PERIOD_OR_UNVERIFIED_MATH")
        a = result["market_analysis"]
        if (a.get("status") not in (
                "REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                or any(a.get(k) is not None and type(a[k]) is not str
                       for k in ("security_return_pct", "benchmark_return_pct",
                                 "beta", "r_squared"))):
            return _blocked("ENGINE_A_METRIC_CONTRACT_INVALID")
        return {
            **_blocked("LOCAL_DESCRIPTIVE_MATH_ONLY_RIGHTS_UNCONFIRMED"),
            "status": "REAL_ISSUER_WITH_LOCAL_NDX_MATH_UNVERIFIED",
            "ticker": ticker, "cik": issuer["cik"],
            "as_of": as_of,
            "issuer_source_sha256": issuer["source_sha256"],
            "issuer_source_url": issuer["source_url"],
            "issuer_release_or_filing_date":
                _PUBLISHER_AVAILABLE_AFTER[ticker],
            "benchmark": "NASDAQ_100",
            "submitted_ndx_symbol": "NDX",
            "local_stock_sha256": result["stock_response_sha256"],
            "local_ndx_sha256": result["index_response_sha256"],
            "market_calculation_sha256": result["source_payload_sha256"],
            "matched_start": result["matched_period_start"],
            "matched_end": result["matched_period_end"],
            "matched_sessions": result["matched_observation_count"],
            "engine_a": {
                "status": a["status"],
                "stock_simple_return_pct": a["security_return_pct"],
                "ndx_simple_return_pct": a["benchmark_return_pct"],
                "beta_descriptive": a["beta"],
                "r_squared_descriptive": a["r_squared"],
            },
        }
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            ArithmeticError, RecursionError, UnicodeError):
        return _blocked("LOCAL_PRICE_OR_INDEX_INPUT_INVALID")


def render_real_issuer_local_market_panel(st, *, ticker: str) -> None:
    """In-memory UI for self-provided price responses, no provider HTTP."""
    from .kuodra_local_workspace_ui import local_workspace_enabled
    if not local_workspace_enabled(st):
        return
    st.subheader("Engine A · 로컬 종목 주가 + 실제 NDX 종목코드 형식 검산")
    st.caption(
        "Alpha Vantage DAILY 형식 JSON 두 개를 본인이 직접 업로드합니다. "
        "INDEX_DATA NDX 형식인지 검사하지만 제공자 진위/지수 이용권은 "
        "검증하지 않습니다. 외부 API 호출·주가 저장·자동 투자 권고 없음."
    )
    stock = st.file_uploader(
        ticker + " 주가 DAILY 응답 JSON", type=["json"],
        key="p219_stock_close_json")
    index = st.file_uploader(
        "Nasdaq-100 (NDX) INDEX_DATA DAILY 응답 JSON (QQQ 대체 불가)",
        type=["json"], key="p219_ndx_close_json")
    ack = st.checkbox(
        "내 로컬 파일로 미인증 산술검산만 진행하며 외부 재배포·투자 승인하지 않음",
        value=False, key="p219_market_local_ack")
    if not st.button(
        "실제 발행사 자료와 주가/NDX 계산 연결 (네트워크 0)",
        key="p219_market_local_review",
        disabled=not (ack and stock is not None and index is not None),
    ):
        return
    try:
        if (type(getattr(stock, "size", None)) is not int
                or type(getattr(index, "size", None)) is not int
                or not 0 < stock.size <= _MAX_STOCK
                or not 0 < index.size <= _MAX_INDEX):
            raise ValueError("LOCAL_MARKET_UPLOAD_BOUNDS")
        stock_raw, index_raw = stock.getvalue(), index.getvalue()
        if (type(stock_raw) is not bytes or len(stock_raw) != stock.size
                or type(index_raw) is not bytes or len(index_raw) != index.size):
            raise ValueError("LOCAL_MARKET_UPLOAD_BYTES")
        result = review_real_issuer_local_market_pair(
            ticker=ticker, stock_json=stock_raw, ndx_json=index_raw,
        )
    except (ValueError, TypeError, KeyError, OSError, RecursionError):
        st.warning("시장자료 크기·바이트·형식 불일치로 계산을 중단했습니다.")
        return
    if result["status"] != "REAL_ISSUER_WITH_LOCAL_NDX_MATH_UNVERIFIED":
        st.warning("발행사·종목/NDX·기준일·원본 또는 투자정보 자료가 불일치합니다.")
        st.code(result["reason_code"], language="text")
        return
    st.success("실제 발행사 근거 + 로컬 주가/NDX 산술검산 연결 (미인증)")
    st.caption(
        result["matched_start"] + " ~ " + result["matched_end"] +
        " · 겹치는 종가 " + str(result["matched_sessions"]) + "거래일"
    )
    market = result["engine_a"]
    st.metric("종목 단순수익률 (미인증)", market["stock_simple_return_pct"] or "자료 없음")
    st.metric("NDX 단순수익률 (미인증)", market["ndx_simple_return_pct"] or "자료 없음")
    st.metric("설명적 베타 (원인·거품 아님)", market["beta_descriptive"] or "자료 없음")
    st.json({
        "market_math": market["status"], "market_rights_verified": False,
        "market_provider_authenticated": False,
        "guard_policy_preview": "HOLD", "full_abc_complete": False,
    })
    st.download_button(
        "로컬 종목/NDX 산술검산 요약 JSON (원본·API키 제외)",
        data=json.dumps(result, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode("utf-8"),
        file_name="kuodra-" + result["ticker"].lower() + "-ndx-UNVERIFIED.json",
        mime="application/json", key="p219_local_market_summary",
    )
    st.warning(
        "지수·주가 제공자 및 재사용 이용권은 인증되지 않았습니다. "
        "출력은 개인 로컬 검토용 산술 결과이며 투자 권고/매매 승인 불가."
    )
