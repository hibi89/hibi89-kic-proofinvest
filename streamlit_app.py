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
_SOURCE_DL_ARCHIVE = "DL 공시 원문 근거 추적 — 합성 오프라인"

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
    # Offline Guard preview: never authorize a real investment action.
    from proofinvest.guard_sec_adapter import evaluate_sec_guard
    guard_preview = evaluate_sec_guard(verdict)
    st.subheader("Guard-Agent — 모의 투자 검토 통제")
    st.metric("정책 판정", guard_preview["guard"]["decision"])
    st.caption("수치 검산만 수행 · 부채/자본 위험 근거 없음 → HOLD · 사람 승인/실거래 없음")
    st.json({"reason_codes": guard_preview["guard"]["reason_codes"],
             "policy_version": guard_preview["guard"]["policy_version"],
             "source_authenticated": False, "trade_executed": False})
    # Persist only on explicit click. This is a local demo acknowledgement,
    # never an investment authorization or authenticated SEC attestation.
    if st.button("Guard 판정·감사 기록 저장 (로컬 모의)", key="guard_sec_record"):
        try:
            import hashlib
            from proofinvest.guard_workflow import run_guard_review
            local_dir = Path.home() / ".proofinvest-guard"
            local_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            key = "|".join([date_choices[asof_label], str(growth_choices[claim_label])])
            run_id = "curated-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
            receipt = run_guard_review(
                verdict, run_id=run_id,
                database_path=local_dir / "audit.sqlite",
            )
            st.success("로컬 감사 기록 저장 완료" if not receipt["audit"]["replayed"]
                       else "기존 감사 기록 재조회 (중복 저장 없음)")
            st.json({"run_id": run_id, "guard": receipt["guard"]["decision"],
                     "audit_event_id": receipt["audit"]["event_id"],
                     "audit_hash": receipt["audit"]["event_hash"],
                     "human_review": "NOT_REQUESTED", "trade_executed": False})
        except (ValueError, OSError, TypeError, KeyError, ImportError) as exc:
            st.error("감사 기록 저장 또는 검증 실패 — 승인되지 않았습니다.")
    # Human review is separate from Guard scoring. The SEC curated view
    # has no verified risk facts and therefore cannot authorize a simulation.
    with st.expander("사람 검토 기록 — 로컬 모의", expanded=False):
        st.caption("검토 기록은 실제 투자 승인이나 거래 실행이 아닙니다.")
        reviewer = st.text_input("검토자 식별명", key="guard_reviewer", max_chars=80)
        review_action = st.selectbox(
            "검토 조치", ["ACKNOWLEDGE", "REQUEST_EXCEPTION"],
            key="guard_review_action",
        )
        review_reason = st.text_area("검토 사유 (5자 이상)", key="guard_review_reason")
        if st.button("검토 기록 저장", key="guard_review_save"):
            try:
                import hashlib
                from proofinvest.guard_workflow import run_guard_review
                local_dir = Path.home() / ".proofinvest-guard"
                local_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                key = "|".join([date_choices[asof_label], str(growth_choices[claim_label])])
                run_id = "curated-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
                result = run_guard_review(
                    verdict, run_id=run_id, database_path=local_dir / "audit.sqlite",
                    reviewer=reviewer, action=review_action, reason=review_reason,
                )
                st.success("모의 검토 기록 저장 완료")
                st.json({"run_id": run_id, "guard_decision": result["guard"]["decision"],
                         "review_id": result["review"]["review_id"],
                         "review_action": result["review"]["action"],
                         "trade_executed": False})
            except (ValueError, OSError, TypeError, KeyError, ImportError):
                st.error("검토 기록 저장 실패 — 승인되지 않았습니다.")
    with st.expander("저장된 Guard 감사 이력 조회", expanded=False):
        if st.button("감사 무결성·이력 조회", key="guard_audit_history"):
            try:
                from proofinvest.guard_audit import GuardAuditStore
                import sqlite3
                db_path = Path.home() / ".proofinvest-guard" / "audit.sqlite"
                if not db_path.is_file():
                    st.info("저장된 로컬 감사 기록이 없습니다.")
                else:
                    store = GuardAuditStore(db_path)
                    from proofinvest.guard_review import GuardReviewStore
                    if not store.verify_chain() or not GuardReviewStore(db_path).verify_reviews():
                        st.error("감사 또는 사람 검토 무결성 검증 실패 — 이력 표시를 중단합니다.")
                    else:
                        with sqlite3.connect(db_path) as conn:
                            rows = conn.execute(
                                "SELECT event_id, run_id, event_type, event_hash, created_at "
                                "FROM guard_audit_events ORDER BY event_id DESC LIMIT 50"
                            ).fetchall()
                        st.success("Guard 결정 감사 체인 검증 통과 (로컬 무결성만)")
                        st.dataframe([
                            {"event_id": a, "run_id": b, "type": c, "sha256": d, "UTC": e}
                            for a, b, c, d, e in rows
                        ], use_container_width=True, hide_index=True)
            except (sqlite3.Error, ValueError, OSError, ImportError):
                st.error("감사 기록을 안전하게 조회할 수 없습니다.")
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



def _valid_dl_archive_receipt(receipt: object) -> bool:
    """Strict presentation-only gate; no third-party bytes treated as trusted."""
    import re

    if type(receipt) is not dict:
        return False
    expected = {
        "schema": "proofinvest.kic-dl-original-e2e.v1",
        "status": "offline_original_source_path_pass",
        "synthetic_only": True,
        "original_file_receipt_status": "SAVED",
        "original_replay_receipt_status": "REUSED",
        "original_bytes_match": True,
        "source_span_status": "untrusted_original_span_for_review",
        "kic_metadata_link": "linked_metadata_only",
        "kic_original_crosslink": "linked_untrusted_original_span_for_review",
        "original_span_metadata_linked": True,
        "authenticated_external_source": False,
        "real_sec_network_called": False,
        "real_filing_retrieved": False,
        "official_submission_made": False,
        "numeric_facts_authenticated": False,
        "issuer_cik": "0000000001",
        "accession": "0000000001-25-000001",
        "source_uri": (
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000125000001/synthetic10k.htm"
        ),
    }
    if any(receipt.get(key) != value or type(receipt.get(key)) is not type(value)
           for key, value in expected.items()):
        return False
    sha = receipt.get("original_filing_sha256")
    index_sha = receipt.get("submissions_sha256")
    if (not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None
            or not isinstance(index_sha, str)
            or re.fullmatch(r"[0-9a-f]{64}", index_sha) is None
            or sha == index_sha):
        return False
    start, end = receipt.get("source_byte_start"), receipt.get("source_byte_end")
    # Literal is a known fixed synthetic marker, not an AI-extracted source fact.
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= 4096
            or end - start != len("TEST_LITERAL_SOURCE_SPAN")):
        return False
    context = receipt.get("escaped_context")
    return (isinstance(context, str) and 0 < len(context) <= 2048
            and "TEST_LITERAL_SOURCE_SPAN" in context
            and "<" not in context and ">" not in context)


def _render_dl_archive_case(st) -> None:
    """Run a synthetic archived-byte replay only when the user selects it."""
    st.title("ProofInvest — DL 원문 근거 추적 (합성 시연)")
    st.warning(
        "SYNTHETIC_ONLY · 실제 존재하지 않는 기업/접수번호와 인공 HTML 사용. "
        "로컬 원문 바이트/해시/위치 연결만 확인하며 SEC 원문 진위·재무 사실을 인증하지 않습니다."
    )
    try:
        from proofinvest.kic_dl_original_demo import replay_original
        receipt = replay_original()
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("오프라인 원문 근거 재현에 실패했습니다. 출처 카드를 표시하지 않습니다.")
        return
    if not _valid_dl_archive_receipt(receipt):
        st.error("원문 메타데이터 신뢰 경계를 통과하지 못해 출처 카드를 차단했습니다.")
        return

    st.subheader("수동 검토용 출처 카드 — 인증되지 않은 원문")
    st.info(
        "기업 CIK/접수번호/원문 URL은 가상 SEC 형식입니다. "
        "인용은 로컬 저장본의 정확한 바이트 위치만 뜻하며, 웹페이지로 이동하지 않습니다."
    )
    st.dataframe([
        {"근거 속성": "기업 CIK (가상)", "값": receipt["issuer_cik"]},
        {"근거 속성": "접수번호 (가상)", "값": receipt["accession"]},
        {"근거 속성": "자료 URL (가상)", "값": receipt["source_uri"]},
        {"근거 속성": "원문 SHA-256", "값": receipt["original_filing_sha256"]},
        {"근거 속성": "인용 바이트 시작", "값": str(receipt["source_byte_start"])},
        {"근거 속성": "인용 바이트 종료 (미포함)", "값": str(receipt["source_byte_end"])},
        {"근거 속성": "교차 연결", "값": "메타데이터 일치 · 사실 미인증"},
    ], use_container_width=True, hide_index=True)
    st.caption("HTML 렌더링 금지: 엔티티 이스케이프된 인공 원문을 텍스트 코드로만 표시합니다.")
    st.code(receipt["escaped_context"], language="text")
    st.warning(
        "SEC 실조회 0회 · 외부 출처 독립 인증 없음 · 재무 숫자 사실 확인 없음 · "
        "LLM/ML/DL 판정 아님 · 실제 공시 인용 또는 대회 공식 제출 근거로 사용 금지."
    )
    try:
        from proofinvest.evidence_report import (
            build_synthetic_evidence_report, render_report,
        )
        report = build_synthetic_evidence_report()
        if (report.get("mode") != "SYNTHETIC_FIXTURE_OFFLINE_ONLY"
                or report.get("status") != "local_structural_review_only"
                or report["issuer"]["cik"] != receipt["issuer_cik"]
                or report["issuer"]["accession"] != receipt["accession"]
                or report["source"]["uri"] != receipt["source_uri"]
                or report["source"]["archived_original_sha256"] != receipt["original_filing_sha256"]
                or report["source"]["submissions_json_sha256"] != receipt["submissions_sha256"]
                or report["source"]["source_span"]["start_byte"] != receipt["source_byte_start"]
                or report["source"]["source_span"]["end_byte_exclusive"] != receipt["source_byte_end"]
                or any(value is not False for value in report["authenticity"].values())):
            raise ValueError("Synthetic report trust/identity mismatch")
        json_report = render_report(report, "json")
        markdown_report = render_report(report, "markdown")
    except (ImportError, ValueError, OSError, TypeError, KeyError):
        st.error("합성 보고서 재검증에 실패하여 다운로드를 차단했습니다.")
        return
    st.subheader("합성 근거 보고서 내보내기 — 실제 투자 분석 자료 아님")
    st.download_button(
        "합성 보고서 JSON 다운로드",
        data=json_report,
        file_name="proofinvest_SYNTHETIC_UNVERIFIED.json",
        mime="application/json",
        key="dl_synthetic_json",
    )
    st.download_button(
        "합성 보고서 Markdown 다운로드",
        data=markdown_report,
        file_name="proofinvest_SYNTHETIC_UNVERIFIED.md",
        mime="text/markdown",
        key="dl_synthetic_markdown",
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
    dl_archive = Path(__file__).resolve().parent / "disclosure_lightning/originals.py"
    dl_replay = Path(__file__).resolve().parent / "proofinvest/kic_dl_original_demo.py"
    if dl_archive.is_file() and dl_replay.is_file():
        available_sources.append(_SOURCE_DL_ARCHIVE)
    source = st.selectbox("자료 유형", available_sources)
    if source == _SOURCE_DL_ARCHIVE:
        _render_dl_archive_case(st)
        return
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
