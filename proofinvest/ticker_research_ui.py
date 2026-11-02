"""P100: opt-in localhost single-ticker SEC source discovery UI.

No HTTP at import/rerun. The primary auto-lookup requires both operator
enable switches, per-click acknowledgement, a genuine SEC contact and button.
No source/identity credentials or raw original are persisted in session_state.
This panel reports SOURCE STATUS, not automatic A/B/C/Guard/AI completion.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os

from .kuodra_local_workspace_ui import local_workspace_enabled
from .ticker_research_intake import (
    MAX_MAP_BYTES, MAX_SUBMISSIONS_BYTES, build_ticker_source_plan,
)
from .sec_api_client import _valid_contact
from .ticker_sec_transport import P105_SEC_403_HOLD

LIVE_GATE = "KUODRA_ENABLE_SEC_FETCH_UI"
MAX_ONLINE_GETS = 4


def ticker_search_enabled(st) -> bool:
    """Only an explicitly enabled loopback Streamlit server exposes this UI."""
    return local_workspace_enabled(st)


def _read_uploaded(upload, maximum: int) -> bytes:
    if (upload is None or type(getattr(upload, "size", None)) is not int
            or not 0 < upload.size <= maximum):
        raise ValueError("SOURCE_UPLOAD_SIZE_INVALID")
    data = upload.getvalue()
    if type(data) is not bytes or len(data) != upload.size:
        raise ValueError("SOURCE_UPLOAD_BYTE_MISMATCH")
    return data


def _display_receipt(st, result: dict, *, online: bool) -> None:
    """Only approved fields; never display raw SEC responses or contact value."""
    if (type(result) is not dict
            or result.get("source_authenticated") is not False
            or result.get("source_rights_verified") is not False
            or result.get("full_a_b_c_ready") is not False
            or result.get("trade_executed") is not False):
        st.error("출처 응답 계약이 맞지 않아 결과를 표시하지 않습니다.")
        return
    status = result.get("status")
    if status == "unavailable":
        st.warning("출처 확인 불가 · 추가 요청 중단 · 위험도/투자 의견은 계산하지 않습니다.")
        st.code(str(result.get("reason_code") or "UNAVAILABLE"), language="text")
        return
    expected = ("four_sec_responses_in_memory_unverified" if online
                else ("10k_source_plan_unverified", "source_plan_only_unverified"))
    if status not in (expected if isinstance(expected, tuple) else (expected,)):
        st.error("예상하지 못한 데이터 상태입니다. 출처 결과를 사용하지 않습니다.")
        return
    if online and (result.get("http_requests_attempted") != MAX_ONLINE_GETS
                   or result.get("live_sec_http_called") is not True
                   or result.get("raw_companyfacts_financial_values_verified") is not False):
        st.error("실제 수집 근거가 일치하지 않아 표시하지 않습니다.")
        return
    if not online and (result.get("network_requests") != 0
                       or result.get("live_data_retrieved") is not False):
        st.error("오프라인 데이터 상태가 일치하지 않습니다.")
        return

    st.success("SEC 출처 조회 단계 완료 · 출처 진위/이용 권리는 미검증")
    summary = {
        "ticker": result.get("ticker"),
        "cik": result.get("cik"),
        "company": result.get("sec_company_name") if not online else None,
        "selected_10k": (result.get("selected_10k_accession") if online else
                         (result.get("latest_10k") or {}).get("accession")),
        "as_of": (result.get("requested_as_of") if online else
                  result.get("as_of_requested")),
        "state": status,
        "source_authenticated": False,
        "source_rights_verified": False,
        "full_a_b_c_ready": False,
        "ai_interpretation_ready": False,
        "trade_executed": False,
    }
    st.json(summary)
    if online:
        # The backend already excludes raw bodies from its receipt.
        st.json({"source_urls": result.get("source_urls"),
                 "source_sha256": result.get("source_sha256"),
                 "source_bytes": result.get("source_bytes"),
                 "http_requests_attempted": MAX_ONLINE_GETS})
    else:
        st.json({"ticker_map_sha256": result.get("ticker_map_sha256"),
                 "sec_submissions_url": result.get("sec_submissions_url"),
                 "sec_companyfacts_url": result.get("sec_companyfacts_url"),
                 "latest_10k": result.get("latest_10k")})
    st.info("후속 Engine A/B/C·Guard 분석에 필요한 가격·산업·경쟁사 자료와 "
            "재무 사실 대조는 아직 연결하지 않았습니다. 자동 투자 추천이 아닙니다.")


def render_single_ticker_search(st) -> None:
    if not ticker_search_enabled(st):
        st.error("종목 검색은 로컬 서버에서만 활성화됩니다.")
        return

    st.title("KUODRA · 종목 하나 검색")
    st.caption("티커 1개 → SEC 기업 CIK 확인 → 공시 목록 → CompanyFacts → "
               "10-K 원문. 대규모 종목 추천·전체 시장 크롤링은 제공하지 않습니다.")
    ticker = st.text_input(
        "미국 주식 티커 (예: NVDA)", value="NVDA", max_chars=20,
        key="kuodra_p100_ticker",
    )
    as_of = st.text_input(
        "조회 기준일 (YYYY-MM-DD)",
        value=datetime.now(timezone.utc).date().isoformat(),
        max_chars=10, key="kuodra_p100_as_of",
    )

    enabled = os.environ.get(LIVE_GATE) == "1" and not P105_SEC_403_HOLD
    if P105_SEC_403_HOLD:
        st.warning("SEC P105 HTTP 403 확인: 기존 수집 경로의 재요청은 중단되었습니다. "
                   "환경변수와 화면 동의만으로 재개할 수 없습니다. "
                   "로컬 자료 출처 계획 확인은 계속 사용할 수 있습니다.")
    elif not enabled:
        st.warning("SEC 네트워크 검색: 관리자 승인 대기. "
                   "별도 환경설정 KUODRA_ENABLE_SEC_FETCH_UI=1 없이는 요청할 수 없습니다.")
    st.subheader("공식 SEC 자동 조회 (명시적 승인 필요)")
    st.caption("한 종목만, 공식 sec.gov/data.sec.gov에 최대 4회 HTTPS GET. "
               "User-Agent 연락처와 개별 동의가 필요합니다. "
               "SEC 403/429 발생 시 우회·반복 요청하지 않습니다.")
    user_agent = st.text_input(
        "SEC 요청 User-Agent (실제 연락처 포함)",
        value="", type="password", max_chars=160,
        key="kuodra_p100_sec_contact",
    )
    accepted = st.checkbox(
        "이 종목에 한해 SEC 공식 서버 최대 4회 GET 요청에 동의합니다",
        value=False, key="kuodra_p100_approve_four",
    )
    # No HTTP from rerun, invalid date, stale UI upload, ordinary preview
    # or disabled button. A real click is a distinct user authorization.
    from .ticker_research_intake import _TICKER, _date
    valid = False
    try:
        key = ticker.strip().upper() if type(ticker) is str else ""
        valid = (bool(_TICKER.fullmatch(key)) and
                 _date(as_of) <= datetime.now(timezone.utc).date())
    except (TypeError, ValueError):
        pass
    can_fetch = bool(enabled and accepted and valid and _valid_contact(user_agent))
    # Optional developer/source-contract fixtures until lawful price and peer
    # providers have been approved; never required for routine ticker input.
    st.caption("Engine A/C 자료: 공급자 연동 검증 대기. 아래 파일은 개발용 "
               "소스 계약 검증이며 자동 수집을 대체하지 않습니다.")
    market_source = st.file_uploader(
        "주가·지수 시계열 JSON (개발·검증용 선택)",
        type=["json"], key="kuodra_p104_market_json",
    )
    industry_source = st.file_uploader(
        "산업·경쟁사 비교 JSON (개발·검증용 선택)",
        type=["json"], key="kuodra_p104_industry_json",
    )
    if st.button("SEC 원문 4종 자동 수집 실행", key="kuodra_p100_live",
                 disabled=not can_fetch):
        if not can_fetch:
            st.error("SEC 수집 차단: 승인·연락처·티커·기준일 확인 필요")
            return
        from .ticker_sec_transport import collect_ticker_sec_sources
        result, raw_sources = collect_ticker_sec_sources(
            ticker=ticker, as_of=as_of, user_agent=user_agent,
            allow_network=True, acknowledge_four_requests=True,
        )
        # P101: match exact SHA-pinned four-source SEC receipt and a single
        # 10-K's annual CompanyFacts before displaying descriptive figures.
        # This is NOT an original HTML text assertion or Engine B/Guard review.
        from .ticker_sec_financial_bridge import inspect_collected_annual_revenue
        revenue = inspect_collected_annual_revenue(result, raw_sources)
        from .ticker_sec_original_guard_preview import inspect_original_guard_preview
        original_preview = inspect_original_guard_preview(
            result, raw_sources, expected_revenue=revenue,
        )
        from .ticker_market_industry_bridge import evaluate_ticker_a_c
        try:
            market_data = (_read_uploaded(market_source, 131072)
                           if market_source is not None else None)
            industry_data = (_read_uploaded(industry_source, 65536)
                             if industry_source is not None else None)
            supplementary = evaluate_ticker_a_c(
                result, raw_sources,
                market_json=market_data, industry_json=industry_data,
            )
        except (TypeError, ValueError, OSError, RecursionError):
            supplementary = None
        # No raw file bytes in state, downloads, JSON, HTML or long-lived cache.
        if raw_sources is not None:
            raw_sources.clear()
        _display_receipt(st, result, online=True)
        if result.get("status") == "four_sec_responses_in_memory_unverified":
            st.subheader("SEC 같은 10-K 연간 매출 검산 (부분 분석)")
            if revenue.get("status") == "REVENUE_CALCULATED_UNVERIFIED":
                st.json({
                    "ticker": revenue["ticker"],
                    "cik": revenue["issuer_cik"],
                    "accession": revenue["accession"],
                    "current_end": revenue["current_end"],
                    "prior_end": revenue["prior_end"],
                    "current_usd": revenue["current_usd"],
                    "prior_usd": revenue["prior_usd"],
                    "revenue_growth_pct_unverified": revenue["growth_pct"],
                    "companyfacts_sha256": revenue["companyfacts_sha256"],
                    "original_10k_sha256": revenue["original_10k_sha256"],
                    "source_authenticated": False,
                    "original_10k_text_verified": False,
                    "engine_b_full_ready": False,
                    "guard_executed": False,
                })
                st.warning("같은 공시의 매출 산술만 확인했습니다. 출처 독립 인증·"
                           "회계 착시 위험·시장/산업 전망은 아직 완료되지 않았습니다.")
                st.subheader("10-K 원문 교차확인 · Guard 정책 미리보기")
                st.json({
                    "original_context_state": original_preview["status"],
                    "reason_code": original_preview["reason_code"],
                    "ixbrl_status": original_preview["ixbrl_status"],
                    "ixbrl_reason": original_preview["ixbrl_reason"],
                    "dei_status": original_preview["dei_status"],
                    "dei_reason": original_preview["dei_reason"],
                    "guard_policy_preview": original_preview["guard_preview"],
                    "original_to_accession_authenticated": False,
                    "guard_executed": False, "audit_written": False,
                    "trade_executed": False,
                })
                st.caption("Guard 규칙 미리보기는 감사 실행·사람 승인·투자 허가가 아닙니다. "
                           "원본 iXBRL 문맥 일치도 SEC 원본 진위 인증이 아닙니다.")
                st.subheader("Engine A/C · 동일 종목 출처 비교 (부분 분석)")
                if supplementary is not None:
                    st.json({
                        "engine_a": supplementary["engine_a"],
                        "engine_c": supplementary["engine_c"],
                        "source_authenticated": False,
                        "source_rights_verified": False,
                        "all_three_engines_ready": False,
                        "guard_executed": False,
                        "trade_executed": False,
                    })
                else:
                    st.warning("추가 시장·산업 자료의 형식 또는 크기를 확인할 수 없습니다.")
                st.caption("공급자·이용권리 및 과거 데이터 기준시점 미검증. "
                           "분석이 있는 경우에도 확정된 거품·사기·미래 전망으로 해석하지 않습니다.")
            else:
                st.warning("연간 매출 검산 불가 · 누락/모순은 0이나 안전 판정으로 대체하지 않습니다.")
                st.code(revenue.get("reason_code", "UNAVAILABLE"), language="text")
    elif not valid:
        st.error("유효한 티커와 오늘(UTC) 이전의 조회 기준일을 입력하십시오.")

    st.subheader("로컬 공시 목록으로 출처 계획 확인 (개발·검증용)")
    st.caption("이 부분은 자동 수집의 대체 사용 경로가 아닌 오프라인 검증용입니다. "
               "사용자가 전체 시장 자료를 준비할 필요는 없습니다.")
    ticker_map = st.file_uploader(
        "SEC ticker 목록 JSON (로컬 선택)",
        type=["json"], key="kuodra_p100_ticker_map",
    )
    submissions = st.file_uploader(
        "선택 기업 SEC submissions.json (선택)",
        type=["json"], key="kuodra_p100_submissions",
    )
    companyfacts_local = st.file_uploader(
        "CompanyFacts JSON (로컬 검산용 선택)",
        type=["json"], key="kuodra_p116_companyfacts",
    )
    original_local = st.file_uploader(
        "동일 10-K 원문 HTML/XHTML (로컬 문맥 검토용 선택)",
        type=["html", "htm", "xhtml", "xml", "txt"],
        key="kuodra_p116_original",
    )
    if st.button("로컬 원본으로 출처 계획 확인", key="kuodra_p100_offline",
                 disabled=ticker_map is None or not valid):
        try:
            mapped = _read_uploaded(ticker_map, MAX_MAP_BYTES)
            filings = (_read_uploaded(submissions, MAX_SUBMISSIONS_BYTES)
                       if submissions is not None else None)
            result = build_ticker_source_plan(
                ticker=ticker, ticker_map=mapped, submissions=filings,
                as_of=as_of,
            )
        except (ValueError, TypeError, OSError, RecursionError):
            st.warning("로컬 자료의 형식·크기·기업 식별 정보를 확인할 수 없습니다.")
            return
        _display_receipt(st, result, online=False)
        # P116: no SEC HTTP. With all four uploaded files, reuse source-SHA-
        # bound arithmetic and read-only Guard policy preview. A local file
        # is never claimed to be SEC-authenticated even if its URL looks valid.
        if companyfacts_local is None and original_local is None:
            return
        if submissions is None or companyfacts_local is None or original_local is None:
            st.warning("로컬 매출 검산에는 ticker 목록, submissions, "
                       "CompanyFacts, 같은 10-K 원문 모두 필요합니다.")
            return
        raw_local = None
        try:
            from .ticker_sec_financial_bridge import _LIMITS
            from .ticker_local_workflow import run_local_ticker_workflow

            raw_local = {
                "ticker_map": mapped,
                "submissions": filings,
                "companyfacts": _read_uploaded(
                    companyfacts_local, _LIMITS["companyfacts"]),
                "original_10k": _read_uploaded(
                    original_local, _LIMITS["original_10k"]),
            }
            market_data = (_read_uploaded(market_source, 131072)
                           if market_source is not None else None)
            industry_data = (_read_uploaded(industry_source, 65536)
                             if industry_source is not None else None)
            workflow = run_local_ticker_workflow(
                ticker=ticker, as_of=as_of, sources=raw_local,
                market_json=market_data, industry_json=industry_data,
            )
            st.subheader("로컬 분석 단계별 실행 기록 · AI/거래 미실행")
            st.json({
                "mode": workflow["mode"], "status": workflow["status"],
                "reason_code": workflow["reason_code"],
                "next_action": workflow["next_action"],
                "tool_calls_executed": workflow["tool_calls_executed"],
                "tool_budget": workflow["tool_budget"],
                "tool_trace": workflow["tool_trace"],
                "ai_agent_executed": False, "network_requests": 0,
                "guard_executed": False, "trade_executed": False,
                "official_contest_submission": False,
            })
            if workflow["status"] != "READY_FOR_HUMAN_REVIEW_UNVERIFIED":
                st.warning("로컬 원본 분석이 중단됐습니다. 차단 단계를 확인해 주세요.")
                st.code(workflow["reason_code"], language="text")
                return
            local_receipt = workflow["receipt"]
            revenue = workflow["revenue"]
            original_check = workflow["original"]
            supplementary = workflow["supplementary"]
            st.subheader("로컬 SEC 자료 검산 · 미인증 결과")
            st.json({
                "source_mode": "LOCAL_USER_FILES_NOT_SEC_AUTHENTICATED",
                "ticker": local_receipt["ticker"],
                "cik": local_receipt["cik"],
                "accession": local_receipt["selected_10k_accession"],
                "input_mode": revenue.get("input_mode"),
                "financial_status": revenue.get("status"),
                "growth_pct_unverified": revenue.get("growth_pct"),
                "original_status": original_check.get("status"),
                "guard_policy_preview": original_check.get("guard_preview"),
                "engine_a": supplementary["engine_a"]["status"],
                "engine_c": supplementary["engine_c"]["status"],
                "source_authenticated": False,
                "source_rights_verified": False,
                "guard_executed": False,
                "audit_written": False,
                "ai_agent_executed": False,
                "trade_executed": False,
                "http_requests_attempted": 0,
            })
            st.warning("로컬 업로드 자료의 진위·제공 권한은 확인되지 않았습니다. "
                       "Guard는 정책 미리보기이며 투자 실행이나 APPROVE가 아닙니다.")
            # Local download is explicitly triggered by the user. No raw
            # original, contact, HTML or token enters this bounded report.
            if (revenue.get("status") == "REVENUE_CALCULATED_UNVERIFIED"
                    and type(original_check.get("guard_preview")) is dict):
                from .ticker_local_report import report_json_bytes
                local_report = workflow["report"]
                st.subheader("출처·이용권리 사전 점검 · 외부 사용 차단")
                st.json({
                    "status": local_report["source_rights_ledger"]["status"],
                    "sources": [{
                        "role": asset["role"],
                        "raw_sha256": asset["raw_sha256"],
                        "origin_authenticated": False,
                        "external_display_rights_verified": False,
                        "redistribution_rights_verified": False,
                    } for asset in local_report["source_rights_ledger"]["sources"]],
                    "contest_public_submission_allowed": False,
                    "external_sharing_allowed": False,
                    "commercial_reuse_allowed": False,
                })
                st.caption("원본 해시는 파일 무결성 식별자일 뿐입니다. "
                           "외부 공유·대회 공개·상용 재사용 권한은 확인되지 않았습니다.")
                st.metric("연매출 성장률 (로컬 미인증)",
                          str(revenue["growth_pct"]) + "%")
                st.metric("Guard 정책 미리보기 (미실행)",
                          local_report["guard_policy_preview"])
                st.download_button(
                    "로컬 4종 출처 검산 보고서 JSON (미인증)",
                    data=report_json_bytes(local_report),
                    file_name="kuodra-local-four-source-UNVERIFIED.json",
                    mime="application/json",
                    key="kuodra_p117_local_report",
                )
        except (ValueError, TypeError, KeyError, OSError, RecursionError):
            st.warning("로컬 파일 크기·형식 또는 교차검증에 실패했습니다.")
        finally:
            if type(raw_local) is dict:
                raw_local.clear()
