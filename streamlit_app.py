"""ProofInvest local-only synthetic Streamlit UI; no live data or uploads.

To use stored mode first run:
  python -m proofinvest.snapshot_store --save
then:
  python -m streamlit run streamlit_app.py
"""
from pathlib import Path

from proofinvest.offline_view import load_synthetic_snapshot
from proofinvest.snapshot_store import _fixture_digest, read_synthetic_snapshot_with_provenance

_SOURCE_SYNTHETIC = "합성 데이터 시연"
_SOURCE_MANUAL = "삼성전자 공개 재무제표 수동검산 (2024/2023)"
_SOURCE_SEC_CURATED = "Apple SEC 10-K 수동 발췌 — 오프라인 검산 (2025/2024)"
_SOURCE_SEC_LIVE = "SEC 공식 CompanyConcept 조회 — 명시적 1회 실행"

_DIRECT = "합성 fixture 직접 계산"
_STORED = "저장된 결과 재조회 (재계산 없음)"


def _render_manual_case(st) -> None:
    """Show a pinned manual historical statement example, never a live API result."""
    st.warning(
        "MANUAL_PRIMARY_SOURCE_VERIFICATION · 삼성전자 2024/2023 매출액 수동 전사 검산. "
        "현재 DART 직접 열람·OpenDART API·PDF 원문 재인증·AI Agent 실행 없음. "
        "투자 권고나 최신 실적 분석이 아닙니다."
    )
    claims = {
        "16.20% — 기록과 일치": "16.20",
        "30% — 불일치 사례": "30",
        "주장 없음 — 판정 보류": "",
    }
    choice = st.selectbox("검증할 성장률 주장", list(claims))
    try:
        # Synthetic recovery archives deliberately exclude issuer/source modules.
        # Import the real-issuer path only when the full local repo offers it.
        from proofinvest.manual_case_demo import run_manual_case
        result = run_manual_case(claims[choice])
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("수동 검증 기록이 없거나 변경되었습니다. 산출 결과를 표시하지 않습니다.")
        return
    verification = result["verification"]
    st.info(
        "출처: 삼성전자 공식 IR 2024 연결재무제표 (게시 2025-02-18) · "
        "과거 수동 검수 기록만 재사용; 현재 원문 열람·자동 추출하지 않음"
    )
    st.markdown(f"[발행기관 IR 게시 페이지]({result['issuer_ir_listing']})")
    a, b, c = st.columns(3)
    a.metric("보고 연도", str(verification["fiscal_year"]))
    b.metric("매출 성장률(수동기록 계산)", (verification["computed_pct"] or "계산 불가") + ("%"
             if verification["computed_pct"] is not None else ""))
    c.metric("외부 원문 독립 인증", "미인증")

    state = verification["state"]
    if state == "verified":
        st.success("일치 — 수동으로 기록한 매출 수치의 산술 검산 결과입니다. 원문 진위 인증이 아닙니다.")
    elif state == "conflict":
        st.error("불일치 — 주장과 수동기록 재계산 결과의 차이가 허용범위를 초과했습니다.")
    else:
        st.warning("검증 보류 — 유효한 성장률 주장이 없어 판정하지 않았습니다.")

    research = result["research"]
    st.subheader("Research → Verification → Risk")
    st.dataframe(
        [
            {"단계": "Research", "판정": research["status"],
             "근거": "발행기관 URL·기업식별자·연도 연결 (실제 출처 인증 아님)"},
            {"단계": "Verification", "판정": state,
             "근거": "2024·2023 연결매출의 수동기록 산술 비교"},
            {"단계": "Risk", "판정": result["risk"]["status"],
             "근거": "검증된 부채·자본 두 항목이 없어 계산 보류"},
        ],
        use_container_width=True, hide_index=True,
    )
    st.info("Risk 산출 보류: 부채·자본의 검증된 원문 수치가 없습니다. 위험도 0 또는 안전 판정으로 대체하지 않습니다.")
    _render_offline_agent_trace(st, claims[choice])
    st.caption(
        "출처 권리/재배포 미확인 · 실제 DART 뷰어 미검증 · AI/LLM·실 API 호출 없음 · "
        "산술 'verified'는 회사 재무자료의 현재 진위 또는 대회 제출 인증이 아닙니다."
    )


def _render_offline_agent_trace(st, claim: str) -> None:
    """Explain an existing bounded local decision without claiming live AI."""
    st.subheader("Agent 판단 추적 — 규칙 기반 오프라인 시연")
    if not st.checkbox("PLAN → EVALUATE → DECIDE → REPORT 확인", value=False):
        st.caption("선택 시 고정된 수동 검증 기록만 재평가합니다. 외부 조회·LLM 호출·자동 투자 판단 없음.")
        return
    try:
        from proofinvest.agent_controller import run_issuer_manual_demo

        decision = run_issuer_manual_demo(claim)
        if (
            decision.get("mode") != "RULE_BASED_OFFLINE_NOT_LLM_AGENT"
            or decision.get("ai_agent_executed") is not False
            or decision.get("live_api_called") is not False
            or decision.get("authenticated_external_source") is not False
            or decision.get("external_tool_calls") != 0
            or decision.get("tool_budget") != 1
        ):
            raise ValueError("Unexpected controller safety contract")
        trace = decision["trace"]
        if not isinstance(trace, list) or [r["step"] for r in trace] != [
            "PLAN", "EVALUATE", "DECIDE", "REPORT"
        ]:
            raise ValueError("Unexpected controller trace")
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("고정된 근거 기록 또는 로컬 판단 경로를 확인할 수 없어 Agent 추적 표시를 중단합니다.")
        return

    st.metric("로컬 제어기 상태", decision["status"])
    st.info(
        "판단 코드: " + decision["reason_code"]
        + " · 사람에게 요청할 다음 조치: " + decision["next_action"]
    )
    st.dataframe(
        [
            {"단계": row["step"],
             "판단": row.get("decision", row.get("tool", "오프라인 평가")),
             "네트워크 호출": "없음"}
            for row in trace
        ],
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "규칙 기반 로컬 제어기 · 내부 검증 도구 최대 1회 · 외부 API 0회 · "
        "실제 LLM Agent 실행/SEC·DART 원문 인증/수익률 예측/공식 제출이 아닙니다."
    )


def _render_sec_curated_case(st) -> None:
    """Use the SEC-format local data verifier; never imply live SEC connectivity."""
    st.title("ProofInvest — SEC 10-K 연매출 검산 (오프라인)")
    st.warning(
        "MANUALLY_CURATED_SEC_EXCERPT · Apple FY2025 10-K의 공개 수치를 수동 발췌한 기록입니다. "
        "SEC CompanyFacts API 실시간 조회·원본 자동수집·LLM Agent·투자 권고가 아닙니다."
    )
    date_choices = {
        "2025-11-01 — 공시 공개 후": "2025-11-01",
        "2025-10-30 — 공시 공개 전": "2025-10-30",
    }
    asof_label = st.selectbox("기준일 (as-of)", list(date_choices))
    growth_choices = {
        "6.43% — 수동 기록과 일치": "6.43",
        "30% — 불일치 주장": "30",
        "주장 없음 — 숫자만 계산": None,
    }
    claim_label = st.selectbox("비교할 성장률 주장", list(growth_choices))
    try:
        from proofinvest.sec_companyfacts import run_curated_apple_demo
        verdict = run_curated_apple_demo(
            as_of=date_choices[asof_label],
            claimed_growth_pct=growth_choices[claim_label],
        )
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("SEC 수동 발췌 데이터가 없거나 변경되어 계산을 중단했습니다.")
        return
    if (verdict.get("authenticated_external_source") is not False
            or verdict.get("live_api_called") is not False
            or verdict.get("ai_agent_executed") is not False):
        st.error("출처 검증 상태가 비정상입니다. 결과를 표시하지 않습니다.")
        return
    st.caption(
        "공개 자료: Apple Inc. FY2025 10-K · CIK 0000320193 · "
        "접수번호 0000320193-25-000079 · 공시일 2025-10-31"
    )
    st.markdown(
        "[SEC 공식 접수 페이지](https://www.sec.gov/Archives/edgar/data/"
        "320193/000032019325000079/0000320193-25-000079-index.htm)"
    )
    if verdict["status"] == "unavailable":
        st.warning(
            "기준일 또는 증거가 검증 요건에 맞지 않아 계산 보류: "
            + verdict["reason_code"]
        )
        return
    st.metric("연매출 성장률 (오프라인 수치검산)", verdict["growth_pct"] + "%")
    st.dataframe([
        {"연도": "2025", "순매출 (백만 USD)": int(verdict["current_usd"]) // 1_000_000},
        {"연도": "2024", "순매출 (백만 USD)": int(verdict["prior_usd"]) // 1_000_000},
    ], use_container_width=True, hide_index=True)
    if verdict["status"] == "conflict":
        st.error("주장한 성장률과 공시 발췌 수치의 계산이 불일치합니다.")
    else:
        st.info("산술 비교만 완료되었습니다. 원본 수집·출처 진위 독립 인증은 미실시입니다.")
    st.caption(
        "규칙 기반 Python Decimal 계산 · 동일 10-K 접수번호 확인 · "
        "기준일 이후 공시 차단 · 실 API/LLM 0회 · 원문 독립 인증 및 Risk 판정 없음"
    )


def _render_sec_verdict_trace(st, verdict: dict) -> None:
    """Expose bounded local outcomes for success, conflict and unavailable."""
    review = verdict.get("bounded_review")
    expected = {
        "calculated_unverified": ("needs_authentication", {"SEC_STRUCTURAL_RESULT_ONLY"}),
        "conflict": ("blocked", {"SEC_GROWTH_CLAIM_CONFLICT"}),
        "unavailable": (
            "blocked", {"SEC_EVIDENCE_UNAVAILABLE", "SEC_VERIFICATION_UNAVAILABLE"}
        ),
    }.get(verdict.get("status"))
    steps = ["PLAN", "EVALUATE", "DECIDE", "REPORT"]
    if (expected is None
            or not isinstance(review, dict)
            or review.get("schema") != "proofinvest.sec-verdict-local-review.v1"
            or review.get("mode") != "RULE_BASED_SEC_VERDICT_REVIEW_NOT_LLM_AGENT"
            or review.get("status") != expected[0]
            or review.get("reason_code") not in expected[1]
            or review.get("ai_agent_executed") is not False
            or review.get("authenticated_external_source") is not False
            or review.get("source_rights_verified") is not False
            or review.get("official_contest_submission") is not False
            or review.get("external_tool_calls") != 0
            or review.get("tool_budget") != 0
            or not isinstance(review.get("trace"), list)
            or [row.get("step") for row in review["trace"] if isinstance(row, dict)] != steps
            or len(review["trace"]) != 4
            or review["trace"][2].get("decision") != review["reason_code"]
            or review["trace"][3].get("decision") != "HUMAN_REVIEW_REQUIRED"):
        st.warning("SEC 판단 추적을 검증하지 못해 Agent 흐름을 표시하지 않습니다.")
        return
    # Only fixed, internal review action codes can reach UI, not remote text.
    actions = {
        "SEC_STRUCTURAL_RESULT_ONLY": "INDEPENDENT_SEC_SOURCE_AND_RIGHTS_REVIEW",
        "SEC_GROWTH_CLAIM_CONFLICT": "REVIEW_DISPUTED_GROWTH_CLAIM",
        "SEC_EVIDENCE_UNAVAILABLE": "CHECK_SOURCE_OR_REQUEST_HUMAN_REVIEW",
        "SEC_VERIFICATION_UNAVAILABLE": "REVIEW_FILING_DATE_PERIOD_OR_SOURCE",
    }
    if review.get("next_action") != actions[review["reason_code"]]:
        st.warning("SEC 판단의 후속 조치가 올바르지 않아 표시를 중단했습니다.")
        return
    st.subheader("SEC 검증 후 판단 추적 — 규칙 기반, AI Agent 아님")
    st.dataframe(
        [{"단계": row["step"], "결정": row["decision"]} for row in review["trace"]],
        use_container_width=True, hide_index=True,
    )
    st.info("추가 확인: " + actions[review["reason_code"]])


def _render_sec_live_case(st) -> None:
    """Explicit-on-click one-issuer SEC HTTP; no automatic background requests."""
    import os

    st.title("ProofInvest — SEC 공식 CompanyConcept 조회")
    st.warning(
        "NETWORK_OPT_IN · Apple FY2025 수치 확인용 SEC HTTPS 조회(버튼 클릭 시 1회). "
        "연결된 실 API 결과라도 공시 내용의 독립적인 원문 인증·LLM Agent 분석·"
        "투자 권고·본선 배포 완료를 뜻하지 않습니다."
    )
    st.info(
        "고정 요청: Apple (CIK 0000320193), FY2025 10-K, 기준일 2025-11-01. "
        "SEC 공개 API 호출에 식별 가능한 User-Agent가 필요합니다. "
        "환경변수 PROOFINVEST_SEC_USER_AGENT에 실제 연락처를 설정하세요."
    )
    if not st.button("SEC 공식 API 1회 조회 및 연매출 검산"):
        st.caption("조회 버튼을 누르지 않으면 SEC 네트워크 요청이 발생하지 않습니다.")
        return
    try:
        from proofinvest.sec_api_client import run_sec_annual_revenue
        verdict = run_sec_annual_revenue(
            cik="0000320193",
            accession="0000320193-25-000079",
            current_end="2025-09-27",
            prior_end="2024-09-28",
            as_of="2025-11-01",
            user_agent=os.environ.get("PROOFINVEST_SEC_USER_AGENT", ""),
            allow_network=True,
        )
        if (verdict.get("authenticated_external_source") is not False
                or verdict.get("ai_agent_executed") is not False
                or verdict.get("source_rights_verified") is not False):
            raise ValueError("Unexpected SEC adapter attestation flags")
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("SEC 응답을 검증하지 못했습니다. 숫자와 인증 상태를 표시하지 않습니다.")
        return
    if verdict.get("status") != "calculated_unverified":
        st.error("SEC 수집·검산 보류: " + str(verdict.get("reason_code", "UNKNOWN")))
        _render_sec_verdict_trace(st, verdict)
        return
    if verdict.get("live_api_called") is not True:
        st.error("실제 HTTP 요청 여부를 확인할 수 없어 결과 표시를 차단했습니다.")
        return
    st.metric("SEC JSON 연매출 증감률 (독립 인증 아님)", verdict["growth_pct"] + "%")
    st.dataframe([
        {"연도": "FY2025", "매출 (백만 USD)": int(verdict["current_usd"]) // 1_000_000},
        {"연도": "FY2024", "매출 (백만 USD)": int(verdict["prior_usd"]) // 1_000_000},
    ], use_container_width=True, hide_index=True)
    st.markdown("[SEC 공식 10-K 접수 페이지](" + verdict["sec_filing_index"] + ")")
    _render_sec_verdict_trace(st, verdict)
    st.caption(
        "단일 SEC 공식 CompanyConcept HTTPS 응답에 대한 산술 검산입니다. "
        "출처 권리/실제 제출/원문 독립 재인증/LLM·ML·DL 모두 별도 검증 대상입니다."
    )


def render_app(st) -> None:
    st.set_page_config(page_title="ProofInvest | 오프라인 출처 시연", layout="wide")
    # The public recovery ZIP is synthetic-only: never offer an unavailable
    # manual issuer mode or import its dependencies from an unrelated install.
    evidence_file = Path(__file__).resolve().parent / "docs/evidence/samsung_2024_cfs_revenue.json"
    available_sources = [_SOURCE_SYNTHETIC]
    if evidence_file.is_file():
        available_sources.append(_SOURCE_MANUAL)
    sec_excerpt = Path(__file__).resolve().parent / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
    if sec_excerpt.is_file():
        available_sources.append(_SOURCE_SEC_CURATED)
        available_sources.append(_SOURCE_SEC_LIVE)
    source = st.selectbox("자료 유형", available_sources)
    if source == _SOURCE_SEC_CURATED:
        _render_sec_curated_case(st)
        return
    if source == _SOURCE_SEC_LIVE:
        _render_sec_live_case(st)
        return
    if source == _SOURCE_MANUAL:
        st.title("ProofInvest — 실제 발행사 수동기록 검산")
        _render_manual_case(st)
        return
    st.title("ProofInvest — 오프라인 합성 데이터")
    st.warning(
        "SYNTHETIC_FIXTURE · 교육용 가상 데이터 · 외부 공시 원본 미인증. "
        "실제 기업 분석, 투자 권고, DAKER 공식 제출물이 아닙니다."
    )
    mode = st.radio("조회 방식", [_DIRECT, _STORED], horizontal=True)
    if mode == _STORED:
        try:
            bundle = read_synthetic_snapshot_with_provenance(
                Path.home() / ".proofinvest-synthetic-cache"
            )
        except (ValueError, OSError):
            st.error(
                "저장된 합성 결과를 확인할 수 없습니다. "
                "먼저 'python -m proofinvest.snapshot_store --save'를 명시적으로 실행하거나 "
                "손상된 로컬 캐시를 확인하세요. 자동 재계산·덮어쓰기는 하지 않습니다."
            )
            return
        view = bundle["view"]
        source_hash = bundle["provenance"]["fixture_sha256"]
        st.success("저장된 합성 계산 결과 조회 성공 · 재계산하지 않음")
        st.caption(
            "저장된 결과 체크섬(SHA-256): "
            + bundle["provenance"]["snapshot_payload_sha256"]
        )
    else:
        view = load_synthetic_snapshot()
        source_hash = _fixture_digest()

    st.info(
        "출처: fixtures/synthetic_annual.json (로컬 합성 fixture) · "
        f"원본 SHA-256: {source_hash} · "
        "무결성 확인은 실제 공시 진위 검증이 아닙니다."
    )
    left, middle, right = st.columns(3)
    left.metric("데이터 유형", view["source_kind"])
    middle.metric("기준 연도", str(view["year"]))
    right.metric("외부 출처 인증", "미인증")

    st.subheader("재무 자료 — 원본 합성 fixture")
    st.caption("CFS(연결)/OFS(별도) 구분 표시 · 금액 단위: KRW · 합성 출처 링크 없음")
    st.dataframe(view["financial_rows"], use_container_width=True, hide_index=True)
    st.subheader("Verification — 합성 데이터 계산")
    st.dataframe(view["checks"], use_container_width=True, hide_index=True)
    st.caption(
        "여기서 verified는 제공된 합성 수치에 대한 산술 일치만 뜻합니다. "
        "실제 원문 인증이 아닙니다."
    )
    st.subheader("Risk — 시연용 탐색 신호")
    risk = view["risk"]
    st.metric("부채/자본 비율", risk["표시 비율"])
    st.info(f'{risk["판정"]} · 보류 코드: {risk["보류 사유"]}')
    st.caption(
        "임계값 200%는 시연용 탐색 기준이며 투자 판단 기준이 아닙니다. "
        "이 화면의 구형 CLI 탐색 결과는 verified-only Risk 인증 경로와 별개입니다."
    )


if __name__ == "__main__":
    import streamlit as st
    render_app(st)
