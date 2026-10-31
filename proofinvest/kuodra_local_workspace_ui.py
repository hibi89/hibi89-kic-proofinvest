"""Opt-in local-only Streamlit interface for operator-supplied SEC-shaped files.

Must NOT run on a publicly reachable Streamlit server. Both an explicit
environment switch and an explicit loopback server bind are mandatory.
No file path inputs, no network calls, no original persistence beyond the
existing temporary source-span checker. Downloading a report is optional.
"""
from __future__ import annotations

import os
import json

from disclosure_lightning.core import MAX_JSON_BYTES
from disclosure_lightning.originals import MAX_FILING_BYTES

from .local_sec_packet import _MAX_FILE_BYTES
from .local_sec_html_report import render_local_sec_html
from .kuodra_local_workspace import (
    preview_uploaded_triplet, review_uploaded_triplet, discover_uploaded_periods,
    discover_uploaded_filing_targets, _check_bytes,
)


def local_workspace_enabled(st) -> bool:
    if os.environ.get("KUODRA_ENABLE_LOCAL_SOURCE_UI") != "1":
        return False
    try:
        return st.get_option("server.address") in ("127.0.0.1", "localhost")
    except (KeyError, AttributeError, RuntimeError):
        return False


def _uploaded_sources(files) -> dict[str, bytes]:
    caps = {
        "submissions": MAX_JSON_BYTES,
        "companyfacts": _MAX_FILE_BYTES,
        "original_filing": MAX_FILING_BYTES,
        "history_page": MAX_JSON_BYTES,
    }
    if set(files) != set(caps) or any(
        files[k] is None or type(files[k].size) is not int
        or not 0 < files[k].size <= caps[k]
        for k in ("submissions", "companyfacts", "original_filing")
    ) or (files["history_page"] is not None and (
        type(files["history_page"].size) is not int
        or not 0 < files["history_page"].size <= caps["history_page"]
    )):
        raise ValueError("THREE_OR_FOUR_BOUNDED_UPLOADS_REQUIRED")
    return {key: files[key].getvalue() for key in caps if files[key] is not None}


def render_local_workspace(st) -> None:
    if not local_workspace_enabled(st):
        st.error("로컬 파일 분석은 localhost 전용 명시적 설정이 없으면 비활성화됩니다.")
        return
    st.title("KUODRA · 로컬 SEC 원본 3종 검토")
    st.caption("오래된 10-K가 recent에 없다면 filings.files에 등록된 이력 JSON 1개를 추가할 수 있습니다.")
    st.warning(
        "로컬 PC에서만 사용하십시오. 파일은 브라우저에서 실행 중인 Streamlit "
        "서버로 전달됩니다. 다른 PC/클라우드에 배포한 서버에는 올리지 마십시오. "
        "원문 출처·시간·권리 모두 미인증이며, 실거래·투자권고가 아닙니다."
    )
    st.caption("Preview → 명시적 임시 감사 동의 → HOLD/REJECT → JSON/HTML 다운로드. "
               "외부 SEC/Gemini 호출 및 영구 SQLite 저장 없음.")

    uploads = {
        "submissions": st.file_uploader("1. submissions.json", type=["json"],
                                        key="kuodra_submissions"),
        "companyfacts": st.file_uploader("2. companyfacts.json", type=["json"],
                                         key="kuodra_companyfacts"),
        "original_filing": st.file_uploader("3. 원문 10-K HTML", key="kuodra_original"),
        "history_page": st.file_uploader("4. 이전 filings.files JSON (선택)", type=["json"],
                                         key="kuodra_history"),
    }
    history_page_name = st.text_input(
        "이력 페이지 파일명 (해당하는 경우 filings.files.name 그대로)",
        key="kuodra_history_name", max_chars=90,
    ).strip()
    # An explicitly chosen filing can only prefill BEFORE the CIK and
    # accession widgets are built on this rerun. Verify byte and date pins
    # again, so stale targets cannot silently overwrite operator identity.
    pending = st.session_state.pop("kuodra_pending_filing", None)
    if pending is not None:
        try:
            exact_pins = _check_bytes(_uploaded_sources(uploads))
            if (pending["source_sha256"] != exact_pins
                    or pending["history_page_name"] != (
                        history_page_name if uploads["history_page"] else None
                    )
                    or pending["as_of"] != st.session_state.get("kuodra_asof")
                    or pending["collected_at"] != st.session_state.get("kuodra_collected")):
                raise ValueError("STALE_FILING_TARGET")
            st.session_state["kuodra_cik"] = pending["cik"]
            st.session_state["kuodra_accession"] = pending["accession"]
        except (ValueError, KeyError, TypeError, OSError):
            st.warning("원본 또는 기준 정보가 변경되어 공시 대상 자동 입력을 취소했습니다.")
    left, right = st.columns(2)
    with left:
        cik = st.text_input("CIK 10자리", key="kuodra_cik", max_chars=10)
        accession = st.text_input("SEC 접수번호", key="kuodra_accession", max_chars=20)
        as_of = st.text_input("기준일 (YYYY-MM-DD)", key="kuodra_asof", max_chars=10)
        collected_at = st.text_input("사용자 주장 수집시각 (UTC ISO8601)",
                                     key="kuodra_collected", max_chars=40)
    # Read-only target discovery uses issuer-specific SEC submissions metadata.
    # It never approves a filing, confirms source provenance or reads HTML text.
    if st.button("업로드한 공시 목록에서 10-K 대상 찾기 (읽기 전용)",
                 key="kuodra_find_filings"):
        st.session_state.pop("kuodra_filing_targets", None)
        st.session_state.pop("kuodra_discovery", None)
        st.session_state.pop("kuodra_preview_receipt", None)
        try:
            candidate_report = discover_uploaded_filing_targets(
                _uploaded_sources(uploads),
                as_of=as_of, collected_at=collected_at,
                history_page_name=(history_page_name if uploads["history_page"] else None),
            )
            st.session_state["kuodra_filing_targets"] = candidate_report
        except (ValueError, KeyError, TypeError, OSError, OverflowError, RecursionError):
            st.error("공시 목록을 읽을 수 없습니다. Submissions·이력 파일·기준 시각을 확인하십시오.")
    candidate_report = st.session_state.get("kuodra_filing_targets")
    if candidate_report is not None:
        try:
            valid_candidates = (
                candidate_report.get("source_sha256")
                == _check_bytes(_uploaded_sources(uploads))
                and candidate_report.get("as_of") == as_of
                and candidate_report.get("collected_at") == collected_at
                and candidate_report.get("history_page_name") == (
                    history_page_name if uploads["history_page"] else None
                )
                and candidate_report.get("source_authenticated") is False
                and candidate_report.get("audit_written") is False
            )
        except (ValueError, KeyError, OSError, TypeError):
            valid_candidates = False
        if not valid_candidates:
            st.session_state.pop("kuodra_filing_targets", None)
            st.warning("입력 파일·시각이 변경되어 이전 공시 후보를 폐기했습니다.")
        else:
            targets = candidate_report["filing_targets"]
            if targets:
                st.caption("공시 목록 후보는 사용자 제공 메타데이터이며 원문 진위가 인증된 것은 아닙니다.")
                target_index = st.selectbox(
                    "10-K 공시 대상 후보 (원본과 대조 후 선택)",
                    list(range(len(targets))),
                    format_func=lambda k: (
                        targets[k]["filing_date"] + " · " +
                        targets[k]["accession"] + " · " + targets[k]["index_kind"]
                    ), key="kuodra_target_choice",
                )
                if st.button("선택한 공시의 CIK·접수번호 입력",
                             key="kuodra_apply_filing"):
                    st.session_state["kuodra_pending_filing"] = {
                        "source_sha256": candidate_report["source_sha256"],
                        "history_page_name": candidate_report["history_page_name"],
                        "as_of": candidate_report["as_of"],
                        "collected_at": candidate_report["collected_at"],
                        "cik": candidate_report["issuer_cik"],
                        "accession": targets[target_index]["accession"],
                    }
                    st.session_state.pop("kuodra_discovery", None)
                    st.session_state.pop("kuodra_preview_receipt", None)
                    st.rerun()
            else:
                st.info("해당 기준 시각에 확인 가능한 10-K 목록이 없습니다. 이력 파일을 확인하십시오.")
    # This read-only discovery happens BEFORE Streamlit constructs the manual
    # fiscal-end/needle widgets. Candidate application can therefore safely
    # prefill widget state on this same rerun (no stale-widget mutation).
    reveal_local_text = st.checkbox(
        "원문 인용 문구 후보를 이 로컬 화면에 표시하는 데 동의",
        value=False, key="kuodra_reveal_candidate_text",
    )
    if st.button("원본에서 연매출 기간 후보 찾기 (읽기 전용)",
                 key="kuodra_discover"):
        st.session_state.pop("kuodra_discovery", None)
        st.session_state.pop("kuodra_preview_receipt", None)
        try:
            found = discover_uploaded_periods(
                _uploaded_sources(uploads),
                cik=cik, accession=accession, as_of=as_of,
                collected_at=collected_at,
                show_local_needle_candidates=reveal_local_text,
                history_page_name=(history_page_name if uploads["history_page"] else None),
            )
            st.session_state["kuodra_discovery"] = found
        except (ValueError, TypeError, OSError, KeyError, OverflowError,
                RecursionError):
            st.error("기간 후보를 찾지 못했습니다. SEC 형식·기간·발행사 식별자를 확인하십시오.")

    found = st.session_state.get("kuodra_discovery")
    if found is not None:
        # Check current sources and requested identity on EVERY rerun, not
        # just when the user clicks "apply"; changed uploads invalidate
        # earlier advice before it can be selected or disclosed.
        try:
            current_digests = _check_bytes(_uploaded_sources(uploads))
            candidate_is_current = (
                found.get("source_sha256") == current_digests
                and found.get("issuer_cik") == cik
                and found.get("accession") == accession
                and found.get("as_of") == as_of
                and found.get("collected_at") == collected_at
                and found.get("history_page_name") == (
                    history_page_name if uploads["history_page"] else None
                )
                and found.get("source_authenticated") is False
            )
        except (ValueError, TypeError, OSError, KeyError):
            candidate_is_current = False
        if not candidate_is_current:
            st.session_state.pop("kuodra_discovery", None)
            st.warning("원본이나 식별자가 변경되어 이전 기간 후보를 폐기했습니다.")
        else:
            periods = found["period_candidates"]
            st.caption("연매출 기간 후보: 원본 형식 검증 결과이며 재무 사실 인증이 아닙니다.")
            options = list(range(len(periods)))
            chosen = st.selectbox(
                "연매출 기간 후보를 선택하십시오",
                options,
                format_func=lambda i: (
                    periods[i]["current_end"] + " / " +
                    periods[i]["prior_end"] + " · " +
                    periods[i]["growth_pct_unverified"] + "% (미인증)"
                ),
                key="kuodra_period_choice",
            )
            needles = (
                found.get("local_needle_candidates", [])
                if reveal_local_text else []
            )
            selected_needle = None
            if needles:
                st.warning("아래 문구는 사용자가 선택한 로컬 원문의 일부이며, 사실 인증이 아닙니다.")
                needle_ix = st.selectbox(
                    "원문 텍스트 후보 (사용자가 검토·선택)",
                    list(range(len(needles))),
                    format_func=lambda i: needles[i]["needle"],
                    key="kuodra_needle_choice",
                )
                selected_needle = needles[needle_ix]["needle"]
            if st.button("선택한 기간·문구를 입력란에 적용",
                         key="kuodra_apply_period"):
                pair = periods[chosen]
                st.session_state["kuodra_current"] = pair["current_end"]
                st.session_state["kuodra_prior"] = pair["prior_end"]
                if selected_needle is not None:
                    st.session_state["kuodra_needle"] = selected_needle
                st.session_state.pop("kuodra_preview_receipt", None)
                st.success("선택 후보를 입력했습니다. 아래 원본 대조 미리보기를 별도로 실행하십시오.")

    with right:
        current_end = st.text_input("현재 회계기간 종료일", key="kuodra_current", max_chars=10)
        prior_end = st.text_input("직전 회계기간 종료일", key="kuodra_prior", max_chars=10)
        needle = st.text_input("원문 본문에서 고유한 인용 문구",
                               key="kuodra_needle", max_chars=240)
        claim = st.text_input("성장률 주장 % (선택)", key="kuodra_claim", max_chars=100)
    request = {
        "cik": cik, "accession": accession,
        "as_of": as_of, "collected_at": collected_at,
        "current_end": current_end, "prior_end": prior_end,
        "needle": needle, "claimed_growth_pct": claim.strip() or None,
    }
    if uploads["history_page"] is not None:
        request["history_page_name"] = history_page_name
    # Optional, read-only contract for separately evaluated historical ML.
    # Neither this upload nor its report can alter the SEC/Decimal/Guard path.
    from .ml_explainability_ui import render_local_ml_evaluation
    render_local_ml_evaluation(st, cik=cik, as_of=as_of)

    # Independent, read-only market/peer comparison; cannot affect Guard.
    from .industry_vision_ui import render_local_industry_vision
    industry_raw = render_local_industry_vision(st, cik=cik, as_of=as_of)

    # Price data is user-provided; analysis is separate from audited SEC facts.
    from .market_reality_ui import render_local_market_reality
    market_raw = render_local_market_reality(st, cik=cik, as_of=as_of)

    if st.button("1단계 · 원본 대조 미리보기", key="kuodra_preview"):
        st.session_state.pop("kuodra_preview_receipt", None)
        try:
            raw = _uploaded_sources(uploads)
            preview = preview_uploaded_triplet(raw, request)
            st.session_state["kuodra_preview_receipt"] = preview
        except (ValueError, TypeError, OSError, KeyError, OverflowError,
                RecursionError):
            st.error("미리보기 차단: 입력 원본·기간·인용·식별자 검증 실패")
    receipt = st.session_state.get("kuodra_preview_receipt")
    if receipt is None:
        st.info("원본 3개(이력 파일은 선택)와 확인한 기간/인용을 입력한 후 미리보기를 실행하십시오.")
        return
    st.subheader("출처 메타데이터 대조 · 아직 감사 DB 기록 없음")
    st.json({
        "issuer_cik_operator_supplied": receipt["issuer_cik_operator_supplied"],
        "accession_operator_supplied": receipt["accession_operator_supplied"],
        "verification_status": receipt["verification_status"],
        "growth_pct_unverified": receipt["growth_pct_unverified"],
        "text_node_status": receipt["text_node_status"],
        "source_sha256": receipt["source_sha256"],
        "source_authenticated": False,
        "audit_written": False,
    })
    consent = st.checkbox("임시 로컬 SQLite 생성·검증 후 자동 삭제에 동의",
                          key="kuodra_ephemeral_consent", value=False)
    if st.button("2단계 · Guard 로컬 검증 실행", disabled=not consent,
                 key="kuodra_run", type="primary"):
        try:
            raw = _uploaded_sources(uploads)
            report, html = review_uploaded_triplet(
                raw, request, expected_preview=receipt, consent=consent,
            )
        except (ValueError, TypeError, OSError, KeyError, OverflowError,
                RecursionError):
            st.error("Guard 실행 차단: 미리보기 이후 원본/입력이 변경됐거나 감사 실패. "
                     "미리보기를 다시 수행하고 로컬 상태를 확인하십시오.")
            return
        # Optional Engine A attaches only AFTER existing source-pinned Guard.
        # No market observation may influence the SEC policy/audit decision.
        if market_raw is not None:
            try:
                from hashlib import sha256
                from .market_reality import (
                    parse_market_reality_json, analyze_market_reality,
                )
                market = analyze_market_reality(
                    parse_market_reality_json(market_raw),
                    expected_issuer_cik=cik, analysis_as_of=as_of,
                    sec_review=report, uploaded_sha256=sha256(market_raw).hexdigest(),
                )
                report["market_reality"] = market
                html = render_local_sec_html(report)
            except (ValueError, TypeError, OverflowError, RecursionError, KeyError):
                report.pop("market_reality", None)
                st.warning("시장자료 연결 검증에 실패하여 Engine A를 보고서에서 제외했습니다. "
                           "SEC·Guard 결과는 변경하지 않았습니다.")
        # The independent industry panel must match the *selected* SEC
        # issuer/period/revenue and the local CompanyFacts source SHA.
        # A malformed or conflicting optional panel cannot block Guard.
        from .three_engine_research import (
            bind_industry_to_sec, summarize_three_engines,
        )
        if industry_raw is not None:
            try:
                report["industry_vision"] = bind_industry_to_sec(report, industry_raw)
                html = render_local_sec_html(report)
            except (ValueError, TypeError, OverflowError, RecursionError, KeyError):
                report.pop("industry_vision", None)
                st.warning("Engine C와 선택 SEC 원본의 발행사·매출·기간·SHA가 "
                           "일치하지 않아 통합 보고서에서 제외했습니다.")
                html = render_local_sec_html(report)
        # This is NOT a new Guard decision and is not a calibrated score.
        report["three_engine_summary"] = summarize_three_engines(report)
        html = render_local_sec_html(report)
        st.success("로컬 Guard 완료 · 임시 SQLite 삭제 · 외부 출처 미인증")
        a, b, c = st.columns(3)
        a.metric("재무 주장", report["verification"]["status"])
        b.metric("Guard", report["guard"]["decision"])
        c.metric("로컬 감사 체인", "PASS")
        fin = report["verification"]
        if "market_reality" in report:
            m = report["market_reality"]
            st.subheader("Engine A · 시장 회귀 + SEC 실적 맥락")
            st.json({
                "regression_status": m["status"], "beta": m["beta"],
                "daily_ols_intercept_pct": m["regression_intercept_daily_pct"],
                "r_squared": m["r_squared"],
                "selected_10k_revenue_context": m["sec_revenue_context"],
                "source_authenticated": False, "market_bubble_proven": False,
                "audit_included": False, "guard_policy_modified": False,
            })
        st.subheader("KUODRA · A/B/C 3엔진 근거 요약")
        st.json(report["three_engine_summary"])
        if "industry_vision" in report:
            ind = report["industry_vision"]
            st.table([
                {"항목": "산업", "값": ind["industry"]},
                {"항목": "기업 매출 성장률 (%)", "값": ind["target"]["growth_pct_reported_input"]},
                {"항목": "업종 지표 성장률 (%)", "값": ind["industry_series"]["growth_pct_reported_input"] or "미확인"},
                {"항목": "기업 대비 산업 성장률 격차 (pp)", "값": ind["growth_gap_to_industry_pp"] or "미확인"},
                {"항목": "선택 SEC와 수치/해시 일치", "값": ind["sec_revenue_link"]["status"]},
            ])
        st.subheader("KUODRA · 비인증 재무 검산 근거")
        st.table([
            {"항목": "공시 접수번호", "값": report["issuer"]["accession"]},
            {"항목": "공시 인덱스 종류", "값": report["source"]["source_index_kind"]},
            {"항목": "US GAAP 수익 항목", "값": fin["revenue_concept"]},
            {"항목": "이전 기간 종료일", "값": fin["prior_period_end"]},
            {"항목": "이전 연매출 (USD)", "값": fin["prior_amount"]},
            {"항목": "현재 기간 종료일", "값": fin["current_period_end"]},
            {"항목": "현재 연매출 (USD)", "값": fin["current_amount"]},
            {"항목": "변화율 (Decimal, %)", "값": fin["growth_pct"]},
            {"항목": "검산 사유", "값": fin["reason_code"]},
        ])
        st.caption("회사 재무 사실이 아닌 사용자 입력 원본의 수치 비교 결과입니다. "
                   "Guard 승인 또는 거래 권한이 아닙니다.")
        # P43: describe the new Engine B as an unverified financial
        # reconciliation candidate, never a proven accounting violation.
        acc = report["accounting_integrity"]
        st.subheader("Engine B · 이익의 질과 현금흐름 괴리")
        st.table([
            {"항목": "순이익 (USD)", "값": acc["net_income_usd"] or "미확인"},
            {"항목": "영업현금흐름 (USD)", "값": acc["operating_cashflow_usd"] or "미확인"},
            {"항목": "순이익 - 영업현금흐름 (USD)", "값": acc["earnings_less_cash_usd"] or "미확인"},
            {"항목": "현금전환율 (%)", "값": acc["cash_to_net_income_pct"] or "미확인"},
            {"항목": "매출채권 - 매출 성장률 격차 (pp)",
             "값": acc["receivables_minus_revenue_growth_pp"] or "미확인"},
            {"항목": "재고 - 매출 성장률 격차 (pp)",
             "값": acc["inventory_minus_revenue_growth_pp"] or "미확인"},
        ])
        st.caption("관측된 괴리는 회계 부정·기업 가치의 확정 판정이 아닙니다. "
                   "공시 원문·발행사·수치 출처는 별도 인증이 필요합니다.")
        st.json({
            "guard_reasons": report["guard"]["reason_codes"],
            "balance_sheet": report["balance_sheet"]["status"],
            "share_capital": report["share_capital"]["status"],
            "capital_filing_watch": report["capital_filing_watch"]["status"],
            "cashflow": report["cashflow"]["status"],
            "accounting_integrity": acc["status"],
            "accounting_cash_signal": acc["earnings_cash_signal"],
            "accounting_working_capital_signals": acc["working_capital_signals"],
            "audit_hash": report["audit"]["event_hash"],
            "source_authenticated": False, "trade_executed": False,
            "audit_retained": False,
        })
        payload = json.dumps(
            report, ensure_ascii=False, sort_keys=True, indent=2,
            allow_nan=False,
        ).encode("utf-8")
        st.download_button(
            "오프라인 분석 보고서 JSON",
            data=payload, file_name="KUODRA_LOCAL_UNVERIFIED.json",
            mime="application/json", on_click="ignore",
        )
        st.download_button(
            "오프라인 분석 보고서 HTML",
            data=html, file_name="KUODRA_LOCAL_UNVERIFIED.html",
            mime="text/html", on_click="ignore",
        )
        st.caption("감사 SHA는 다운로드 보고서의 로컬 계산 증거이며 "
                   "삭제된 임시 DB의 영구 감사 보증서가 아닙니다.")
