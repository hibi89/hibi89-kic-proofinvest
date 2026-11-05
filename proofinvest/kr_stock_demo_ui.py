"""Locally gated Korean stock/KOSPI or KOSDAQ price comparison."""
from __future__ import annotations
from .kr_stock_demo import analyze_kr_prices
from .kuodra_local_workspace_ui import local_workspace_enabled

def render_kr_stock_demo(st):
    if not local_workspace_enabled(st):
        return
    st.subheader("한국 주식 분석 시연 · 로컬")
    st.caption("KOSPI/KOSDAQ 대체 시연 경로. 미국 Nasdaq-100 연결은 보존되며 "
               "별도 이용권 승인 전 비활성입니다.")
    st.warning("KRX 자료도 제3자 공개·심사위원 배포 이용권은 별도 확인해야 합니다. "
               "사용자가 제공한 CSV로 로컬 산술 검산만 실행합니다.")
    with st.form("kr_stock_demo"):
        ticker=st.text_input("한국 주식 종목코드",value="005930",max_chars=6)
        benchmark=st.selectbox("비교지수",["KOSPI","KOSDAQ"])
        cutoff=st.text_input("분석 기준일",value="2026-11-06",max_chars=10)
        upload=st.file_uploader("CSV: date,stock_close,benchmark_close (31~501행)",
                                type=["csv"],key="kr_stock_demo_csv")
        submit=st.form_submit_button("로컬 검산")
    if not submit:
        return
    if upload is None:
        st.info("데이터를 업로드해야 분석할 수 있습니다.")
        return
    try:
        if type(upload.size) is not int or not 0 < upload.size <= 131072:
            raise ValueError("UPLOAD_SIZE")
        data=upload.getvalue()
        if type(data) is not bytes or len(data) != upload.size:
            raise ValueError("UPLOAD_BYTES")
        result=analyze_kr_prices(data,ticker=ticker,benchmark=benchmark,as_of=cutoff)
    except (ValueError,TypeError,OverflowError,ArithmeticError):
        st.error("CSV 날짜·가격·형식 또는 종목코드 검증 실패")
        return
    st.table([{"항목":k,"값":result[k]} for k in
              ("ticker","benchmark","period_start","period_end",
               "stock_return_pct","index_return_pct","beta",
               "ols_intercept_daily_pct","r_squared")])
    st.caption("로컬 입력 SHA256: "+result["original_sha256"])
    st.json({"status":result["status"],"source_authenticated":False,
             "source_rights_verified":False,"external_sharing_allowed":False,
             "market_bubble_proven":False,"guard_policy_preview":"HOLD",
             "full_a_b_c_ready":False,"network_requests":0})
