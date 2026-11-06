"""Operator-owned 4+4 SEC-format source upload, two-issuer peer comparison."""
from __future__ import annotations
import json
from .kuodra_local_workspace_ui import local_workspace_enabled
from .ticker_sec_financial_bridge import _KEYS,_LIMITS
from .owner_peer_compare import (
    compare_owner_peer,verify_owner_peer,render_owner_peer_html,
)

def render_owner_peer_compare(st)->None:
    if not local_workspace_enabled(st):
        return
    st.subheader("KUODRA · 미국 두 기업 공시 원본 직접 비교 (Engine C)")
    st.warning("현재는 사용자가 직접 제공한 SEC 형식 원본 구조 검산만 수행합니다. "
               "실제 SEC 원본 인증, 기업 간 동종성, 원본 및 AI 재이용권은 미확인입니다. "
               "공개 배포·투자권고·자동 거래 불가.")
    st.caption("대상과 비교기업 각각 10-K 기반 원본 4개를 업로드하세요. "
               "서로 다른 CIK와 제출번호가 필요하며 결산일 차이가 45일을 넘으면 "
               "성장률 격차는 UNAVAILABLE로 처리합니다.")
    labels={
        "ticker_map":"종목·CIK 대응표",
        "submissions":"SEC 제출 목록",
        "companyfacts":"SEC CompanyFacts",
        "original_10k":"해당 10-K HTML 원문",
    }
    with st.form("owner_peer_compare"):
        col1,col2=st.columns(2)
        with col1:
            ticker=st.text_input("대상 종목",max_chars=12,key="owner_pair_primary")
        with col2:
            peer_ticker=st.text_input("비교 종목",max_chars=12,key="owner_pair_peer")
        as_of=st.text_input("비교 기준일 (YYYY-MM-DD)",value="2026-11-06",
                            max_chars=10,key="owner_pair_asof")
        uploads={}
        for role in ("primary","peer"):
            st.markdown("**"+("대상 기업" if role=="primary" else
                            "비교 기업")+" 공시 파일 4개**")
            for key in _KEYS:
                uploads[(role,key)]=st.file_uploader(
                    ("대상 " if role=="primary" else "비교 ")+labels[key],
                    type=["html","htm"] if key=="original_10k" else ["json"],
                    key="owner_pair_"+role+"_"+key)
        submitted=st.form_submit_button("두 기업 각각 검산 → Engine C 비교 → Guard")
    if not submitted:
        return
    def extract(role):
        data={}
        for key in _KEYS:
            upload=uploads[(role,key)]
            if upload is None or type(upload.size) is not int or not(
                    0<upload.size<=_LIMITS[key]):
                raise ValueError("FOUR_UPLOADS_REQUIRED")
            raw=upload.getvalue()
            if type(raw) is not bytes or len(raw)!=upload.size:
                raise ValueError("UPLOAD_BYTES_MISMATCH")
            data[key]=raw
        return data
    try:
        src=extract("primary")
        peer=extract("peer")
    except (ValueError,TypeError,AttributeError):
        st.warning("서로 다른 2개 기업의 공시 형식 원본 4개씩을 확인하세요.")
        return
    ticker=ticker.strip().upper()
    peer_ticker=peer_ticker.strip().upper()
    args=dict(ticker=ticker,peer_ticker=peer_ticker,as_of=as_of,
              sources=src,peer_sources=peer)
    packet=compare_owner_peer(**args)
    if not verify_owner_peer(packet,**args):
        st.warning("기업·CIK·원본/기간/산술 검증 실패. 비교를 차단했습니다.")
        st.code(packet.get("reason_code","PAIR_SOURCE_REPLAY_FAILED"))
        return
    st.success("독립 원본 2세트 · 14단계 검산 완료 · Guard "+packet["comparison_guard"])
    st.table([{"항목":"대상 성장률 (%)","결과":packet["primary"]["revenue_growth_pct"]},
              {"항목":"비교 성장률 (%)","결과":packet["peer"]["revenue_growth_pct"]},
              {"항목":"성장률 격차 (pp)","결과":
                  packet["growth_gap_primary_minus_peer_pp"] or "UNAVAILABLE"},
              {"항목":"최대 결산일 차이 (일)","결과":packet["max_fiscal_end_offset_days"]},
              {"항목":"비교 상태","결과":packet["comparison_status"]},
              {"항목":"Guard","결과":packet["comparison_guard"]}])
    st.json({"primary":packet["primary"],"peer":packet["peer"],
             "limits":packet["limitations"],
             "source_authenticated":False,"source_rights_verified":False,
             "peer_reuse_rights_verified":False,
             "external_sharing_allowed":False})
    data=(json.dumps(packet,ensure_ascii=False,sort_keys=True,
                     separators=(",",":"),allow_nan=False)+"\n").encode()
    html=render_owner_peer_html(packet,**args)
    st.download_button("로컬 비교 근거 JSON",data=data,
        file_name="KUODRA_TWO_ISSUERS_UNVERIFIED.json",
        mime="application/json",on_click="ignore",key="owner_pair_json")
    st.download_button("로컬 비교 인쇄 HTML",data=html,
        file_name="KUODRA_TWO_ISSUERS_UNVERIFIED.html",
        mime="text/html",on_click="ignore",key="owner_pair_html")
