"""P225: real-publisher A/B/C guarded fact-review handoff, offline only.

This is a deterministic, cross-source reviewer-ready explanation, **not**
an LLM run or legal approval to send these values to a model. Numeric matching
is only historical source/derived math integrity, not market origin/licensing.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from typing import Any

from .real_issuer_abc_local_review import replay_partial_source_bound_abc
from .real_issuer_ticker_review import review_supported_real_ticker

_SCHEMA = "kuodra.p225-real-publisher-abc-fact-review.v1"
_STATUS = "LOCAL_A_B_C_CLAIM_REVIEW_FOR_HUMAN_ONLY"
_ISSUER_NOTE = (
    "NVIDIA 발행사 원문 수치의 과거 산술 대조입니다. 투자 추천이나 "
    "회계부정 확정이 아니며 SEC EDGAR 원본 동일성과 상업·AI 처리권은 미확인입니다."
)
_MARKET_NOTE = (
    "주가·NDX 데이터는 사용자가 올린 JSON의 계산값입니다. "
    "제공자·시세 원본·이용권이 인증되지 않아 시장 우위, 베타 인과관계, "
    "과대평가 및 투자 신호 판단은 불가합니다."
)
_PEER_NOTE = (
    "AMD와 Intel의 과거 공식 10-K·실적발표 수치 비교입니다. "
    "두 회사의 원문 바이트 인증·재사용권이 없고 NVIDIA와 결산일이 29일 다르며 "
    "Intel Altera 연결 범위가 달라 업종 순위·예측을 산출할 수 없습니다."
)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason": reason,
        "guard_policy_preview": "HOLD", "ai_agent_executed": False,
        "source_rights_verified": False, "market_rights_verified": False,
        "external_sharing_allowed": False, "full_abc_complete": False,
        "investment_recommendation": False, "trade_executed": False,
        "network_requests": 0,
    }


def build_source_factual_abc_brief(abc: Any) -> dict[str, Any]:
    """Prepare a verified-exact local narrative plus evidence references.

    VERIFIABLE_MATH means numerical consistency against fixed historical
    issuer facts; peer source text is NOT SHA verified and rights are false.
    Market conclusions are UNAVAILABLE, not fabricated from local fixtures.
    """
    if type(abc) is not dict or not replay_partial_source_bound_abc(abc):
        return _blocked("SOURCE_LINKED_ABC_REPLAY_REQUIRED")
    try:
        ab, c = abc["engine_ab_partial"], abc["engine_c_partial"]
        publisher = review_supported_real_ticker("NVDA", as_of="2026-11-05")
        rows = c["source_revenue_growth_observations_not_sector_rank"]
        if (abc["ticker"] != "NVDA" or abc["as_of"] != "2026-11-05"
                or publisher["source_sha256"] != abc["source_linked_issuer_sha256"]
                or ab["engine_b"]["issuer_financial_source_sha256"] !=
                   publisher["source_sha256"]
                or c["issuer_source_sha256"] != publisher["source_sha256"]
                or c["peer_count"] != 2
                or [r["ticker"] for r in rows] != ["NVDA", "AMD", "INTC"]
                or rows[0]["actual_source_sha256"] != publisher["source_sha256"]
                or rows[1]["actual_source_sha256"] is not None
                or rows[2]["actual_source_sha256"] is not None
                or c["fiscal_end_offsets_days"] != {"AMD": 29, "INTC": 29}
                or abc["guard_policy_preview"] != "HOLD"
                or abc["full_abc_complete"] is not False
                or abc["market_rights_verified"] is not False
                or abc["peer_rights_verified"] is not False
                or abc["source_provider_authenticated"] is not False
                or abc["ai_agent_executed"] is not False
                or abc["trade_executed"] is not False):
            return _blocked("GAAP_OR_MARKET_OR_PEER_LINEAGE_CONFLICT")
        market=ab["engine_a"]
        if market["status"] not in ("REPORTED_UNVERIFIED",
                                    "INSUFFICIENT_MARKET_VARIANCE"):
            return _blocked("MARKET_MATH_STATUS_INVALID")
        source_links = [
            {"type":"ISSUER_PUBLISHER", "ticker":"NVDA",
             "url":publisher["source_url"],
             "source_sha256":publisher["source_sha256"],
             "original_byte_verified_by_publisher_test":True,
             "sec_edgar_original_identical":False},
            {"type":"PEER_10K_PUBLIC_MANUAL", "ticker":"AMD",
             "url":rows[1]["source_url"], "source_sha256":None,
             "original_byte_verified_by_publisher_test":False,
             "sec_edgar_original_identical":False},
            {"type":"PEER_10K_PUBLIC_MANUAL", "ticker":"INTC",
             "url":rows[2]["source_url"], "source_sha256":None,
             "original_byte_verified_by_publisher_test":False,
             "sec_edgar_original_identical":False},
        ]
        claims = [
            {"engine":"A", "claim_id":"STOCK_VS_NDX_LOCAL_REVIEW",
             "verification":"UNAVAILABLE_PROVIDER_ORIGIN_AND_RIGHTS",
             "value":None, "unit":"NONE",
             "source_type":"OPERATOR_UPLOADED_MARKET_UNAUTHENTICATED",
             "text":_MARKET_NOTE},
            {"engine":"B", "claim_id":"NVDA_GAAP_REVENUE_GROWTH",
             "verification":"VERIFIED_HISTORICAL_NUMERIC_MATCH_ONLY",
             "value":ab["engine_b"]["revenue_growth_pct"],"unit":"PCT",
             "source_type":"ISSUER_PUBLISHER","text":(
                "NVIDIA 과거 공시의 연매출 증가율 산술검산: "+
                ab["engine_b"]["revenue_growth_pct"]+"%. "+_ISSUER_NOTE)},
            {"engine":"B", "claim_id":"NVDA_CFO_TO_NET_INCOME",
             "verification":"VERIFIED_HISTORICAL_NUMERIC_MATCH_ONLY",
             "value":ab["engine_b"]["cashflow_to_net_income_ratio"],
             "unit":"RATIO","source_type":"ISSUER_PUBLISHER",
             "text":("NVIDIA 과거 영업현금흐름/순이익 비율 산술검산: "+
                     ab["engine_b"]["cashflow_to_net_income_ratio"]+". "+_ISSUER_NOTE)},
            {"engine":"C", "claim_id":"AMD_YEARLY_REVENUE_GROWTH",
             "verification":"PUBLIC_TEXT_NUMERIC_MATCH_RAW_UNVERIFIED",
             "value":rows[1]["revenue_growth_pct"],"unit":"PCT",
             "source_type":"PEER_10K_PUBLIC_MANUAL",
             "text":("AMD 공시상 과거 매출 증가율 산술 대조: "+
                     rows[1]["revenue_growth_pct"]+"%. "+_PEER_NOTE)},
            {"engine":"C", "claim_id":"INTC_YEARLY_REVENUE_GROWTH",
             "verification":"PUBLIC_TEXT_NUMERIC_MATCH_RAW_UNVERIFIED",
             "value":rows[2]["revenue_growth_pct"],"unit":"PCT",
             "source_type":"PEER_10K_PUBLIC_MANUAL",
             "text":("Intel 공시상 과거 매출 증가율 산술 대조: "+
                     rows[2]["revenue_growth_pct"]+"%. "+_PEER_NOTE)},
        ]
        if (claims[1]["value"] != "65.47" or claims[2]["value"] != "0.8555"
                or claims[3]["value"] != "34.34"
                or claims[4]["value"] != "-0.47"
                or c["nvda_minus_amd_growth_pp"] != "31.14"
                or c["nvda_minus_intc_growth_pp"] != "65.94"):
            return _blocked("SOURCE_PINNED_FACTS_NOT_RECONCILED")
        report = {
            "schema": _SCHEMA, "status": _STATUS,
            "ticker":"NVDA", "reviewed_as_of":"2026-11-05",
            "linked_abc_digest": abc["derived_sha256"],
            "publisher_source_sha256": publisher["source_sha256"],
            "uploaded_market_source_sha256": {
                "stock":abc["stock_uploaded_sha256"],
                "ndx":abc["ndx_uploaded_sha256"],
            },
            "review_outcomes": ["UNAVAILABLE","VERIFIED","VERIFIED","VERIFIED","VERIFIED"],
            "claims":claims, "source_links":source_links,
            "market_source_authenticated":False, "market_rights_verified":False,
            "peer_raw_sources_verified":False, "source_rights_verified":False,
            "sec_edgar_original_identical":False,
            "legal_model_use_approved":False, "llm_invoked":False,
            "ai_agent_executed":False, "guard_policy_preview":"HOLD",
            "guard_executed":False, "full_abc_complete":False,
            "trade_executed":False, "investment_recommendation":False,
            "external_sharing_allowed":False, "network_requests":0,
            "review_mode":"DETERMINISTIC_NOT_AI_OR_INVESTMENT_ADVICE",
            "integrity_scope":"UNKEYED_DERIVED_REPLAY_ONLY",
        }
        raw=_canonical(report)
        if len(raw)>16384:
            return _blocked("REDACTED_FACT_BRIEF_TOO_LARGE")
        report["brief_sha256"]=sha256(raw).hexdigest()
        return report
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
        return _blocked("MISSING_OR_UNSAFE_SOURCE_FACTS")


def replay_source_factual_abc_brief(report: Any, abc: Any) -> bool:
    if type(report) is not dict or type(abc) is not dict:
        return False
    try:
        if report.get("status") != _STATUS:
            return False
        expected=build_source_factual_abc_brief(abc)
        return expected==report
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
        return False


def source_factual_brief_html(report: Any, abc: Any) -> bytes:
    """Standalone *static* UTF-8 HTML with escaped, whitelisted source text."""
    if not replay_source_factual_abc_brief(report,abc):
        raise ValueError("UNTRUSTED_CLAIM_REVIEW_OR_PROVENANCE")
    if any(link["url"].split(":")[0] != "https" for link in report["source_links"]):
        raise ValueError("NON_HTTPS_SOURCE_LINK")
    cells=[]
    for claim in report["claims"]:
        cells.append("<tr><td>"+escape(claim["engine"])+"</td><td>"+
                     escape(claim["claim_id"])+"</td><td>"+
                     escape(claim["verification"])+"</td><td>"+
                     escape(claim["text"])+"</td></tr>")
    links=[]
    for ref in report["source_links"]:
        url=escape(ref["url"],quote=True)
        links.append("<li>"+escape(ref["ticker"])+
                     ": <a rel=\"noopener noreferrer\" href=\""+url+"\">"+
                     escape(ref["type"])+"</a></li>")
    html=(
        "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>KUODRA 제한 출처 검산 보고서 · HOLD</title>"
        "<style>body{font:16px/1.65 system-ui,sans-serif;max-width:900px;"
        "margin:2rem auto;padding:0 1rem;color:#182334}h1{font-size:1.6rem}"
        "table{border-collapse:collapse;width:100%}td,th{padding:.6rem;"
        "border:1px solid #b7c2cd;vertical-align:top}thead{background:#edf3f6}"
        ".notice{padding:.8rem;border:1px solid #556574}code{overflow-wrap:anywhere}</style>"
        "</head><body><h1>KUODRA · NVIDIA 실제 발행사 A/B/C 제한 사실검산</h1>"
        "<p class=\"notice\"><strong>HOLD · 개인 로컬 검토 전용</strong>."
        " 본 내용은 AI 모델 분석이 아니며, 시장가격·동종기업의 출처/이용권과 "
        "SEC 원본 바이트 동일성은 검증되지 않았습니다. "
        "투자추천·매매·외부 배포 불가.</p>"
        "<p>기준일 "+escape(report["reviewed_as_of"])+
        " · 연결 A/B/C 체크섬 <code>"+escape(report["linked_abc_digest"])+
        "</code></p><table><thead><tr><th>엔진</th><th>항목</th><th>검증 경계"
        "</th><th>근거 요약</th></tr></thead><tbody>"+
        "".join(cells)+"</tbody></table><h2>출처(권한 미확인)</h2><ul>"+
        "".join(links)+"</ul><p>발행사 SHA-256: <code>"+
        escape(report["publisher_source_sha256"])+
        "</code></p><p>시장 파일 SHA-256(원본값 불포함): <code>"+
        escape(report["uploaded_market_source_sha256"]["stock"])+
        "</code> / <code>"+
        escape(report["uploaded_market_source_sha256"]["ndx"])+
        "</code></p><p>변조탐지용 비밀키 없는 SHA-256: <code>"+
        escape(report["brief_sha256"])+
        "</code> · 인증/라이선스 아님.</p></body></html>"
    )
    raw=html.encode("utf-8")
    if len(raw)>32768:
        raise ValueError("STATIC_REDACTED_HTML_TOO_LARGE")
    return raw
