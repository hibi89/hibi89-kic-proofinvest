"""Optional source-linked Industry Vision panel in the existing local-only workspace."""
from __future__ import annotations

from .industry_vision import (
    MAX_UPLOAD_BYTES, parse_industry_vision_json, analyze_industry_vision,
)


def render_local_industry_vision(st, *, cik: str, as_of: str) -> None:
    st.subheader("KUODRA · Engine C — Industry Vision")
    st.caption("선택한 기업 vs 동종 기업 vs 산업 성장률 / 시장 성장 동력과 위험. "
               "업로드 데이터만 비교하며 SEC·거시 API·LLM을 호출하지 않습니다.")
    uploaded = st.file_uploader(
        "산업·경쟁사 성장률 근거 JSON (선택, 최대 64 KiB)",
        type=["json"], key="kuodra_industry_vision",
    )
    if uploaded is None:
        st.info("비교에 필요한 산업·경쟁사 원본 자료가 없습니다. 산업 성장 전망을 임의 생성하지 않습니다.")
        return
    try:
        if type(uploaded.size) is not int or not 0 < uploaded.size <= MAX_UPLOAD_BYTES:
            raise ValueError("INDUSTRY_JSON_TOO_LARGE")
        result = analyze_industry_vision(
            parse_industry_vision_json(uploaded.getvalue()),
            expected_issuer_cik=cik, analysis_as_of=as_of,
        )
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        st.error("산업 분석 차단: 원본 출처·기간·기업 식별자·성장률 계약을 확인하십시오.")
        return
    st.warning("입력 자료의 수치와 출처 진위는 독립 인증되지 않았습니다. "
               "시장 전망은 투자 권유·미래 성과 예측이 아닙니다.")
    st.write(result["headline"])
    st.write(result["summary"])
    st.table([{
        "대상": result["target"]["name"],
        "종류": "분석 기업",
        "입력 지표의 성장률 %": result["target"]["growth_pct_reported_input"],
    }] + [{
        "대상": row["name"], "종류": "동종 기업",
        "입력 지표의 성장률 %": row["growth_pct_reported_input"],
    } for row in result["peers"]] + [{
        "대상": result["industry_series"]["name"],
        "종류": result["industry_series"]["kind"],
        "입력 지표의 성장률 %": result["industry_series"]["growth_pct_reported_input"],
    }])
    st.json({
        "산업 성장률 대비 격차(퍼센트포인트)": result["growth_gap_to_industry_pp"],
        "경쟁사 중위 성장률 대비 격차(퍼센트포인트)": result["growth_gap_to_peer_median_pp"],
        "산업 지표 단위": result["industry_series"]["unit"],
        "비교 기준 기간": result["periods"], "분석상태": result["status"],
    })
    st.write(result["vision_summary"])
    if result["vision_drivers"]:
        st.table([{
            "성장·위험 동인 (입력값)": row["label"],
            "성격(사용자 입력)": row["direction_operator_supplied"],
            "출처 ID": ", ".join(row["source_ids"]),
        } for row in result["vision_drivers"]])
    st.json({"자료 출처·공개일·SHA256 (미인증)": result["sources"],
             "중요한 제한": result["caveats"],
             "source_authenticated": False, "industry_outlook_verified": False,
             "ai_generated": False, "trade_signal": False})
