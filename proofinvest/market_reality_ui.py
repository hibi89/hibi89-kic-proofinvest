"""Optional localhost read-only market regression panel for KUODRA."""
from __future__ import annotations

from hashlib import sha256
from .market_reality import (
    MAX_UPLOAD_BYTES, analyze_market_reality, parse_market_reality_json,
)


def render_local_market_reality(st, *, cik: str, as_of: str) -> bytes | None:
    st.subheader("KUODRA · Engine A — Market Reality")
    st.caption("종목 vs S&P 500 / Nasdaq-100 / DJIA 가격 수익률 회귀. "
               "선택 JSON의 과거 가격만 사용합니다. API·LLM·주문 호출 없음.")
    uploaded = st.file_uploader(
        "주가와 시장 지수 시계열 JSON (선택, 최대 128 KiB)",
        type=["json"], key="kuodra_market_reality",
    )
    if uploaded is None:
        st.caption("실제 주가·지수 원본 데이터가 없어 Beta·Alpha를 계산하지 않습니다.")
        return None
    try:
        if type(uploaded.size) is not int or not 0 < uploaded.size <= MAX_UPLOAD_BYTES:
            raise ValueError("MARKET_JSON_SIZE")
        raw = uploaded.getvalue()
        result = analyze_market_reality(
            parse_market_reality_json(raw), expected_issuer_cik=cik,
            analysis_as_of=as_of, uploaded_sha256=sha256(raw).hexdigest(),
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        st.error("Engine A 차단: 가격·시장지수 날짜/단위/출처·발행사를 확인하십시오.")
        return None
    st.warning("이 입력은 독립 출처 인증 전입니다. Beta는 유동성 기여율이 아니고 "
               "회귀 절편은 실적 기여분이 아닙니다. 거품/매매 판정 불가.")
    st.table([
        {"항목": "선택 종목 / 비교지수", "값": result["symbol"] + " / " + result["benchmark"]},
        {"항목": "수익률 정의", "값": result["return_basis"]},
        {"항목": "종목 기간 수익률 (%)", "값": result["security_return_pct"]},
        {"항목": "시장 기간 수익률 (%)", "값": result["benchmark_return_pct"]},
        {"항목": "베타 (표본회귀)", "값": result["beta"] or "미산출"},
        {"항목": "일별 회귀 절편 (%)", "값": result["regression_intercept_daily_pct"] or "미산출"},
        {"항목": "R² (표본내)", "값": result["r_squared"] or "미산출"},
        {"항목": "수익률 관측 개수", "값": result["return_count"]},
        {"항목": "분석 상태", "값": result["status"]},
    ])
    st.json({"주가·지수 출처 (사용자 입력, 미인증)": result["source"],
             "평가 한계": result["limitations"], "market_bubble_proven": False,
             "guard_policy_modified": False, "trade_signal": False})
    return raw
