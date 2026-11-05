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
    # Atomic Streamlit form: both files and explicit approval arrive in one
    # backend event, not a chain of 3 independent reruns that can invalidate
    # earlier file-widget state. No bytes persist after this button handler.
    with st.form("p226_market_pair_atomic", clear_on_submit=False):
        stock = st.file_uploader(
            ticker + " 주가 DAILY 응답 JSON", type=["json"],
            key="p219_stock_close_json")
        index = st.file_uploader(
            "Nasdaq-100 (NDX) INDEX_DATA DAILY 응답 JSON (QQQ 대체 불가)",
            type=["json"], key="p219_ndx_close_json")
        ack = st.checkbox(
            "내 로컬 파일로 미인증 산술검산만 진행하며 외부 재배포·투자 승인하지 않음",
            value=False, key="p219_market_local_ack")
        # P231: a separate explicit local-disk authorization. This checkbox
        # and both submit actions are one atomic form, so no uploaded bytes
        # need be retained across a Streamlit rerun.
        audit_ack = st.checkbox(
            "개인 로컬 SQLite에 검산 해시와 Guard HOLD를 기록하는 데 별도 동의",
            value=False, key="p231_local_audit_ack")
        submitted = st.form_submit_button(
            "실제 발행사 자료와 주가/NDX 계산 연결 (네트워크 0)",
            key="p219_market_local_review",
        )
        audit_submitted = st.form_submit_button(
            "A/B/C 출처결합 Guard HOLD 로컬 감사기록 (원본 저장 안 함)",
            key="p231_local_audit_run",
        )
        receipt_upload = st.file_uploader(
            "P231 로컬 Guard HOLD 영수증 검증용 JSON (DB 쓰기 없음)",
            type=["json"], key="p232_hold_receipt_json",
        )
        replay_submitted = st.form_submit_button(
            "다운로드한 Guard HOLD 영수증과 로컬 SQLite 대조 (읽기 전용)",
            key="p232_replay_receipt",
        )
    if not (submitted or audit_submitted or replay_submitted):
        return
    if replay_submitted and receipt_upload is None:
        st.warning("감사영수증 JSON과 원래 주가/NDX 파일 두 개가 필요합니다.")
        return
    if audit_submitted and not audit_ack:
        st.warning("로컬 SQLite 감사기록 별도 동의가 필요합니다.")
        return
    if not ack or stock is None or index is None:
        st.warning("두 시장 파일과 로컬 산술검산 동의가 모두 필요합니다.")
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
        on_click="ignore",
    )
    if result["ticker"] == "NVDA":
        from .real_issuer_abc_local_review import (
            build_partial_source_bound_abc, replay_partial_source_bound_abc,
        )
        abc=build_partial_source_bound_abc(ab_review=result)
        if (abc["status"]=="REAL_ISSUER_B_LOCAL_A_PEER_C_PARTIAL_UNVERIFIED"
                and replay_partial_source_bound_abc(abc)):
            st.subheader("A/B/C · 발행사·로컬 시장·AMD/Intel 출처결합 검산 (제한)")
            st.caption("A=제공자 미인증 로컬 주가·NDX, B=NVIDIA 발행사 GAAP, "
                       "C=AMD·Intel 공식 감사 10-K 공개 수치. 3엔진의 전체 "
                       "라이선스·원본바이트·산업 대표성은 미검증.")
            st.json({
                "ticker":abc["ticker"],
                "issuer_sha256":abc["source_linked_issuer_sha256"],
                "stock_input_sha256":abc["stock_uploaded_sha256"],
                "ndx_input_sha256":abc["ndx_uploaded_sha256"],
                "peers":abc["engine_c_partial"]["peer_count"],
                "derived_sha256":abc["derived_sha256"],
                "guard_policy_preview":"HOLD",
                "full_abc_complete":False,
            })
            # P232: independent local receipt replay, explicitly user-triggered.
            # Read-only mode never creates missing SQLite data or grants rights.
            if replay_submitted:
                from pathlib import Path
                from .real_issuer_abc_receipt_replay import verify_p231_local_receipt
                try:
                    if (type(getattr(receipt_upload, "size", None)) is not int
                            or not 0 < receipt_upload.size <= 1048576):
                        raise ValueError("RECEIPT_SIZE_INVALID")
                    receipt_bytes = receipt_upload.getvalue()
                    if (type(receipt_bytes) is not bytes
                            or len(receipt_bytes) != receipt_upload.size):
                        raise ValueError("RECEIPT_BYTES_INVALID")
                    receipt = json.loads(receipt_bytes)
                    checked = verify_p231_local_receipt(
                        abc_review=abc, receipt=receipt,
                        audit_db_path=Path.home() /
                            "kuodra-real-abc-guard-audit.sqlite3",
                    )
                except (TypeError, ValueError, OSError, RecursionError,
                        UnicodeError):
                    checked = {"status": "BLOCKED",
                               "reason_code": "INVALID_RECEIPT_UPLOAD"}
                if checked["status"] == "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY":
                    st.success("A/B/C 영수증 ↔ 원본 검산자료 ↔ 로컬 SQLite 일치")
                    st.json({
                        "event_hash": checked["event_hash"],
                        "local_chain_valid": True,
                        "receipt_matches_local_source": True,
                        "source_authenticated_by_sec": False,
                        "market_rights_verified": False,
                        "peer_rights_verified": False,
                        "full_abc_complete": False,
                        "trade_executed": False,
                    })
                else:
                    st.warning("영수증·원본 검산자료·SQLite 기록이 일치하지 않습니다.")
                    st.code(checked["reason_code"], language="text")
            # P231: exact same operator form event, with separate consent,
            # source replay and only bounded SHA/status fields written locally.
            if audit_submitted and audit_ack:
                from pathlib import Path
                from .real_issuer_abc_guard_audit import (
                    run_source_bound_abc_hold_audit,
                )
                local_db = Path.home() / "kuodra-real-abc-guard-audit.sqlite3"
                hold = run_source_bound_abc_hold_audit(
                    abc_review=abc, audit_db_path=local_db,
                    acknowledge_local_persistence=True,
                )
                if hold["status"] == "PARTIAL_SOURCE_BOUND_ABC_GUARD_HOLD_AUDIT_RECORDED":
                    st.success("A/B/C 출처결합 Guard HOLD SQLite 감사 기록 완료 (로컬 전용)")
                    st.json({
                        "run_id": hold["report"]["run_id"],
                        "source_bound_abc_digest": hold["report"]["source_bound_abc_digest"],
                        "event_hash": hold["report"]["audit"]["event_hash"],
                        "idempotent_replay": hold["report"]["audit"]["replayed"],
                        "guard_decision": "HOLD",
                        "market_rights_verified": False,
                        "peer_rights_verified": False,
                        "trade_executed": False,
                    })
                    st.download_button(
                        "A/B/C Guard HOLD 로컬 감사영수증 JSON (원본 제외)",
                        data=json.dumps(hold["report"],ensure_ascii=False,
                                        sort_keys=True,separators=(",",":"),
                                        allow_nan=False).encode("utf-8"),
                        file_name="kuodra-nvda-partial-abc-hold-audit.json",
                        mime="application/json",
                        key="p231_abc_hold_receipt_download",
                        on_click="ignore",
                    )
                else:
                    st.warning("A/B/C 원문·시장·동종기업 검산 또는 로컬 감사 체인 실패")
            st.download_button(
                "실제 발행사 A/B/C 제한 결합 JSON (출처·이용권 미인증)",
                data=json.dumps(abc,ensure_ascii=False,sort_keys=True,
                                separators=(",",":"),allow_nan=False).encode("utf-8"),
                file_name="kuodra-nvda-partial-abc-UNVERIFIED.json",
                mime="application/json",key="p224_partial_abc_download",
                on_click="ignore",
            )
            # P225: independently regenerate a conservative cross-source
            # fact-review HTML, with A unavailable and B/C numeric-only.
            from .real_issuer_abc_fact_review import (
                build_source_factual_abc_brief,
                replay_source_factual_abc_brief,
                source_factual_brief_html,
            )
            brief=build_source_factual_abc_brief(abc)
            if (brief["status"] ==
                    "LOCAL_A_B_C_CLAIM_REVIEW_FOR_HUMAN_ONLY"
                    and replay_source_factual_abc_brief(brief,abc)):
                st.subheader("A/B/C · 실제 원문 연결 사실검산 설명서 (AI 아님)")
                st.caption("A 제공자 미인증→UNAVAILABLE, B NVIDIA 실적 수치→"
                           "VERIFIED(역사적 산술만), C AMD·Intel 수치→"
                           "공개자료 대조만. 모델 호출·권한 인증·투자추천 없음.")
                st.dataframe([
                    {"엔진":item["engine"],"검토 항목":item["claim_id"],
                     "검증 한계":item["verification"],"설명":item["text"]}
                    for item in brief["claims"]
                ],hide_index=True,use_container_width=True)
                # P226 real-source model triage requires independent two
                # explicit consents; default path is pure, zero HTTP.
                from .real_issuer_model_focus import (
                    render_real_issuer_model_focus_panel,
                )
                render_real_issuer_model_focus_panel(st,abc,brief)
                st.download_button(
                    "A/B/C 출처·사실검산 설명서 HTML (AI 미실행)",
                    data=source_factual_brief_html(brief,abc),
                    file_name="kuodra-nvda-factual-review-NO-AI.html",
                    mime="text/html",key="p225_fact_brief_html",
                    on_click="ignore",
                )
                st.download_button(
                    "A/B/C 출처·사실검산 설명서 JSON (AI 미실행)",
                    data=json.dumps(brief,ensure_ascii=False,sort_keys=True,
                                    separators=(",",":"),allow_nan=False).encode("utf-8"),
                    file_name="kuodra-nvda-factual-review-NO-AI.json",
                    mime="application/json",key="p225_fact_brief_json",
                    on_click="ignore",
                )
            else:
                st.warning("검증 가능한 출처연결 사실 설명을 생성할 수 없어 "
                           "설명서 출력을 차단했습니다.")
            st.warning("3개 엔진의 출처 결합은 개인 검산용입니다. "
                       "시장 제공자 진위·공시 원본 바이트·이용권·모델 처리는 "
                       "인증하지 않았고 매매 승인은 불가합니다. Guard HOLD.")
        else:
            st.warning("Engine C 동종기업 원문 교차검증 불일치로 통합 보고서를 차단했습니다.")
    st.warning(
        "지수·주가 제공자 및 재사용 이용권은 인증되지 않았습니다. "
        "출력의 SHA-256은 변조 탐지용 비밀키 없는 체크섬일 뿐 출처 인증이 아닙니다. "
        "개인 로컬 검토용이며 Engine C·투자 권고·매매 승인 불가."
    )
