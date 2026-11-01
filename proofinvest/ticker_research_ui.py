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

    enabled = os.environ.get(LIVE_GATE) == "1"
    if not enabled:
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
        # No raw file bytes in state, downloads, JSON, HTML or long-lived cache.
        if raw_sources is not None:
            raw_sources.clear()
        _display_receipt(st, result, online=True)
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
