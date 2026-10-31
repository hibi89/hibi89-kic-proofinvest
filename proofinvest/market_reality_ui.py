"""Optional localhost read-only market regression panel for KUODRA."""
from __future__ import annotations

from hashlib import sha256
from .market_price_csv import market_price_csv_to_json
from .market_reality import (
    MAX_UPLOAD_BYTES, analyze_market_reality, parse_market_reality_json,
)


def render_local_market_reality(st, *, cik: str, as_of: str) -> bytes | None:
    st.subheader("KUODRA · Engine A — Market Reality")
    st.caption("종목 vs S&P 500 / Nasdaq-100 / DJIA 수익률 회귀. "
               "기존 JSON 또는 정렬된 3열 CSV를 로컬 변환합니다. API·LLM·주문 호출 없음.")
    uploaded = st.file_uploader(
        "주가와 시장 지수 시계열 JSON 또는 CSV (선택, 최대 128 KiB)",
        type=["json", "csv"], key="kuodra_market_reality",
    )
    if uploaded is None:
        st.caption("실제 주가·지수 원본 데이터가 없어 Beta·Alpha를 계산하지 않습니다.")
        return None
    # CSV supplies an explicit paired-price format; its source URL, price
    # basis and release date remain operator claims, not vendor authentication.
    # No additional upload slot is introduced, preserving existing browser E2E.
    upload_name = getattr(uploaded, "name", "market.json")
    suffix = upload_name.lower() if type(upload_name) is str else ""
    is_csv = suffix.endswith(".csv")
    if is_csv:
        st.caption("CSV 정확한 열: date,security_close,benchmark_close. "
                   "가격은 양의 소수(최대 8자리), 날짜는 영업일 순서. "
                   "휴장일은 공통 행으로 제외하며 결측치 보간하지 않습니다.")
        symbol = st.text_input("Engine A 종목 티커", key="kuodra_csv_symbol",
                               max_chars=25)
        benchmark = st.selectbox("Engine A 시장지수",
                                 ["NASDAQ_100", "S&P_500", "DJIA"],
                                 key="kuodra_csv_benchmark")
        basis = st.selectbox("Engine A 수익률 기준",
                             ["PRICE_ONLY_CLOSE", "ADJUSTED_CLOSE_TOTAL_RETURN_PROXY"],
                             key="kuodra_csv_basis")
        source_url = st.text_input("Engine A CSV 출처 HTTPS URL (사용자 주장)",
                                   key="kuodra_csv_url", max_chars=400)
        published = st.text_input("Engine A CSV 공개일 (YYYY-MM-DD, 사용자 주장)",
                                  key="kuodra_csv_publication", max_chars=10)
    try:
        if type(uploaded.size) is not int or not 0 < uploaded.size <= MAX_UPLOAD_BYTES:
            raise ValueError("MARKET_INPUT_SIZE")
        upload_bytes = uploaded.getvalue()
        if is_csv:
            raw = market_price_csv_to_json(
                upload_bytes, issuer_cik=cik, as_of=as_of, symbol=symbol,
                benchmark=benchmark, return_basis=basis, source_url=source_url,
                published_at=published,
            )
        elif suffix.endswith(".json"):
            raw = upload_bytes
        else:
            raise ValueError("MARKET_UNSUPPORTED_FILE_SUFFIX")
        result = analyze_market_reality(
            parse_market_reality_json(raw), expected_issuer_cik=cik,
            analysis_as_of=as_of, uploaded_sha256=sha256(raw).hexdigest(),
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        st.error("Engine A 차단: 가격·시장지수 날짜/단위/출처·발행사를 확인하십시오.")
        return None
    if is_csv:
        st.caption("CSV 원본 SHA256: " + sha256(upload_bytes).hexdigest()
                   + " / 다운로드 보고서의 upload_sha256은 정규화 JSON SHA256입니다."
                   " CSV 원본·발행시점·출처 라이선스는 독립 인증되지 않았습니다.")
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
