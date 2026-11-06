"""Local upload-only arbitrary U.S. issuer evidence-backed question review."""
from __future__ import annotations
import json
from .kuodra_local_workspace_ui import local_workspace_enabled
from .ticker_sec_financial_bridge import _KEYS, _LIMITS
from .owner_source_global_agent import (
    answer_owner_source_question,answer_owner_multi_question,
    verify_owner_source_answer,
)

def _upload(upload,limit:int,required:bool=True):
    if upload is None:
        if required: raise ValueError("REQUIRED_OPERATOR_ORIGINAL_MISSING")
        return None
    if type(upload.size) is not int or not 0<upload.size<=limit:
        raise ValueError("OPERATOR_FILE_TOO_LARGE_OR_EMPTY")
    raw=upload.getvalue()
    if type(raw) is not bytes or len(raw)!=upload.size:
        raise ValueError("OPERATOR_FILE_BYTES_MISMATCH")
    return raw

def render_owner_source_question(st)->None:
    if not local_workspace_enabled(st):
        return
    st.subheader("KUODRA · 미국 전 종목 원본 4개 → 질문 → 검산 → Guard (로컬)")
    st.warning("실제 SEC 발행처 인증·주가/지수·경쟁사·AI 이용권은 별도입니다. "
               "사용자 직접 제공 파일의 구조와 산술만 검증하며 투자 승인하지 않습니다.")
    st.caption("ticker-map, SEC submissions, SEC CompanyFacts, 해당 10-K 원문 "
               "4개 파일을 직접 업로드하십시오. 파일 원본은 서버에서 저장하지 않으며 "
               "고객 데이터나 임의 원문을 외부 모델로 보내지 않습니다.")
    with st.form("kuodra_owner_source_question"):
        ticker=st.text_input("검산할 미국 종목코드",value="",max_chars=12,
                             key="owner_source_ticker")
        as_of=st.text_input("기준일 (YYYY-MM-DD)",value="2026-11-06",
                            max_chars=10,key="owner_source_date")
        question=st.text_input("검토할 질문",value="이 기업의 매출 성장률을 검산해줘",
                                max_chars=180,key="owner_source_question")
        multi=st.checkbox(
            "여러 분석 항목을 한 번에 조사 (질문에 2~4개 주제 필요)",
            value=False,key="owner_source_multi")
        st.caption("다중 조사는 원본 4개를 7단계로 한 번만 검산하고, "
                   "각 분석 항목을 독립적으로 근거 연결해 보여줍니다.")
        uploads={}
        labels={
            "ticker_map":"SEC 상장 종목-기업식별자 대응표 JSON",
            "submissions":"SEC 제출 목록 JSON",
            "companyfacts":"SEC CompanyFacts JSON",
            "original_10k":"해당 10-K 원문 HTML",
        }
        for key in _KEYS:
            uploads[key]=st.file_uploader(
                labels[key],key="owner_source_"+key,
                type=["json"] if key!="original_10k" else ["html","htm"])
        st.caption("선택적 Engine A/C 자료는 사용자 소유 권한이 확인된 원본만 허용. "
                   "검증할 자료가 없으면 해당 엔진은 unavailable로 표시합니다.")
        market=st.file_uploader(
            "선택: 주가/시장 근거 JSON",type=["json"],
            key="owner_source_market")
        industry=st.file_uploader(
            "선택: 산업/경쟁사 근거 JSON",type=["json"],
            key="owner_source_industry")
        with_model=st.checkbox(
            "선택: 로컬 Qwen이 허용 도구를 선택 (기본 비활성)",
            value=False,key="owner_source_model")
        c1=st.checkbox("본인 관리 로컬 모델(127.0.0.1:11435), 외부 중계 아님 확인",
                       value=False,key="owner_source_model_owner")
        c2=st.checkbox("질문 문구+선택한 종목코드만 로컬 모델에 전송 동의",
                       value=False,key="owner_source_question_consent")
        submitted=st.form_submit_button("원본 4개 검산 + 질문 분석 + Guard")
    if not submitted:
        return
    try:
        files={key:_upload(uploads[key],_LIMITS[key]) for key in _KEYS}
        market_raw=_upload(market,131072,False)
        industry_raw=_upload(industry,65536,False)
    except (ValueError,TypeError,AttributeError):
        st.warning("원본 4개 파일과 크기를 확인하세요. 분석을 실행하지 않았습니다.")
        return
    # Normalize the user-entered US ticker once; original filenames and
    # source CIK / selected annual accession are still independently checked.
    ticker=ticker.strip().upper()
    runner=(answer_owner_multi_question if multi else answer_owner_source_question)
    result=runner(
        ticker=ticker,as_of=as_of,question=question,sources=files,
        market_json=market_raw,industry_json=industry_raw,
        use_local_model=with_model,consent_local_model=c1,
        consent_question_text=c2)
    if (result.get("status")!="LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW"
            or not verify_owner_source_answer(
                result,ticker=ticker,as_of=as_of,question=question,
                sources=files,market_json=market_raw,industry_json=industry_raw)):
        st.warning("기업/기간/4개 원본/근거/권한 검증 불일치. 결과를 차단했습니다.")
        st.code(result.get("reason_code","REPLAY_BLOCKED"))
        return
    st.success("7단계 업로드 원본 검산 완료 · Guard "+result["guard_policy_preview"])
    st.info(result["answer"])
    if result["review_mode"]=="MULTI_EVIDENCE_PLAN":
        st.subheader("연속 분석: 검증된 원본 1세트 · 다중 근거")
        st.table([{
            "순서":item["step"],"도구":item["tool"],
            "연구 결과":item["finding"],
            "Guard":item["guard"],
        } for item in result["analysis_findings"]])
    st.table([{"항목":"기업", "결과":result["ticker"]},
              {"항목":"접수번호", "결과":result["filing_accession"]},
              {"항목":"Engine A", "결과":result["engine_a_status"]},
              {"항목":"Engine B", "결과":result["engine_b_status"]},
              {"항목":"Engine C", "결과":result["engine_c_status"]},
              {"항목":"Guard", "결과":result["guard_policy_preview"]}])
    st.json({"source_sha256":result["sources_sha256"],
             "filing_date":result["filing_date"],
             "sources":result["source_urls"],
             "tool_trace":result["tool_trace"],
             "analysis_count":result["analysis_count"],
             "research_plan":result["analysis_findings"],
             "source_authenticated":False,
             "external_sharing_allowed":False,
             "trades":0})
    output=(json.dumps(result,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"),allow_nan=False)+"\n").encode()
    if len(output)<=16384:
        st.download_button("개인 로컬 검토용 파생 보고서 JSON",
            data=output,file_name="kuodra-owner-ticker-UNVERIFIED.json",
            mime="application/json",key="owner_source_review_download",
            on_click="ignore")
    from .owner_source_global_html import render_owner_source_html
    try:
        printable=render_owner_source_html(
            result,ticker=ticker,as_of=as_of,question=question,
            sources=files,market_json=market_raw,industry_json=industry_raw)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        st.warning("독립 HTML 원본 재검산 실패 · 인쇄 보고서를 제공하지 않습니다.")
        return
    st.download_button(
        "검산된 전체 분석 HTML (로컬 인쇄용)",data=printable,
        file_name="kuodra-owner-multi-HOLD-UNVERIFIED.html",
        mime="text/html",key="owner_source_review_html",on_click="ignore")
