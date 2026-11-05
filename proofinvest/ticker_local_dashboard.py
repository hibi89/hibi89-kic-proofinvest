"""Single-ticker A/B/C decision panel from an independently replayed local workflow.

Display-only projection: caller-owned bytes never enter the view, no HTTP,
no model calls, no storage, and no inference of publisher/rights authentication.
"""
from __future__ import annotations

import re
from typing import Any

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TICKER = re.compile(r"[A-Z0-9.^_-]{1,20}\Z")
_CIK = re.compile(r"[0-9]{10}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_NUMBER = re.compile(r"-?[0-9]{1,15}(?:\.[0-9]{1,6})?\Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "kuodra.local-ticker-dashboard.v1",
        "status": "BLOCKED", "reason_code": reason,
        "network_requests": 0, "guard_executed": False,
        "ai_agent_executed": False, "trade_executed": False,
        "source_authenticated": False, "source_rights_verified": False,
        "investment_recommendation": False,
    }


def _number(value: Any) -> str | None:
    if type(value) is str and _NUMBER.fullmatch(value):
        return value
    if type(value) is int and not isinstance(value, bool) and abs(value) <= 10**15:
        return str(value)
    return None


def _slot(value: Any, *, good: tuple[str, ...], required_digest: str | None,
          digest_field: str = "input_sha256") -> bool:
    if type(value) is not dict or value.get("status") not in good:
        return False
    if any(value.get(key) is not False for key in
           ("source_authenticated", "provider_rights_verified")):
        return False
    digest = value.get(digest_field)
    return (type(required_digest) is str and _HEX.fullmatch(required_digest) is not None
            and digest == required_digest)


def summarize_local_ticker_dashboard(workflow: Any) -> dict[str, Any]:
    """Fail closed if any replay, source, rights, Guard or issuer contract differs.

    This is not an SEC attestation. Never consume raw uploaded files here.
    """
    blocked = _blocked("WORKFLOW_OR_REPORT_UNVERIFIED")
    if type(workflow) is not dict or workflow.get("schema") != "kuodra.local-ticker-workflow.v1":
        return blocked
    trace = workflow.get("tool_trace")
    if (type(trace) is not list
            or workflow.get("status") != "READY_FOR_HUMAN_REVIEW_UNVERIFIED"
            or workflow.get("mode") != "DETERMINISTIC_LOCAL_TOOLS_NOT_LLM_AGENT"
            or workflow.get("tool_calls_executed") != workflow.get("tool_budget")
            or workflow.get("tool_budget") != 7
            or len(trace) != 7
            or any(workflow.get(k) is not False for k in (
                "guard_executed", "audit_written", "human_approved",
                "trade_executed", "ai_agent_executed", "source_authenticated",
                "source_rights_verified", "official_contest_submission"))
            or workflow.get("network_requests") != 0):
        return blocked
    report, receipt, revenue, original, supplement, b = (
        workflow.get(k) for k in ("report", "receipt", "revenue",
                                   "original", "supplementary", "engine_b"))
    if any(type(x) is not dict for x in (report, receipt, revenue, original, supplement, b)):
        return blocked
    issuer, rights, limits = (report.get(k) for k in
                               ("issuer", "source_rights_ledger", "limits"))
    if any(type(x) is not dict for x in (issuer, rights, limits)):
        return blocked
    ticker, cik, accession, as_of = (issuer.get(k) for k in
                                    ("ticker", "cik", "accession", "as_of"))
    digests, original_guard, verification = (
        receipt.get("source_sha256"), original.get("guard_preview"),
        report.get("verification"))
    if any(type(x) is not dict for x in (digests, original_guard, verification)):
        return blocked
    sha = digests.get("companyfacts")
    guard = original_guard.get("decision")
    if (type(ticker) is not str or not _TICKER.fullmatch(ticker)
            or type(cik) is not str or not _CIK.fullmatch(cik)
            or type(as_of) is not str or not _DATE.fullmatch(as_of)
            or type(accession) is not str or len(accession) != 20
            or type(sha) is not str or _HEX.fullmatch(sha) is None
            or type(report.get("report_sha256")) is not str
            or _HEX.fullmatch(report["report_sha256"]) is None
            or issuer.get("ticker") != receipt.get("ticker")
            or issuer.get("cik") != receipt.get("cik")
            or issuer.get("accession") != receipt.get("selected_10k_accession")
            or issuer.get("as_of") != receipt.get("requested_as_of")
            or report.get("source_sha256") != receipt.get("source_sha256")
            or revenue.get("ticker") != ticker
            or revenue.get("issuer_cik") != cik
            or revenue.get("accession") != accession
            or revenue.get("companyfacts_sha256") != sha
            or revenue.get("status") != "REVENUE_CALCULATED_UNVERIFIED"
            or verification.get("growth_pct") != revenue.get("growth_pct")
            or original.get("companyfacts_sha256") != sha
            or report.get("guard_policy_preview") != guard
            or guard not in ("HOLD", "REJECT")
            or rights.get("status") != "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED"
            or any(rights.get(k) is not False for k in (
                "external_sharing_allowed", "commercial_reuse_allowed"))
            or any(limits.get(k) is not False for k in (
                "source_authenticated", "source_rights_verified",
                "ai_agent_executed", "guard_executed", "audit_written",
                "human_approved", "trade_executed", "official_contest_submission"))
            or limits.get("external_http_requests") != 0
            or supplement.get("source_authenticated") is not False
            or supplement.get("source_rights_verified") is not False
            or b.get("companyfacts_sha256") != sha
            or b.get("source_authenticated") is not False
            or b.get("source_rights_verified") is not False):
        return blocked
    # A self-contradictory issuer original must never produce apparently valid
    # investment metrics merely because its reported revenue happens to parse.
    if guard != "HOLD":
        return _blocked("GUARD_REJECTS_ORIGINAL_CONTEXT")
    if _number(revenue.get("growth_pct")) is None:
        return blocked
    a, c = supplement.get("engine_a"), supplement.get("engine_c")
    if type(a) is not dict or type(c) is not dict:
        return blocked
    if report.get("engine_a_status") != a.get("status") or report.get("engine_c_status") != c.get("status"):
        return blocked
    a_ok = _slot(a, good=("REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE"),
                 required_digest=report.get("engine_a_input_sha256"))
    c_ok = _slot(c, good=("OBSERVED_COMPARISON_UNVERIFIED", "INSUFFICIENT_EVIDENCE"),
                 required_digest=report.get("engine_c_input_sha256"))
    if (a.get("status") == "UNAVAILABLE" and a.get("input_sha256") is not None
            or c.get("status") == "UNAVAILABLE" and c.get("input_sha256") is not None):
        return blocked
    if a.get("status") != "UNAVAILABLE" and not a_ok:
        return blocked
    if c.get("status") != "UNAVAILABLE" and not c_ok:
        return blocked
    if c_ok and (type(c.get("peer_count")) is not int
                 or not 0 <= c["peer_count"] <= 8
                 or c.get("cohort_source_scope") != "DISJOINT_SOURCE_CLAIMS_ONLY_UNVERIFIED"):
        return _blocked("ENGINE_C_PEER_COHORT_CONTRACT_INVALID")
    if c_ok and (
            type(c.get("peer_growth_observation_count")) is not int
            or not 0 <= c["peer_growth_observation_count"] <= c["peer_count"]
            or c.get("peer_growth_sample_scope") != (
                "NO_COMPARABLE_PEER_GROWTH"
                if c["peer_growth_observation_count"] == 0 else
                "SPARSE_PEER_GROWTH_UNVERIFIED"
                if c["peer_growth_observation_count"] < 3 else
                "COMPARATIVE_PEER_GROWTH_UNVERIFIED"
            )):
        return _blocked("ENGINE_C_USABLE_PEER_SAMPLE_INVALID")
    if c_ok and c["peer_growth_observation_count"] == 0 and (
            c.get("peer_median_growth_pct") is not None
            or c.get("growth_gap_to_peer_median_pp") is not None):
        return _blocked("ENGINE_C_EMPTY_PEER_SAMPLE_HAS_MEDIAN")
    if c_ok and c["peer_growth_observation_count"] > 0 and (
            _number(c.get("peer_median_growth_pct")) is None):
        return _blocked("ENGINE_C_PEER_MEDIAN_MISSING")
    if b.get("status") not in ("REVIEWED_UNVERIFIED", "UNAVAILABLE"):
        return blocked
    result = {
        **_blocked(""), "status": "LOCAL_SOURCE_REPLAYED_UNVERIFIED",
        "reason_code": "LOCAL_ORIGINAL_AND_LICENSE_UNAUTHENTICATED",
        "ticker": ticker, "cik": cik, "as_of": as_of,
        "report_sha256": report["report_sha256"], "guard_policy": "HOLD",
        "revenue_growth_pct": _number(revenue["growth_pct"]),
        "engine_a": {
            "status": a["status"],
            "security_return_pct": _number(a.get("security_return_pct")) if a_ok else None,
            "benchmark_return_pct": _number(a.get("benchmark_return_pct")) if a_ok else None,
            "beta": _number(a.get("beta")) if a_ok else None,
            "r_squared": _number(a.get("r_squared")) if a_ok else None,
        },
        "engine_b": {
            "status": b["status"],
            "cash_to_net_income_pct": _number(b.get("cash_to_net_income_pct"))
            if b["status"] == "REVIEWED_UNVERIFIED" else None,
        },
        "engine_c": {
            "status": c["status"],
            "peer_count": c["peer_count"] if c_ok else None,
            "peer_growth_observation_count": c["peer_growth_observation_count"] if c_ok else None,
            "peer_growth_sample_scope": c["peer_growth_sample_scope"] if c_ok else None,
            "peer_median_growth_pct": _number(c.get("peer_median_growth_pct")) if c_ok else None,
            "growth_gap_to_industry_pp": _number(c.get("growth_gap_to_industry_pp")) if c_ok else None,
        },
    }
    return result


def render_local_ticker_dashboard(st: Any, workflow: Any) -> None:
    """Present only validated scalars, never HTML, user strings or original bytes."""
    result = summarize_local_ticker_dashboard(workflow)
    st.subheader("KUODRA · A/B/C 통합 분석 대시보드 (로컬 근거, 미인증)")
    if result["status"] == "BLOCKED":
        st.warning("근거·재검증·Guard 계약을 충족하지 못해 통합 지표를 표시하지 않습니다.")
        st.code(result["reason_code"], language="text")
        return
    st.metric("분석 종목 / 기준일", result["ticker"] + " / " + result["as_of"])
    st.metric("연매출 성장률 (로컬 재검산 · 미인증)", result["revenue_growth_pct"] + "%")
    st.metric("Guard 정책 (실행 아님)", result["guard_policy"])
    a, b, c = (result[k] for k in ("engine_a", "engine_b", "engine_c"))
    st.subheader("Engine A · 가격/벤치마크 설명적 비교")
    st.metric("주가 수익률 (미인증)", a["security_return_pct"] + "%" if a["security_return_pct"] is not None else "자료 없음")
    st.metric("지수 수익률 (미인증)", a["benchmark_return_pct"] + "%" if a["benchmark_return_pct"] is not None else "자료 없음")
    st.metric("OLS 베타 (인과관계 아님)", a["beta"] if a["beta"] is not None else "자료 없음")
    st.subheader("Engine B · 이익/영업현금 흐름")
    st.metric("영업현금/순이익 (미인증)", b["cash_to_net_income_pct"] + "%" if b["cash_to_net_income_pct"] is not None else "자료 없음")
    st.subheader("Engine C · 동종기업·산업 성장 비교")
    peers = c["peer_count"]
    usable = c["peer_growth_observation_count"]
    st.metric("입력 동종기업 표본 수", str(peers) if peers is not None else "자료 없음")
    st.metric("성장률 계산 가능한 동종기업 수", str(usable) if usable is not None else "자료 없음")
    if usable is not None and usable < 3:
        st.warning("동종기업 " + str(peers) + "개 중 성장률 계산 가능한 표본이 "
                   + str(usable) + "개입니다. 업종 대표값·투자 판단으로 사용할 수 없습니다.")
    st.metric("동종기업 성장률 중앙값", c["peer_median_growth_pct"] + "%" if c["peer_median_growth_pct"] is not None else "자료 없음")
    st.metric("산업 대비 성장률 격차", c["growth_gap_to_industry_pp"] + "pp" if c["growth_gap_to_industry_pp"] is not None else "자료 없음")
    st.json({"engine_a": a["status"], "engine_b": b["status"],
             "engine_c": c["status"], "report_sha256": result["report_sha256"],
             "source_authenticated": False, "source_rights_verified": False,
             "ai_agent_executed": False, "trade_executed": False})
    st.warning("로컬 업로드 데이터의 발행기관 진위·재배포 권리·시장 데이터 시점은 인증되지 않았습니다. "
               "수치는 설명용이며 매매·투자 승인 또는 자동 AI 실행이 아닙니다.")


def analyze_local_ticker_dashboard(
    *, ticker: str, as_of: str, sources: dict[str, bytes],
    market_json: bytes | None = None, industry_json: bytes | None = None,
) -> dict[str, Any]:
    """Single-call local A/B/C dashboard backed by actual source-byte replay.

    This is a user-facing orchestration entrypoint, not an authenticated
    provider, investment recommendation, model agent or trading execution.
    Never return the raw source bytes or a partial unverified report.
    """
    from .ticker_local_workflow import run_local_ticker_workflow

    workflow = run_local_ticker_workflow(
        ticker=ticker, as_of=as_of, sources=sources,
        market_json=market_json, industry_json=industry_json,
    )
    if workflow.get("status") != "READY_FOR_HUMAN_REVIEW_UNVERIFIED":
        return _blocked(workflow.get("reason_code", "WORKFLOW_BLOCKED"))
    return summarize_local_ticker_dashboard(workflow)
