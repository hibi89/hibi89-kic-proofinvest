"""Local-only, read-only ML evaluation explanation component for KUODRA."""
from __future__ import annotations

from .ml_explainability import (
    MAX_ML_REPORT_BYTES, explain_ml_evaluation, parse_ml_evaluation_json,
)


def render_local_ml_evaluation(st, *, cik: str, as_of: str) -> None:
    """Render only in an already localhost-gated workspace; no model execution."""
    st.subheader("KUODRA · ML 결과 쉬운 해석 / 도출 근거")
    st.caption("선택 기능: 모델 평가 JSON만 로컬로 읽습니다. 학습·Gemini·SEC 요청 없음. "
               "입력된 평가값은 독립 재현·출처 인증 전까지 미검증입니다.")
    upload = st.file_uploader("ML 평가 결과 JSON (선택, 최대 64 KiB)",
                              type=["json"], key="kuodra_ml_evaluation")
    if upload is None:
        st.caption("현재 검증된 ML 평가 결과가 없습니다. 임의의 예측·신뢰도 수치를 표시하지 않습니다.")
        return
    try:
        if type(upload.size) is not int or not 0 < upload.size <= MAX_ML_REPORT_BYTES:
            raise ValueError("INVALID_ML_JSON_SIZE")
        report = explain_ml_evaluation(
            parse_ml_evaluation_json(upload.getvalue()),
            expected_issuer_cik=cik, analysis_as_of=as_of,
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        st.error("ML 설명 차단: JSON 계약, 발행사·기준일, 기간 또는 출처 근거를 확인하십시오.")
        return
    st.warning("사용자 제공 ML 성능·출처 정보의 형식만 확인했습니다. "
               "실제 모델·데이터·공시와의 독립 대조는 수행하지 않았습니다.")
    st.write(report["headline"])
    st.write(report["summary"])
    if report["metric_comparison"] is not None:
        st.json({"평가 방법·표본·모델 대비 기준모델": report["metric_comparison"]})
    if report["factors"]:
        st.table([{
            "특징량": f["name"], "설명 방법": f["method"],
            "입력된 중요도": f["importance_reported"],
            "출처 ID": ", ".join(f["source_ids"]),
            "해석 제한": f["interpretation"],
        } for f in report["factors"]])
    if report["sources"]:
        st.json({"출처 URL·최초 공개일·SHA256 (인증 전)": report["sources"]})
    st.json({"주의·미검증 항목": report["caveats"],
             "model_verified": False, "source_authenticated": False,
             "ai_generated": False, "trade_signal": False})
