"""P219: a real issuer's independently reviewed metadata -> offline close/NDX math.

The market sources are *operator-supplied*, Alpha Vantage-shaped JSON only.
A well-formed payload or hash is NOT provider-origin verification, a data
license, a real NDX entitlement, or proof of available data. This code never
fetches a source or exports raw prices; the real issuer itself was confirmed
in prior one-shot official-publisher tests.
"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .real_issuer_ticker_review import review_supported_real_ticker

_AS_OF = "2026-11-05"
_PUBLISHER_AVAILABLE_AFTER = {"NVDA": "2026-02-25", "DELL": "2026-03-16"}
_MAX_STOCK = 262144
_MAX_INDEX = 8388608
_AB_SCHEMA = "kuodra.p220-issuer-financial-market-joined.v1"
_PINNED_ENGINE_B = {
    "NVDA": ("65.47", "0.8555", "1.30", "46.86"),
    "DELL": ("18.80", "1.8843", "51.96", "36.60"),
}
_FINANCIAL_KEYS = (
    "issuer_revenue_growth_pct", "cashflow_to_net_income_ratio",
    "receivables_minus_revenue_growth_pp",
    "inventory_minus_revenue_growth_pp",
)


def _canonical_derived_bytes(packet: dict[str, Any]) -> bytes:
    return json.dumps(packet, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def verify_derived_ab_checksum(packet: Any) -> bool:
    """Detect accidental changes to the derived local packet; not authentication.

    An attacker may recalculate this unkeyed digest. The attached source
    digests likewise cannot establish provider identity or usage rights.
    """
    if (type(packet) is not dict
            or packet.get("combined_review_schema") != _AB_SCHEMA
            or packet.get("status") != "REAL_ISSUER_WITH_LOCAL_NDX_MATH_UNVERIFIED"
            or packet.get("guard_policy_preview") != "HOLD"
            or packet.get("full_abc_complete") is not False
            or packet.get("market_rights_verified") is not False
            or packet.get("stock_provider_authenticated") is not False
            or packet.get("ndx_provider_authenticated") is not False
            or type(packet.get("engine_a")) is not dict
            or type(packet.get("engine_b")) is not dict
            or packet.get("combined_review_digest_kind") !=
               "UNKEYED_DERIVED_INTEGRITY_ONLY"):
        return False
    digest = packet.get("combined_review_sha256")
    if type(digest) is not str or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest):
        return False
    try:
        unsigned = dict(packet)
        del unsigned["combined_review_sha256"]
        return sha256(_canonical_derived_bytes(unsigned)).hexdigest() == digest
    except (ValueError, TypeError, OverflowError, RecursionError):
        return False


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
    # P220: refuse a partial or altered issuer fact bridge, even if market
    # files are independently well formed. This remains a historical pin.
    if (issuer.get("review_as_of") != as_of
            or issuer.get("financial_review") !=
               "ISSUER_ENGINE_B_NUMERICAL_SCREEN_UNVERIFIED"
            or tuple(issuer.get(key) for key in _FINANCIAL_KEYS)
               != _PINNED_ENGINE_B[ticker]
            or any(type(issuer.get(key)) is not str for key in (
                "fiscal_prior_end", "fiscal_latest_end", "source_url",
                "source_ci_run"))):
        return _blocked("PINNED_REAL_ISSUER_ENGINE_B_REPLAY_FAILED")
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
        packet = {
            **_blocked("LOCAL_DESCRIPTIVE_MATH_ONLY_RIGHTS_UNCONFIRMED"),
            "status": "REAL_ISSUER_WITH_LOCAL_NDX_MATH_UNVERIFIED",
            "combined_review_schema": _AB_SCHEMA,
            "combined_review_digest_kind": "UNKEYED_DERIVED_INTEGRITY_ONLY",
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
            "engine_b": {
                "status": "REAL_PUBLISHER_DERIVED_PARTIAL_FINANCIAL_SCREEN",
                "fiscal_prior_end": issuer["fiscal_prior_end"],
                "fiscal_latest_end": issuer["fiscal_latest_end"],
                "revenue_growth_pct": issuer["issuer_revenue_growth_pct"],
                "cashflow_to_net_income_ratio":
                    issuer["cashflow_to_net_income_ratio"],
                "receivables_minus_revenue_growth_pp":
                    issuer["receivables_minus_revenue_growth_pp"],
                "inventory_minus_revenue_growth_pp":
                    issuer["inventory_minus_revenue_growth_pp"],
                "issuer_financial_source_sha256": issuer["source_sha256"],
                "issuer_source_ci_run": issuer["source_ci_run"],
            },
        }
        packet["combined_review_sha256"] = sha256(
            _canonical_derived_bytes(packet)).hexdigest()
        return packet
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
    if not verify_derived_ab_checksum(result):
        st.warning("결합 A/B 보고서의 산술 결과 체크섬이 일치하지 않습니다.")
        return
    st.success("실제 발행사 Engine B + 로컬 Engine A 결합 (시장 미인증)")
    st.caption(
        result["matched_start"] + " ~ " + result["matched_end"] +
        " · 겹치는 종가 " + str(result["matched_sessions"]) + "거래일"
    )
    market = result["engine_a"]
    st.metric("종목 단순수익률 (미인증)", market["stock_simple_return_pct"] or "자료 없음")
    st.metric("NDX 단순수익률 (미인증)", market["ndx_simple_return_pct"] or "자료 없음")
    st.metric("설명적 베타 (원인·거품 아님)", market["beta_descriptive"] or "자료 없음")
    issuer_b = result["engine_b"]
    st.subheader("Engine B · 발행사 원문 근거 재무 검산 (부분)")
    st.metric("발행사 매출 증가율 (%)", issuer_b["revenue_growth_pct"])
    st.metric("발행사 영업현금/순이익", issuer_b["cashflow_to_net_income_ratio"])
    st.caption(
        "매출채권 증가율 차이 " +
        issuer_b["receivables_minus_revenue_growth_pp"] +
        "pp · 재고 증가율 차이 " +
        issuer_b["inventory_minus_revenue_growth_pp"] + "pp"
    )
    st.json({
        "market_math": market["status"], "market_rights_verified": False,
        "market_provider_authenticated": False,
        "guard_policy_preview": "HOLD", "full_abc_complete": False,
        "report_integrity_only_sha256": result["combined_review_sha256"],
    })
    st.download_button(
        "발행사 재무 B + 로컬 시장 A 결합 JSON (원본·API키 제외)",
        data=json.dumps(result, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"), allow_nan=False).encode("utf-8"),
        file_name="kuodra-" + result["ticker"].lower() + "-ab-UNVERIFIED.json",
        mime="application/json", key="p219_local_market_summary",
    )
    st.warning(
        "지수·주가 제공자 및 재사용 이용권은 인증되지 않았습니다. "
        "출력의 SHA-256은 변조 탐지용 비밀키 없는 체크섬일 뿐 출처 인증이 아닙니다. "
        "개인 로컬 검토용이며 Engine C·투자 권고·매매 승인 불가."
    )
