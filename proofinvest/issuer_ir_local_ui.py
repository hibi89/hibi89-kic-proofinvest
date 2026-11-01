"""P107 local-only presentation of P106 historical issuer-IR arithmetic.

No SEC access, market/peer API, uploaded source, cache, SQLite, LLM or trade.
Default synthetic and existing SEC flows remain separate and unchanged.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .issuer_ir_replay import ISSUER_URL, replay
from .kuodra_local_workspace_ui import local_workspace_enabled

_CHOICES = {
    "114.20% — 과거 IR 수치와 산술 일치": "114.20",
    "140% — 근거 수치와 충돌": "140",
    "주장 없음 — 판정 보류": "",
}
_BLOCKED = ("source_authenticated", "sec_accessed", "rights_to_redistribute_verified",
            "original_filing_verified", "full_engine_abc_executed", "ai_agent_executed",
            "trade_executed", "risk_of_misconduct_concluded")


def build_manual_ir_report(claim_pct: str = "114.20") -> dict[str, Any]:
    """Return source-bounded offline JSON; never upgrade manual math to SEC proof."""
    receipt = replay(claim_pct)
    if (type(receipt) is not dict
            or receipt.get("schema") != "kuodra.issuer-ir-replay.v1"
            or receipt.get("mode") != "HISTORICAL_MANUAL_ISSUER_IR_OFFLINE"
            or receipt.get("ticker") != "NVDA"
            or receipt.get("fiscal_year") != "FY2025"
            or receipt.get("source_url") != ISSUER_URL
            or receipt.get("source_kind") != "ISSUER_IR_PRESS_RELEASE_UNAUDITED"
            or receipt.get("source_publication_date") != "2025-02-26"
            or receipt.get("unit") != "USD_MILLIONS"
            or receipt.get("external_network_requests") != 0
            or receipt.get("guard_decision") != "HOLD"
            or any(receipt.get(flag) is not False for flag in _BLOCKED)
            or receipt.get("arithmetic_state") not in ("verified", "conflict", "unavailable")):
        raise ValueError("Untrusted historical IR report contract")
    metrics = receipt.get("metrics")
    if (type(metrics) is not dict or set(metrics) != {
            "fy2025_revenue", "fy2024_revenue", "revenue_yoy_pct",
            "fy2025_operating_cash_flow", "fy2025_net_income",
            "fy2025_cash_conversion_pct", "fy2024_cash_conversion_pct",
            "accounts_receivable_yoy_pct"
        } or any(type(v) is not str or re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", v) is None
                 for v in metrics.values())
            or type(receipt.get("evidence_sha256")) is not str
            or re.fullmatch(r"[0-9a-f]{64}", receipt["evidence_sha256"]) is None):
        raise ValueError("Invalid issuer facts, hash or arithmetic")
    # "unavailable" can still carry historic arithmetic, but is never a
    # successful claim verification. No risk rating or automated conclusion.
    return {
        "schema": "kuodra.historical-issuer-ir-dashboard.v1",
        "scope": "HISTORICAL_FY2025_MANUAL_ISSUER_IR_NOT_LIVE_SEC",
        "issuer": {"ticker": "NVDA", "name": "NVIDIA Corporation"},
        "source": {
            "publisher": "NVIDIA Corporation Investor Relations",
            "url": ISSUER_URL,
            "published_at": "2025-02-26",
            "fiscal_ends": {"FY2025": "2025-01-26", "FY2024": "2024-01-28"},
            "basis": "GAAP_CONSOLIDATED_CONDENSED_UNAUDITED",
            "unit": "USD_MILLIONS",
            "evidence_sha256": receipt["evidence_sha256"],
            "origin_authenticated": False,
            "redistribution_licensed": False,
        },
        "verification": {
            "state": receipt["arithmetic_state"],
            "claim_pct": receipt["claim_pct"],
            "reason": receipt["reason"],
            "scope": "MANUAL_TRANSCRIPTION_ARITHMETIC_ONLY",
        },
        "metrics": metrics,
        "engines": {
            "A": "UNAVAILABLE_NO_POINT_IN_TIME_PRICE_BENCHMARK",
            "B": "PARTIAL_MANUAL_REVENUE_CASH_RECEIVABLES_ONLY",
            "C": "UNAVAILABLE_NO_LICENSED_PEERS_INDUSTRY",
        },
        "guard": {"decision": "HOLD", "approval_granted": False},
        "execution": {
            "network_requests": 0, "sec_accessed": False, "llm_called": False,
            "db_written": False, "trade_executed": False,
            "full_abc_completed": False,
        },
    }


def render_nvda_ir_local(st) -> None:
    """Show a separate read-only *local* reference without touching SEC fetch UI."""
    if not local_workspace_enabled(st):
        st.error("로컬 전용 IR 보기가 비활성화되었습니다. 공개 서버에서는 표시하지 않습니다.")
        return
    st.title("KUODRA — NVIDIA 과거 IR 실수치 검산")
    st.warning(
        "HISTORICAL_MANUAL_ISSUER_IR_OFFLINE · NVIDIA FY2025/FY2024 발행사 발표 수동 전사. "
        "SEC 403 이후 SEC 재요청 0회. 최신 실적·원문 인증·전체 A/B/C 완료·AI 투자 권고가 아닙니다."
    )
    chosen = st.selectbox("FY2025 매출 성장률 주장", list(_CHOICES),
                          key="p107_ir_claim")
    try:
        report = build_manual_ir_report(_CHOICES[chosen])
    except (ValueError, OSError, TypeError, KeyError, ArithmeticError):
        st.error("IR 수동기록 또는 검증 계약이 일치하지 않습니다. 수치 표시·내보내기 차단.")
        return
    m = report["metrics"]
    st.markdown("[NVIDIA 발행사 IR 2025-02-26 원문 링크](" + ISSUER_URL + ")")
    st.caption("회계연도 FY2025 종료 2025-01-26 · FY2024 종료 2024-01-28 · "
               "GAAP 연결 요약표(미감사) · 단위 백만 USD · 외부 원본 독립 인증/재배포 권리 미확인")
    a, b, c = st.columns(3)
    a.metric("FY2025 매출 증가율 (수동 검산)", m["revenue_yoy_pct"] + "%")
    b.metric("FY2025 영업현금흐름 / 순이익", m["fy2025_cash_conversion_pct"] + "%")
    c.metric("Guard 결정 (실거래 없음)", "HOLD")
    st.subheader("FY2025/FY2024 재무 숫자 — 수동 전사 근거")
    st.dataframe([
        {"지표": "매출 (백만 USD)", "FY2025": m["fy2025_revenue"],
         "FY2024": m["fy2024_revenue"]},
        {"지표": "영업현금흐름 (백만 USD)",
         "FY2025": m["fy2025_operating_cash_flow"],
         "FY2024": "28,090 (공식 IR, 참조값)"},
        {"지표": "순이익 (백만 USD)", "FY2025": m["fy2025_net_income"],
         "FY2024": "29,760 (공식 IR, 참조값)"},
    ], use_container_width=True, hide_index=True)
    state = report["verification"]["state"]
    if state == "verified":
        st.info("산술 일치 — 입력 주장이 수동 전사된 과거 발행사 숫자와 일치합니다. "
                "실제 출처 인증이나 투자 적합성 판정은 아닙니다.")
    elif state == "conflict":
        st.error("수치 충돌 — 주장 성장률이 과거 수동 기록 계산과 다릅니다. Guard HOLD 유지.")
    else:
        st.warning("주장 미확정 — 수치 비교 판정 보류. Guard HOLD 유지.")
    st.subheader("Engine A/B/C · 검증 가능 범위")
    st.dataframe([
        {"엔진": "A 시장/주가", "상태": "UNAVAILABLE", "사유": "동일 시점 주가·시장지수 근거 없음"},
        {"엔진": "B 재무검증", "상태": "PARTIAL", "사유": "매출·현금흐름·채권 수치 산술만"},
        {"엔진": "C 산업/동종", "상태": "UNAVAILABLE", "사유": "권리 검토된 동종기업·산업 입력 없음"},
        {"엔진": "Guard", "상태": "HOLD", "사유": "인증 원문·전체 근거·사람 승인 없음"},
    ], use_container_width=True, hide_index=True)
    st.caption("보고서 해시: " + report["source"]["evidence_sha256"] +
               " · 로컬 파일 바이트 무결성만 의미 · SEC 인증 아님 · DB/외부 API/LLM/매매 0회")
    st.download_button(
        "과거 IR 검산 보고서 JSON 다운로드 (미인증)",
        data=json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True,
                        allow_nan=False),
        file_name="KUODRA_NVDA_FY2025_IR_MANUAL_UNAUTHENTICATED.json",
        mime="application/json", key="p107_ir_json",
    )
