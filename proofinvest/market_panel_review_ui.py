"""Local operator-only three-to-five US stock + true I:NDX Engine A UI."""
from __future__ import annotations

import json
from .kuodra_local_workspace_ui import local_workspace_enabled
from .market_panel_review import (
    review_local_market_panel, verify_local_market_panel,
)

_TICKERS = ("NVDA", "AAPL", "MSFT", "AMZN", "GOOGL")
_MAX = 262144


def _upload_bytes(upload) -> bytes:
    if (upload is None or type(getattr(upload, "size", None)) is not int
            or not 0 < upload.size <= _MAX):
        raise ValueError("BOUNDED_JSON_UPLOAD_REQUIRED")
    content = upload.getvalue()
    if type(content) is not bytes or len(content) != upload.size:
        raise ValueError("UPLOAD_SIZE_OR_TYPE_MISMATCH")
    return content


def render_market_panel_review(st) -> None:
    if not local_workspace_enabled(st):
        return
    st.subheader("KUODRA · 미국 3~5종목 + 실제 I:NDX 형식 Engine A (로컬)")
    st.warning(
        "사용자가 로컬에서 제공한 Massive 형식 JSON의 계산만 검증합니다. "
        "실제 Massive/Nasdaq 발행 원본 인증, AI/심사위원 공개 표시권과 "
        "지속 보관권은 아직 미확인입니다. QQQ 대용 불가 · Guard HOLD · "
        "투자 권고 및 공개 공유 금지."
    )
    st.caption(
        "실제 I:NDX 형식 JSON 하나와 미국 주식 3~5종목의 "
        "미조정(adjusted=false) 일봉 JSON을 준비하세요. "
        "CIK는 고정 매핑이며 각 10-K 제출일은 사용자가 기입합니다. "
        "제출일이 가격 구간보다 먼저인지 계산 전에 검사합니다. "
        "이 화면에서는 외부 API를 호출하거나 업로드 파일을 저장하지 않습니다."
    )
    with st.form("kuodra_market_panel_p270"):
        size = st.selectbox("분석 종목 수", (3, 4, 5),
                            key="p270_stock_count")
        symbols = list(_TICKERS[:size])
        as_of = st.text_input(
            "시장 데이터 기준일 (YYYY-MM-DD)",
            value="", placeholder="YYYY-MM-DD", max_chars=10, key="p270_market_asof")
        ndx = st.file_uploader(
            "실제 Nasdaq-100 지수 I:NDX JSON (QQQ 불가)",
            type=["json"], key="p270_upload_ndx")
        files = {}
        filings = {}
        for ticker in symbols:
            files[ticker] = st.file_uploader(
                ticker + " 일봉 JSON", type=["json"],
                key="p270_upload_" + ticker)
            filings[ticker] = st.text_input(
                ticker + " 원본 10-K 제출일 (YYYY-MM-DD)",
                value="", placeholder="YYYY-MM-DD", max_chars=10,
                key="p270_filing_" + ticker)
        submitted = st.form_submit_button(
            "로컬 3~5종목 Engine A 계산 → Guard HOLD")
    if not submitted:
        return
    try:
        sources = {"I:NDX": _upload_bytes(ndx)}
        for ticker in symbols:
            sources[ticker] = _upload_bytes(files[ticker])
    except (ValueError, TypeError, AttributeError):
        st.warning("I:NDX와 선택한 모든 주식의 256KiB 이하 JSON이 필요합니다.")
        return
    report = review_local_market_panel(
        sources, symbols, filings, as_of=as_of)
    if not verify_local_market_panel(
            report, sources, symbols, filings, as_of=as_of):
        st.warning("종목·기준일·파일 형식·가격 거래일 검증 실패: 결과를 차단했습니다.")
        st.code(report.get("reason_code", "P270_MARKET_PANEL_REPLAY_FAILED"))
        return
    st.success("3~5종목 시장수익률·회귀 계산 완료 · Guard HOLD · 미인증")
    st.caption(
        "베타는 표본 공분산 회귀계수입니다. 일간 OLS 절편은 Jensen 알파/"
        "거품률이 아니며, R²는 예측 정확도가 아닙니다. "
        "Engine B 재무·매출과의 인과관계는 이 화면에서 계산하지 않습니다."
    )
    rows = []
    for item in report["issuers"]:
        analysis = item["market_analysis"]
        rows.append({
            "종목": item["ticker"],
            "대조지수": "I:NDX",
            "대응 거래일": item["matched_observation_count"],
            "종목 수익률 (%)": analysis.get("security_return_pct"),
            "NDX 수익률 (%)": analysis.get("benchmark_return_pct"),
            "Beta": analysis.get("beta"),
            "OLS 일간 절편 (%)": analysis.get("regression_intercept_daily_pct"),
            "R²": analysis.get("r_squared"),
            "Guard": "HOLD",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.json({
        "as_of": report["as_of"], "index_symbol": "I:NDX",
        "index_sha256": report["ndx_snapshot_sha256"],
        "issuers": [{"ticker": item["ticker"],
                     "cik": item["issuer_cik"],
                     "filing_date": item["filing_date"],
                     "stock_sha256": item["stock_response_sha256"],
                     "index_sha256": item["index_response_sha256"]}
                    for item in report["issuers"]],
        "network_requests": 0, "source_authenticated": False,
        "vendor_response_authenticity_verified": False,
        "source_rights_verified": False,
        "public_display_allowed": False,
        "trade_executed": False,
        "full_a_b_c_ready": False, "guard": "HOLD",
    })
    data = (json.dumps(report, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()
    st.download_button(
        "로컬 Engine A 근거 JSON (미인증)",
        data=data, file_name="KUODRA_LOCAL_NDX_3_TO_5_UNVERIFIED.json",
        mime="application/json", on_click="ignore",
        key="p270_panel_local_export")
