"""P229: real issuer → NDX vendor-use rights gap, native offline review.

A bounded issuer-origin historical source can prove the issuer observation
but never confer Nasdaq-100 rights, data-provider account entitlement, model
permissions, source identity for stock/NDX responses, or public-display rights.

This is a human license procurement checklist. It grants NOTHING and never
contacts a vendor, requests payment, stores credentials or executes trades.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .provider_rights_preflight import evaluate_provider
from .real_issuer_ticker_review import review_supported_real_ticker

_SCHEMA = "kuodra.p229-real-issuer-ndx-license-readiness.v1"
_STATUS = "ISSUER_BOUND_NDX_LICENSE_GAPS_HUMAN_ONLY"
_AS_OF = "2026-11-05"
_PROVIDERS = ("massive", "twelve_data", "fred", "nasdaq_gids", "nasdaq_data_link")
_USES = ("internal_research", "contest_judge_demo", "public_dashboard", "commercial_product")


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _blocked(code: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": code,
        "market_vendor_authenticated": False,
        "market_index_ndx_identified_by_provider": False,
        "licensed_stock_and_ndx_available": False,
        "account_entitlement_verified": False,
        "data_use_rights_verified": False,
        "model_use_rights_verified": False,
        "display_rights_verified": False,
        "owner_network_approval_received": False,
        "request_execution_authorized": False,
        "full_abc_complete": False, "guard_policy_preview": "HOLD",
        "external_network_requests": 0, "paid_services_activated": False,
        "trade_executed": False,
    }


def build_issuer_ndx_license_gap(
    *, ticker: Any, provider: Any, intended_use: Any,
    as_of: Any = _AS_OF,
) -> dict[str, Any]:
    """Prepare source-bound, no-credentials vendor/rights evidence request.

    Public supplier coverage statements are NOT authenticated account rights.
    No caller-provided 'approved' flag can upgrade a license claim.
    """
    if (type(ticker) is not str or ticker not in ("NVDA", "DELL")
            or type(provider) is not str or provider not in _PROVIDERS
            or type(intended_use) is not str or intended_use not in _USES
            or type(as_of) is not str or as_of != _AS_OF):
        return _blocked("ISSUER_VENDOR_USE_OR_VINTAGE_UNSUPPORTED")
    issuer = review_supported_real_ticker(ticker, as_of=as_of)
    if (issuer.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
            or issuer.get("ticker") != ticker
            or issuer.get("review_as_of") != as_of
            or issuer.get("publisher_original_observed") is not True
            or issuer.get("source_authenticated_by_sec") is not False
            or issuer.get("source_rights_verified") is not False
            or issuer.get("market_ndx_peer_licensed") is not False
            or issuer.get("guard_policy_preview") != "HOLD"
            or issuer.get("trade_executed") is not False
            or type(issuer.get("cik")) is not str
            or type(issuer.get("source_sha256")) is not str
            or len(issuer["source_sha256"]) != 64):
        return _blocked("FIRST_PARTY_ISSUER_ORIGIN_CHAIN_INVALID")
    try:
        rights = evaluate_provider(provider=provider, intended_use=intended_use)
        if (type(rights) is not dict
                or rights.get("schema") != "kuodra.provider-rights-preflight.v1"
                or rights.get("status") !=
                   "BLOCKED_VENDOR_RIGHTS_AND_OWNER_APPROVAL_REQUIRED"
                or rights.get("provider") != provider
                or rights.get("intended_use") != intended_use
                or rights.get("request_execution_authorized") is not False
                or rights.get("account_entitlement_verified") is not False
                or rights.get("ndx_identity_independently_verified") is not False
                or rights.get("data_use_permission_verified") is not False
                or rights.get("ai_system_use_rights_verified") is not False
                or rights.get("derived_analytics_display_permission_verified") is not False
                or rights.get("redistribution_permission_verified") is not False
                or rights.get("owner_network_approval_received") is not False
                or rights.get("trade_executed") is not False
                or rights.get("network_requests_executed") != 0
                or not isinstance(rights.get("license_blocker_codes"), list)
                or not rights["license_blocker_codes"]
                or type(rights.get("official_terms_url")) is not str
                or not rights["official_terms_url"].startswith("https://")
                or type(rights.get("required_next_evidence")) is not str):
            return _blocked("PROVIDER_RIGHTS_ORIGIN_AND_SCOPE_INVALID")
        out = {
            **_blocked("PROVIDER_WRITTEN_RIGHTS_AND_OWNER_APPROVAL_MISSING"),
            "status": _STATUS,
            "ticker": ticker, "issuer_cik": issuer["cik"],
            "issuer_as_of": as_of,
            "historical_issuer_original_sha256": issuer["source_sha256"],
            "historical_issuer_source_url": issuer["source_url"],
            "historical_issuer_original_publisher_observed": True,
            "issuer_sec_edgar_original_verified": False,
            "candidate_provider": provider, "intended_use": intended_use,
            "benchmark": "NASDAQ_100", "instrument": "NDX",
            "catalog_coverage_status": rights["published_ndx_coverage"],
            "published_information_url": rights["published_information_url"],
            "vendor_terms_url": rights["official_terms_url"],
            "vendor_secondary_url": rights["official_secondary_url"],
            "published_terms_as_of": rights["public_terms_reviewed_kst"],
            "blocking_legal_scope_codes": rights["license_blocker_codes"],
            "evidence_needed_before_first_vendor_request":
                rights["required_next_evidence"],
            "stock_symbol_coverage_verified": False,
            "stock_corporate_actions_adjustments_verified": False,
            "ndx_provider_original_bytes_verified": False,
            "exact_source_vintage_verified": False,
            "reuse_rights_verified": False,
            "unkeyed_digest_not_entitlement": True,
        }
        if len(_canonical(out)) > 4096:
            return _blocked("LICENSE_GAP_PACKET_TOO_LARGE")
        out["gap_packet_sha256"] = sha256(_canonical(out)).hexdigest()
        return out
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return _blocked("PROVIDER_RIGHTS_PREFLIGHT_FAILED_CLOSED")


def replay_issuer_ndx_license_gap(report: Any) -> bool:
    """Reject modified reports even with a recomputed unkeyed digest."""
    if (type(report) is not dict or report.get("schema") != _SCHEMA
            or report.get("status") != _STATUS):
        return False
    try:
        return report == build_issuer_ndx_license_gap(
            ticker=report["ticker"], provider=report["candidate_provider"],
            intended_use=report["intended_use"],
            as_of=report["issuer_as_of"],
        )
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
        return False


def render_issuer_ndx_license_gap_panel(st, *, ticker: str) -> None:
    """Real ticker → vendor rights decision, one click, no I/O or keys."""
    st.subheader("Engine A · NDX 공급자 사용권 사전검증 (외부 요청 0)")
    st.caption(
        "현재 발행사 원문은 과거 자료로만 검증됐습니다. 공급자 목록·요금제·"
        "공식 안내는 계정의 이용권이나 진짜 NDX 데이터 취득을 보증하지 않습니다. "
        "API 키나 계약서를 업로드하지 마세요."
    )
    with st.form("p229_real_issuer_ndx_rights_form"):
        provider = st.selectbox(
            "NDX 데이터 공급자 후보", _PROVIDERS,
            key="p229_ndx_vendor",
        )
        intended_use = st.selectbox(
            "분석 자료 활용 목적", _USES,
            key="p229_ndx_use",
        )
        submitted = st.form_submit_button(
            "NDX 공급자 사용권 사전점검 (외부 요청 0)",
            key="p229_ndx_rights_submit",
        )
    if not submitted:
        return
    out = build_issuer_ndx_license_gap(
        ticker=ticker, provider=provider, intended_use=intended_use)
    if out["status"] != _STATUS or not replay_issuer_ndx_license_gap(out):
        st.warning("발행사 증거와 공급자 사용권 점검이 일치하지 않아 차단했습니다.")
        return
    st.warning("NDX 공급자 실계정·이용권 미검증 — 데이터 조회·공개·AI 학습/추론 승인 불가.")
    st.json({
        "provider": out["candidate_provider"], "intended_use": out["intended_use"],
        "requires": out["blocking_legal_scope_codes"],
        "next_proof": out["evidence_needed_before_first_vendor_request"],
        "request_execution_authorized": False,
        "account_entitlement_verified": False, "data_use_rights_verified": False,
        "model_use_rights_verified": False, "guard_policy_preview": "HOLD",
    })
    st.markdown(
        f'[공급자 공식 약관]({out["vendor_terms_url"]}) · '
        f'[추가 공식 안내]({out["vendor_secondary_url"]})'
    )
    st.download_button(
        "NDX 출처·계정 사용권 미검증 확인서 JSON",
        data=_canonical(out),
        file_name="kuodra-ndx-license-gaps-UNVERIFIED.json",
        mime="application/json", key="p229_ndx_gap_export",
        on_click="ignore",
    )
