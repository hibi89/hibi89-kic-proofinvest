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


_P153_LINKED_CACHE_KEY = "kuodra_p153_linked_report_cache"


def _p154_pair_source_fingerprint(*, ticker, as_of, receipt,
                                  market_json, industry_json) -> str:
    """One paid-attempt key per exact independently reviewed source set.

    Pure local metadata hashing: no original bytes, token or provider URL
    enters session_state. Changing a 10-K, issuer, ticker, as-of or optional
    A/C input permits a NEW separately clicked request while an unchanged
    set cannot trigger another paid request.
    """
    from hashlib import sha256
    import json
    import re

    if (type(ticker) is not str or type(as_of) is not str
            or type(receipt) is not dict):
        raise ValueError("PAIR_FINGERPRINT_IDENTITY_INVALID")
    hashes = receipt.get("source_sha256")
    expected = {"ticker_map", "submissions", "companyfacts", "original_10k"}
    if (type(hashes) is not dict or set(hashes) != expected
            or any(type(v) is not str or re.fullmatch(
                r"[0-9a-f]{64}", v) is None for v in hashes.values())):
        raise ValueError("PAIR_FINGERPRINT_SOURCE_HASHES_INVALID")
    for optional in (market_json, industry_json):
        if optional is not None and type(optional) is not bytes:
            raise ValueError("PAIR_FINGERPRINT_OPTIONAL_INVALID")
    identity = {
        "schema": "kuodra.p154.explicit-paid-attempt.v1",
        "ticker": ticker,
        "as_of": as_of,
        "cik": receipt.get("cik"),
        "accession": receipt.get("selected_10k_accession"),
        "sources": hashes,
        "market_sha256": (
            sha256(market_json).hexdigest() if market_json is not None else None),
        "industry_sha256": (
            sha256(industry_json).hexdigest() if industry_json is not None else None),
    }
    if (type(identity["cik"]) is not str
            or re.fullmatch(r"[0-9]{10}", identity["cik"]) is None
            or type(identity["accession"]) is not str
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}",
                            identity["accession"]) is None):
        raise ValueError("PAIR_FINGERPRINT_FILING_INVALID")
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _p153_uploaded_input_digest(
    *, ticker, as_of, operator_zip, ticker_map, submissions,
    companyfacts_local, original_local, market_source, industry_source,
) -> str:
    """Bind a redacted receipt to exact user uploads; never retain their bytes.

    Local read/hash only. The raw files are NOT cached in Streamlit session
    state; the digest is a session-local invalidation key, not SEC provenance.
    """
    from hashlib import sha256
    from .operator_sec_zip import _MAX_ZIP_BYTES
    from .ticker_sec_financial_bridge import _LIMITS

    individual = (ticker_map, submissions, companyfacts_local, original_local)
    if operator_zip is not None:
        if any(item is not None for item in individual):
            raise ValueError("ZIP_AND_FOUR_SOURCE_CONFLICT")
        fields = (("operator_zip", operator_zip, _MAX_ZIP_BYTES),)
    else:
        if any(item is None for item in individual):
            raise ValueError("FOUR_SOURCE_INPUT_REQUIRED")
        fields = (
            ("ticker_map", ticker_map, MAX_MAP_BYTES),
            ("submissions", submissions, MAX_SUBMISSIONS_BYTES),
            ("companyfacts", companyfacts_local, _LIMITS["companyfacts"]),
            ("original_10k", original_local, _LIMITS["original_10k"]),
        )
    fields += (
        ("optional_market", market_source, 131072),
        ("optional_industry", industry_source, 65536),
    )
    if type(ticker) is not str or type(as_of) is not str:
        raise ValueError("TICKER_OR_CUTOFF_INVALID")
    digest = sha256(b"kuodra.p153.private-session-upload-binding.v1\x00")
    for token in (ticker, as_of):
        encoded = token.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    for role, upload, maximum in fields:
        digest.update(role.encode("ascii") + b"\x00")
        if upload is None:
            digest.update(b"MISSING\x00")
        else:
            raw = _read_uploaded(upload, maximum)
            digest.update(len(raw).to_bytes(8, "big"))
            digest.update(sha256(raw).digest())
    return digest.hexdigest()


def _p153_render_cached_linked_report(st, *, ticker, as_of, approved,
                                     operator_zip, ticker_map, submissions,
                                     companyfacts_local, original_local,
                                     market_source, industry_source) -> None:
    """Display only a previously validated 16 KiB redacted export on rerun.

    No vendor request, local raw-byte storage, automatic regeneration or
    source-rights elevation. Any changed input revokes this download.
    """
    state = getattr(st, "session_state", None)
    if state is None:
        return
    from .linked_report_session_cache import (
        clear_linked_reports, discard_linked_report, find_linked_report,
    )
    if not approved:
        clear_linked_reports(state)
        return
    fingerprint = None
    try:
        fingerprint = _p153_uploaded_input_digest(
            ticker=ticker, as_of=as_of, operator_zip=operator_zip,
            ticker_map=ticker_map, submissions=submissions,
            companyfacts_local=companyfacts_local, original_local=original_local,
            market_source=market_source, industry_source=industry_source,
        )
        latest = state.get(_P153_LINKED_CACHE_KEY)
        # The P153 latest record has precedence, including when corrupted:
        # do not bypass a tampered current record with a historical copy.
        if (type(latest) is dict and latest.get("fingerprint") == fingerprint):
            cached = latest
        else:
            cached = find_linked_report(state, fingerprint)
            if cached is None:
                state.pop(_P153_LINKED_CACHE_KEY, None)
                return
        if (type(cached) is not dict
                or set(cached) != {"fingerprint", "data"}
                or cached.get("fingerprint") != fingerprint
                or type(cached.get("data")) is not bytes
                or not 0 < len(cached["data"]) <= 16384):
            raise ValueError("CACHED_LINKED_RECEIPT_INVALID")
        from .ticker_market_pair_evidence import linked_evidence_json_bytes
        import json
        report = json.loads(cached["data"].decode("utf-8"))
        if (type(report) is not dict
                or report.get("issuer", {}).get("ticker") != ticker
                or report.get("issuer", {}).get("as_of") != as_of
                or linked_evidence_json_bytes(report) != cached["data"]):
            raise ValueError("CACHED_LINKED_RECEIPT_REVALIDATION_FAILED")
    except (ValueError, TypeError, KeyError, AttributeError,
            OverflowError, UnicodeError, RecursionError):
        if fingerprint is None:
            state.pop(_P153_LINKED_CACHE_KEY, None)
        else:
            discard_linked_report(state, fingerprint)
        return
    st.subheader("이전 검산 완료 · 통합 증거 JSON (현재 세션에서만 유지)")
    st.json({
        "status": report["status"],
        "ticker": ticker, "as_of": as_of,
        "matched_period_start": report["premium_engine_a"]["matched_period_start"],
        "matched_period_end": report["premium_engine_a"]["matched_period_end"],
        "evidence_sha256": report["evidence_sha256"],
        "guard_policy_preview": "HOLD",
        "source_authenticated": False, "source_rights_verified": False,
        "external_sharing_allowed": False, "trade_executed": False,
        "provider_requests_on_rerun": 0,
    })
    st.download_button(
        "통합 검산 근거 JSON (로컬 전용 · 미인증)",
        data=cached["data"],
        file_name="kuodra-local-market-linked-UNVERIFIED.json",
        mime="application/json", key="kuodra_p143_linked_market_report",
    )
    _render_p158_source_linked_interpretation(st, report)


def _render_p158_source_linked_interpretation(
        st, linked: dict, *, source_replay: dict | None = None) -> None:
    """Display deterministic review notes only for strict validated evidence.

    The caller must have independently replayed the original source inputs.
    The explanation is descriptive, not an LLM execution or investment advice.
    """
    try:
        from .ticker_evidence_explanation import (
            explain_linked_market_receipt, explanation_json_bytes,
        )
        interpretation = explain_linked_market_receipt(linked)
        safe_json = explanation_json_bytes(interpretation)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError, UnicodeError):
        st.warning("A/B/C 근거 해석이 불가능합니다. 원본 검산 JSON은 유지됩니다.")
        return
    st.subheader("Engine A/B/C · 출처 연결 설명 (규칙 기반 · AI 미실행)")
    st.json({
        "ticker": interpretation["issuer"]["ticker"],
        "filing_date": interpretation["issuer"]["filing_date"],
        "as_of": interpretation["issuer"]["as_of"],
        "linked_evidence_sha256": interpretation["linked_evidence_sha256"],
        "source_hashes": interpretation["source_hashes"],
        "findings": interpretation["findings"],
        "guard_policy_preview": "HOLD",
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "investment_recommendation": False,
        "trade_executed": False,
    })
    st.download_button(
        "A/B/C 출처 연결 설명 JSON (로컬 전용 · 규칙 기반)",
        data=safe_json,
        file_name="kuodra-local-evidence-interpretation-UNVERIFIED.json",
        mime="application/json",
        key="kuodra_p158_explanation_json",
    )
    # P160: an initial approved analysis may independently replay the
    # complete packet against the original four SEC and paired price inputs.
    # Cached reruns have no original market receipts and MUST NOT pretend
    # a new independent source replay occurred.
    if source_replay is not None:
        st.json({
            "packet_source_replay_status": source_replay["status"],
            "packet_source_replay_reason": source_replay["reason_code"],
            "local_source_replay_verified": source_replay["local_source_replay_verified"],
            "market_math_recomputed": source_replay["market_math_recomputed"],
            "source_authenticated": False,
            "source_rights_verified": False,
            "network_requests": 0,
        })
        if source_replay["status"] != "PASS_UNVERIFIED_ORIGIN":
            st.warning("패키지 원본 교차검증 실패: 단일 패키지 다운로드 차단. "
                       "기존 개별 검산 자료는 유지됩니다.")
            return
    else:
        st.caption("캐시 재열람: 패키지 내부 무결성만 검사합니다. "
                   "원본 SEC·시장 입력 재검산은 이 실행에서 수행하지 않습니다.")
    # P159: one offline review file for evidence + derived explanation.
    # Both parts are internally checked. This is not provider authentication
    # and does not change the original report or allow external sharing.
    try:
        from .ticker_review_packet import (
            build_review_packet, review_packet_json_bytes,
            inspect_review_packet_bytes,
        )
        packet = build_review_packet(linked)
        packet_bytes = review_packet_json_bytes(packet)
        internal_check = inspect_review_packet_bytes(packet_bytes)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError, UnicodeError):
        st.warning("단일 검토 패키지 구성 실패: 기존 근거·설명 다운로드는 유지됩니다.")
    else:
        st.subheader("A/B/C + Guard · 단일 로컬 검토 패키지 (출처 미인증)")
        st.json({
            "status": internal_check["status"],
            "packet_sha256": internal_check["packet_sha256"],
            "linked_evidence_sha256": internal_check["linked_evidence_sha256"],
            "ticker": internal_check["ticker"],
            "guard_policy_preview": "HOLD",
            "source_authenticated": False,
            "source_rights_verified": False,
            "external_sharing_allowed": False,
            "trade_executed": False,
        })
        st.download_button(
            "A/B/C 근거+설명 통합 검토 JSON (로컬 전용 · 미인증)",
            data=packet_bytes,
            file_name="kuodra-a-b-c-review-packet-UNVERIFIED.json",
            mime="application/json",
            key="kuodra_p159_review_packet",
        )



def _render_p164_downloaded_packet_inspector(st) -> None:
    """Independently inspect a downloaded review JSON on localhost.

    This checks strict canonical bytes, schemas, arithmetic self-consistency
    and packet digests. It never fetches, caches, uploads externally or
    claims the separate original SEC / market-source replay was repeated.
    """
    st.subheader("다운로드한 A/B/C 검토 패키지 재검사 (오프라인)")
    st.caption("로컬 JSON의 내부 무결성만 확인합니다. 원본 SEC·주가·지수 "
               "재검산이나 발행자 인증·재배포 권한 검증이 아닙니다.")
    selected = st.file_uploader(
        "이전에 다운로드한 검토 패키지 JSON (28KiB 이하)",
        type=["json"], key="kuodra_p164_packet_file",
    )
    clicked = st.button(
        "다운로드 패키지 무결성 검사 (네트워크 없음)",
        key="kuodra_p164_packet_inspect",
        disabled=selected is None,
    )
    _render_p166_original_source_replay(st, selected)
    if not clicked:
        return
    try:
        from .ticker_review_packet import inspect_review_packet_bytes
        checked = inspect_review_packet_bytes(_read_uploaded(selected, 28672))
    except (ValueError, TypeError, AttributeError, OverflowError,
            RecursionError, UnicodeError):
        st.warning("검토 패키지 크기·형식·내부 증거 연결 또는 무결성 검사 실패. "
                   "원본 내용을 신뢰하거나 외부에 공유하지 마십시오.")
        st.code("REVIEW_PACKET_OFFLINE_INTEGRITY_FAILED", language="text")
        return
    st.success("검토 패키지 내부 무결성 PASS (원본·공급자 인증 아님)")
    st.metric("검사 대상 종목 (미인증)", checked["ticker"])
    st.json({
        "status": checked["status"],
        "ticker": checked["ticker"],
        "packet_sha256": checked["packet_sha256"],
        "linked_evidence_sha256": checked["linked_evidence_sha256"],
        "guard_policy_preview": "HOLD",
        "packet_internal_integrity_passed": True,
        "original_sources_replayed_in_this_check": False,
        "market_math_independently_recomputed_in_this_check": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_sharing_allowed": False,
        "network_requests": 0,
        "trade_executed": False,
    })
    st.warning("내부 무결성 통과는 공급자 원문 인증, 독립적인 원본 재검산, "
               "사용권리 또는 투자·제출 승인이 아닙니다.")




def _render_p166_original_source_replay(st, packet_upload) -> None:
    """Opt-in full offline SEC+market original replay, no provider requests.

    All original bytes are read only when the human clicks verification;
    nothing is written, cached, exported, or sent to a vendor. The mandatory
    four SEC-shape files and two price-response bodies must be supplied again.
    A/C inputs are optional only when absent from the downloaded packet.
    """
    if not st.checkbox(
        "원본 SEC·주가·NDX 파일로 독립 산술 재검산 펼치기 (로컬 전용)",
        value=False, key="kuodra_p166_replay_mode",
    ):
        return
    st.caption("이 절차는 기존 검토 패키지와 원본 6종을 별도로 비교하고 "
               "A/B/C·Guard HOLD의 로컬 계산을 다시 수행합니다. "
               "파일을 외부 제공자에게 보내거나 이용권리를 확인하지 않습니다.")
    role_inputs = (
        ("ticker_map", "원본 SEC ticker_map JSON (재검산)", ["json"]),
        ("submissions", "원본 SEC submissions JSON (재검산)", ["json"]),
        ("companyfacts", "원본 SEC CompanyFacts JSON (재검산)", ["json"]),
        ("original_10k", "원본 SEC 10-K HTML (재검산)",
         ["html", "htm", "xhtml", "xml", "txt"]),
    )
    original_files = {}
    for role, label, extension in role_inputs:
        original_files[role] = st.file_uploader(
            label, type=extension, key="kuodra_p166_" + role,
        )
    stock_file = st.file_uploader(
        "종목 일별 응답 JSON 원본 (재검산)",
        type=["json"], key="kuodra_p166_stock",
    )
    index_file = st.file_uploader(
        "실제 Nasdaq-100 NDX 일별 응답 JSON 원본 (재검산)",
        type=["json"], key="kuodra_p166_index",
    )
    market_file = st.file_uploader(
        "기존 Engine A 로컬 입력 JSON (패키지에 포함된 경우 필수)",
        type=["json"], key="kuodra_p166_market",
    )
    industry_file = st.file_uploader(
        "기존 Engine C 로컬 입력 JSON (패키지에 포함된 경우 필수)",
        type=["json"], key="kuodra_p166_industry",
    )
    ready = (packet_upload is not None
             and all(x is not None for x in original_files.values())
             and stock_file is not None and index_file is not None)
    clicked = st.button(
        "원본 SEC + 주가·NDX A/B/C 독립 재계산 (네트워크 없음)",
        disabled=not ready, key="kuodra_p166_replay_click",
    )
    if not clicked:
        return
    try:
        from .ticker_sec_financial_bridge import _LIMITS as sec_limits
        from .ticker_review_source_replay import (
            replay_review_packet_from_original_bytes,
        )
        raw = {
            role: _read_uploaded(original_files[role], sec_limits[role])
            for role in original_files
        }
        outcome = replay_review_packet_from_original_bytes(
            _read_uploaded(packet_upload, 28672),
            sources=raw,
            stock_raw=_read_uploaded(stock_file, 262144),
            index_raw=_read_uploaded(index_file, 8388608),
            market_json=(_read_uploaded(market_file, 131072)
                         if market_file is not None else None),
            industry_json=(_read_uploaded(industry_file, 65536)
                           if industry_file is not None else None),
        )
    except (ValueError, TypeError, KeyError, AttributeError, OSError,
            OverflowError, RecursionError, UnicodeError):
        st.warning("원본 파일의 크기·형식 또는 무결성 확인 실패. 분석을 승인하지 않습니다.")
        st.code("ORIGINAL_BYTES_OR_FORMAT_INVALID", language="text")
        return
    if outcome.get("status") != "PASS_UNVERIFIED_ORIGIN":
        st.warning("원본 바이트·출처 식별자·기간 또는 산술 재검산 불일치. "
                   "패키지를 독립 검증 완료로 취급하지 않습니다.")
        st.code(outcome.get("reason_code", "SOURCE_REPLAY_FAILED"),
                language="text")
        return
    st.success("원본 6종 해시 + SEC/Engine A/B/C 산술 재계산 PASS (출처 미인증)")
    st.json({
        "ticker": outcome["ticker"],
        "packet_sha256": outcome["packet_sha256"],
        "status": outcome["status"],
        "packet_internal_integrity_passed": True,
        "original_byte_hashes_matched": True,
        "local_source_replay_verified": True,
        "market_math_recomputed": True,
        "guard_policy_preview": "HOLD",
        "source_authenticated": False,
        "source_rights_verified": False,
        "market_vintage_authenticated": False,
        "external_sharing_allowed": False,
        "trade_executed": False,
        "network_requests": 0,
    })
    st.warning("원본 업로드와 재계산 결과는 공급자 진위·시점·법적 재사용권·"
               "투자 권고·거래·대회 제출 승인을 증명하지 않습니다.")


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
    run_sec_clicked = st.button(
        "SEC 원문 4종 자동 수집 실행", key="kuodra_p100_live",
        disabled=not can_fetch,
    )
    _render_p164_downloaded_packet_inspector(st)
    from .ticker_local_model_triage_ui import render_local_model_triage_ui
    render_local_model_triage_ui(st)
    from .ticker_local_numeric_claim_ui import render_local_numeric_claim_ui
    render_local_numeric_claim_ui(st)
    if run_sec_clicked:
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

    # P140: explicit opt-in provider panel. Never runs in a rerender.
    from .market_provider_alpha_vantage import render_daily_price_panel
    render_daily_price_panel(st, ticker=key, as_of=as_of, ticker_valid=valid)

    # P125: show the verified PUBLIC terms blockers in the exact on-demand
    # user flow. This is never a vendor HTTP/API call or entitlement grant.
    if st.button(
        "시장 데이터 이용권한 사전 점검 (네트워크 없음)",
        key="kuodra_p125_license_preflight",
    ):
        from .provider_rights_preflight import evaluate_provider
        st.subheader("실사용 데이터 공급자 이용권한 · 아직 미확인")
        st.warning(
            "SEC P105 403 재요청 금지. 시장 지수의 무료 조회/가격표/시계열 공개는 "
            "심사 공개, AI 처리, 재배포, 상용 대시보드 이용 허가가 아닙니다."
        )
        results = [
            evaluate_provider(provider=name, intended_use="contest_judge_demo")
            for name in ("massive", "twelve_data", "fred", "nasdaq_gids")
        ]
        st.json({
            "schema": "kuodra.p125-market-and-sec-license-gaps.v1",
            "status": "BLOCKED_NO_LICENSED_LIVE_E2E_YET",
            "sec_access": "P105_SEC_ACCESS_DENIED_403_NO_RETRY",
            "sec_http_attempted": False,
            "source_legal_review_scope": "PUBLIC_TERMS_NOT_USER_ENTITLEMENTS",
            "ndx_data_authorized": False,
            "judge_demo_external_display_authorized": False,
            "ai_processing_authorized": False,
            "owner_approved_paid_services": False,
            "providers": results,
            "next_action": "OBTAIN_OWNER_APPROVAL_AND_LICENSE_SCOPE_BEFORE_INTEGRATION",
        })
    # P126: a genuine issuer-reported historical *manual* case exists
    # independently of the unavailable automatic SEC/data-provider path.
    # No bytes are fetched and no claim of official-source authentication.
    if isinstance(ticker, str) and ticker.strip().upper() == "AAPL":
        st.subheader("Apple FY2025 · 공개공시 수동검산 (과거 사례)")
        st.caption(
            "이미 확인한 Apple 2025년 10-K/발표자료의 전사 수치만 재계산합니다. "
            "현재 실적·실시간 SEC 조회/시장지수 분석/원본 바이트 인증이 아닙니다."
        )
        from .ticker_apple_historical import review_apple_fy2025_historical
        from datetime import date
        history_eligible = False
        try:
            history_eligible = (
                valid and date.fromisoformat(as_of) >= date(2025, 10, 31)
            )
        except (ValueError, TypeError):
            pass
        if st.button(
            "Apple FY2025 원문·발표 수동기록 재검산 (네트워크 없음)",
            key="kuodra_p126_apple_manual",
            disabled=not history_eligible,
        ):
            manual_result = review_apple_fy2025_historical(
                ticker=ticker, as_of=as_of,
            )
            if (
                manual_result.get("status")
                    != "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED"
                or manual_result.get("source_authenticated") is not False
                or manual_result.get("source_rights_verified") is not False
                or manual_result.get("original_html_authenticated") is not False
                or manual_result.get("raw_sec_api_used") is not False
                or manual_result.get("guard_executed") is not False
                or manual_result.get("audit_written") is not False
                or manual_result.get("trade_executed") is not False
                or manual_result.get("network_requests") != 0
                or manual_result.get("guard_policy_preview", {}).get("decision")
                    != "HOLD"
            ):
                st.error("Apple 수동자료 교차검산 실패 · 투자 판단을 표시하지 않습니다.")
            else:
                st.success("Apple FY2025 수동발췌 10-K·발표 수치 대조 통과 (원본 미인증)")
                st.metric(
                    "2025년 Apple 연매출 성장률 · 수동 기록",
                    manual_result["sales_growth_pct"] + "%",
                )
                st.metric(
                    "2025년 Apple 현금흐름−CAPEX 대리치 · 백만 USD",
                    manual_result["cashflow_minus_capex_2025_usd_millions"],
                )
                st.json({
                    "status": manual_result["status"],
                    "issuer_cik": manual_result["issuer_cik"],
                    "accession": manual_result["accession"],
                    "filed_at": manual_result["filed_at"],
                    "fiscal_end": manual_result["fiscal_end"],
                    "manual_10k_source": manual_result["issuer_hosted_10k_url"],
                    "issuer_press_source": manual_result["issuer_press_release_url"],
                    "manual_sources_sha256": {
                        "10k": manual_result["manual_10k_json_sha256"],
                        "press": manual_result["manual_press_json_sha256"],
                        "curated": manual_result["manual_companyfacts_excerpt_sha256"],
                    },
                    "sales_2025_usd_millions": manual_result["sales_2025_usd_millions"],
                    "sales_2024_usd_millions": manual_result["sales_2024_usd_millions"],
                    "sales_growth_pct": manual_result["sales_growth_pct"],
                    "receivables_minus_sales_growth_pp":
                        manual_result["receivables_minus_sales_growth_pp"],
                    "guard_preview": manual_result["guard_policy_preview"],
                    "source_authenticated": False,
                    "source_rights_verified": False,
                    "as_of_latest_filing_researched": False,
                    "current_live_market_data": False,
                    "ai_agent_executed": False,
                    "trade_executed": False,
                })
                st.warning(
                    "수치는 과거 Apple 발행자료의 수동 전사 결과입니다. "
                    "원문 바이트·최신 공시·지수/가격 데이터·이용권한 미인증. "
                    "FCF 대리치는 비GAAP이며 Guard는 HOLD 미리보기만 수행합니다."
                )

        # P128: reuse P127's one-shot public-byte observation without any GET.
        # The upload is optional and evaluated only on a local explicit click.
        from .apple_p127_local_evidence import (
            MAX_UPLOAD_SIZE, SUCCESS, prior_public_observation,
            review_local_apple_p127_original,
        )
        st.subheader("Apple FY2025 · P127 원본 바이트 관측값 대조")
        st.caption(
            "GitHub Actions가 과거 1회 관측한 Apple 호스팅 HTML의 SHA-256/크기입니다. "
            "같은 바이트라도 발행자 전자서명·SEC 원본/재배포 권리 인증은 아닙니다. "
            "새 HTTP 요청 없이 로컬 선택 파일만 검사합니다."
        )
        st.json(prior_public_observation())
        local_apple_original = st.file_uploader(
            "Apple FY2025 10-K HTML (선택 · 로컬 메모리에서만 검증)",
            type=["html", "htm"], key="kuodra_p128_apple_original",
        )
        if st.button(
            "Apple P127 관측 SHA·재무 24칸 로컬 검증 (네트워크 없음)",
            key="kuodra_p128_review",
            disabled=not history_eligible or local_apple_original is None,
        ):
            size = getattr(local_apple_original, "size", None)
            if type(size) is not int or not 0 < size <= MAX_UPLOAD_SIZE:
                st.error("선택 HTML 크기/형식이 허용 범위가 아닙니다.")
            else:
                try:
                    local_review = review_local_apple_p127_original(
                        local_apple_original.getvalue(), ticker=ticker, as_of=as_of,
                    )
                except (OSError, TypeError, ValueError, AttributeError):
                    st.error("로컬 HTML을 읽지 못했습니다. 원본은 보관하지 않습니다.")
                else:
                    if (local_review.get("status") == SUCCESS
                            and local_review.get("source_rights_verified") is False
                            and local_review.get("sec_original_authenticated") is False
                            and local_review.get("network_requests") == 0):
                        st.success("과거 P127 관측 바이트와 동일 · 재무 수치 24/24 일치")
                    else:
                        st.warning("P127 바이트 일치·재무 검산 조건을 충족하지 못했습니다.")
                    st.json(local_review)
                    st.warning(
                        "일치 결과는 로컬 파일과 과거 CI 관측의 동일성만 의미합니다. "
                        "SEC 인증·원본 서명·데이터 이용권·최신 공시·투자 승인은 미검증입니다."
                    )

    # P145: third-party licensed SEC-derived source adapter.
    # Unlike SEC P105, this targets only the independent paid provider's
    # own API hosts. No request on reruns, no paid call without new approval.
    st.subheader("티커 한 개 → 별도 허가된 공시 공급자 → 7단계 검증")
    st.caption("sec-api.io 공급자의 Mapping/Query/XBRL/원문 미러 4회 경로. "
               "공식 SEC 서버 재시도가 아니며 제3자 제공·과금·이용권한 승인이 필요합니다.")
    vendor_gate = all(os.environ.get(name) == "1" for name in (
        "KUODRA_ENABLE_SEC_API_VENDOR",
        "KUODRA_SEC_API_VENDOR_RETRIEVAL_APPROVED",
        "KUODRA_SEC_API_VENDOR_RIGHTS_APPROVED",
    )) and bool(os.environ.get("KUODRA_SEC_API_VENDOR_KEY"))
    vendor_ack = st.checkbox(
        "이 티커·날짜로 제3자 sec-api.io 최대 4회 유료 가능 요청에 동의 (원본 미인증·외부공유 불가)",
        value=False, key="kuodra_p145_vendor_ack",
    )
    vendor_clicked = st.button(
        "승인된 공급자로 10-K 조회 → A/B/C·Guard·근거 보고서 (최대 4회)",
        key="kuodra_p145_vendor_run",
        disabled=not (vendor_gate and vendor_ack and valid),
    )
    peer_gate = (os.environ.get("KUODRA_ENABLE_SEC_API_PEER_EXTRA") == "1"
                 and os.environ.get("KUODRA_SEC_API_PEER_RIGHTS_APPROVED") == "1")
    peer_ack = st.checkbox(
        "동일 업종 단일 기업 추가 공시 최대 3회 요청 (총 최대 7회, "
        "비대표본·산업 성장률 미산출)에 별도 동의합니다",
        value=False, key="kuodra_p146_peer_ack",
    )
    peer_clicked = st.button(
        "승인된 공급자 + 동종기업 1개 연간 매출 비교 (최대 7회)",
        key="kuodra_p146_peer_run",
        disabled=not (vendor_gate and vendor_ack and
                      peer_gate and peer_ack and valid),
    )
    if vendor_clicked or peer_clicked:
        from .ticker_provider_sec_api import run_sec_api_on_demand
        try:
            market_bytes = (_read_uploaded(market_source, 131072)
                            if market_source is not None else None)
            industry_bytes = (_read_uploaded(industry_source, 65536)
                              if industry_source is not None else None)
            vendor = run_sec_api_on_demand(
                ticker=key, as_of=as_of,
                api_key=os.environ.get("KUODRA_SEC_API_VENDOR_KEY"),
                explicit_click=True, operator_retrieval_approved=True,
                operator_rights_approved=True,
                market_json=market_bytes, industry_json=industry_bytes,
                include_one_peer=peer_clicked, peer_approved=peer_clicked,
            )
        except (ValueError, TypeError, OSError, RecursionError):
            st.warning("공급자 자료 형식·입력 검증 실패. 원본·API 키는 기록하지 않습니다.")
        else:
            st.json({k: v for k, v in vendor.items()
                     if k not in ("report", "dashboard")})
            if vendor.get("status") == "SOURCE_REPLAYED_UNVERIFIED":
                report = vendor.get("report")
                if type(report) is dict:
                    st.json(vendor["dashboard"])
                    if type(vendor.get("peer_comparison")) is dict:
                        st.subheader("Engine C 보조 · 동일 업종 1기업 매출 비교 (비대표본)")
                        st.json(vendor["peer_comparison"])
                        st.warning("기업 하나를 비교한 수치일 뿐 산업지표·대표 표본·"
                                   "시장전망으로 일반화할 수 없습니다.")
                    from .ticker_provider_sec_api import encode_vendor_evidence_json
                    st.download_button(
                        "제3자 공시 출처·Guard 로컬 검토 JSON (미인증)",
                        data=encode_vendor_evidence_json(vendor),
                        file_name="kuodra-vendor-local-review-UNVERIFIED.json",
                        mime="application/json", key="kuodra_p145_vendor_report",
                    )
                st.warning("7단계 산술 검산은 제3자 자료에서 재구성한 입력 기준입니다. "
                           "SEC 발행자 인증·서비스 내 재배포 권한·지수/산업 실데이터 "
                           "보장은 아니며 Guard는 HOLD/REJECT입니다.")
            else:
                st.warning("검증되지 않은 데이터/계약/공시 상태이므로 분석을 차단했습니다.")

    st.subheader("로컬 공시 목록으로 출처 계획 확인 (개발·검증용)")
    st.caption("이 부분은 자동 수집의 대체 사용 경로가 아닌 오프라인 검증용입니다. "
               "사용자가 전체 시장 자료를 준비할 필요는 없습니다.")
    # P144: existing operator 3-source ZIP is a single-upload fallback.
    # Its self-reported submissions ticker becomes an explicitly untrusted
    # derived map, never an official company_tickers.json authentication.
    from .operator_sec_zip import _MAX_ZIP_BYTES
    operator_zip = st.file_uploader(
        "기존 3원본 ZIP 하나로 로컬 분석 (개발용 · 출처 미인증)",
        type=["zip"], key="kuodra_p144_operator_zip",
    )
    if operator_zip is not None:
        st.caption("기존 operator SEC ZIP 형식만 지원합니다. "
                   "티커/CIK는 ZIP 내 자체 주장으로 검증하며, 공식 발행자 인증이 아닙니다. "
                   "ZIP 선택 시 아래 4개 개별 SEC 파일은 비워 두십시오.")
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
    # P167: initial A/B/C review-packet creation from caller-owned raw
    # issuer, stock and NDX bytes. No provider entitlement or network gate
    # because this path NEVER issues HTTP or persists the originals.
    st.subheader("SEC 4원본 + 종목·NDX 로컬 입력으로 통합 보고서 최초 생성")
    st.caption("종목·실제 NDX 제공자 형식 JSON이 이미 합법적으로 확보된 경우에만 "
               "오프라인 산술 재검산합니다. ETF를 NDX로 대체하지 않습니다. "
               "원본 출처·시점·재배포 권리는 여전히 미인증입니다.")
    offline_stock_upload = st.file_uploader(
        "종목 일별 종가 응답 JSON (로컬 분석 전용)",
        type=["json"], key="kuodra_p167_stock",
    )
    offline_ndx_upload = st.file_uploader(
        "Nasdaq-100 NDX 일별 지수 응답 JSON (로컬 분석 전용)",
        type=["json"], key="kuodra_p167_ndx",
    )
    # P169: allow an independent vendor-neutral local CSV source; one
    # stock + one NDX file. A mixed JSON/CSV pair must never silently pass.
    st.caption("대체 로컬 CSV 형식: symbol,date,close (일자 오름차순, "
               "평일 31~100개, 종목 표기·NDX 원문 헤더 필수). "
               "CSV 업로드도 공급자·라이선스 인증이 아닙니다.")
    offline_stock_csv = st.file_uploader(
        "종목 일별 CSV (JSON 대신, 원본 미인증)",
        type=["csv"], key="kuodra_p169_stock_csv",
    )
    offline_ndx_csv = st.file_uploader(
        "Nasdaq-100 NDX 일별 CSV (JSON 대신, 원본 미인증)",
        type=["csv"], key="kuodra_p169_ndx_csv",
    )
    csv_mode = (offline_stock_csv is not None
                and offline_ndx_csv is not None
                and offline_stock_upload is None
                and offline_ndx_upload is None)
    json_mode = (offline_stock_upload is not None
                 and offline_ndx_upload is not None
                 and offline_stock_csv is None
                 and offline_ndx_csv is None)
    if ((offline_stock_csv is not None or offline_ndx_csv is not None)
            and not csv_mode):
        st.warning("시장 원본은 JSON 2개 또는 CSV 2개 중 하나만 선택해야 합니다. "
                   "혼합 입력과 불완전한 파일은 거부합니다.")
    offline_ack = st.checkbox(
        "로컬 계산만 수행하며 원본 진위·재사용권·투자 승인으로 취급하지 않습니다",
        value=False, key="kuodra_p167_ack",
    )
    # P123: separate explicit human act; each click rereads source uploads
    # and independently replays the report before producing any receipt.
    # Do not cache original bytes, account/identity claims or review receipts.
    st.subheader("사람의 로컬 검토 확인 · 승인/감사 아님")
    st.caption("표시명은 본인 확인이 되지 않습니다. 개인 식별정보를 입력하지 마십시오. "
               "확인 기록은 별도 다운로드할 때만 생성하며 투자·제출 허가가 아닙니다.")
    reviewer_alias = st.text_input(
        "검토 표시명 (영문/숫자/한글/밑줄, 실명 금지)",
        value="", max_chars=40, key="kuodra_p123_alias",
    )
    review_note = st.text_input(
        "검토 사유 (10~240자, 개인정보 입력 금지)",
        value="", max_chars=240, key="kuodra_p123_note",
    )
    local_ack = st.checkbox(
        "원본 미인증·이용권리 미확인·Guard HOLD/REJECT 유지에 동의합니다",
        value=False, key="kuodra_p123_ack",
    )
    source_selected = ticker_map is not None or operator_zip is not None
    human_review_clicked = st.button(
        "6단계 재검증 후 로컬 확인 기록 생성",
        key="kuodra_p123_review",
        disabled=not source_selected or not valid or not local_ack,
    )
    source_plan_clicked = st.button(
        "로컬 원본으로 출처 계획 확인", key="kuodra_p100_offline",
        disabled=not source_selected or not valid,
    )
    # P141: one click can run both a pinned local SEC replay and (only with
    # separate Premium market-data permission) two licensed vendor GETs.
    # The click label explicitly says network; old offline button stays offline.
    pair_approved = all(os.environ.get(k) == "1" for k in (
        "KUODRA_ENABLE_ALPHA_VANTAGE_DAILY",
        "KUODRA_ENABLE_ALPHA_VANTAGE_INDEX",
        "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED",
        "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED",
    )) and bool(os.environ.get("KUODRA_ALPHA_VANTAGE_API_KEY"))
    pair_ack = st.checkbox(
        "별도 승인된 Premium NDX + 종목 주가 총 최대 2회 외부 조회에 동의합니다",
        value=False, key="kuodra_p141_pair_ack",
    )
    pair_clicked = st.button(
        "로컬 공시 재검산 + 승인된 주가·실제 NDX 지수 조회 (최대 2회)",
        key="kuodra_p141_pair_run",
        disabled=not (pair_approved and pair_ack and valid and
                      (operator_zip is not None or
                       all(x is not None for x in (
                           ticker_map, submissions, companyfacts_local, original_local)))),
    )
    offline_pair_clicked = st.button(
        "로컬 SEC + 종목·실제 NDX A/B/C 통합 검토 파일 생성 (외부 요청 0회)",
        key="kuodra_p167_run",
        disabled=not (
            valid and offline_ack
            and (json_mode or csv_mode)
            and (operator_zip is not None or
                 all(x is not None for x in (
                     ticker_map, submissions, companyfacts_local, original_local)))
        ),
    )
    if source_plan_clicked or human_review_clicked or pair_clicked or offline_pair_clicked:
        raw_local = None
        using_zip = operator_zip is not None
        if using_zip and any(x is not None for x in (
                ticker_map, submissions, companyfacts_local, original_local)):
            st.warning("ZIP과 개별 SEC 파일을 동시에 선택할 수 없습니다.")
            return
        try:
            if using_zip:
                from .ticker_operator_zip_bridge import restore_operator_zip_for_ticker
                raw_local, zip_receipt = restore_operator_zip_for_ticker(
                    _read_uploaded(operator_zip, _MAX_ZIP_BYTES),
                    ticker=key, as_of=as_of,
                )
                mapped, filings = raw_local["ticker_map"], raw_local["submissions"]
                st.json(zip_receipt)
                st.warning("ZIP 내 ticker 목록으로 복원된 로컬 출처 지도입니다. "
                           "공식 SEC ticker_map 원본이 아니며 원본 진위·권리는 미검증입니다.")
            else:
                mapped = _read_uploaded(ticker_map, MAX_MAP_BYTES)
                filings = (_read_uploaded(submissions, MAX_SUBMISSIONS_BYTES)
                           if submissions is not None else None)
            result = build_ticker_source_plan(
                ticker=ticker, ticker_map=mapped, submissions=filings,
                as_of=as_of,
            )
        except (ValueError, TypeError, OSError, RecursionError):
            if type(raw_local) is dict:
                raw_local.clear()
            st.warning("로컬 자료의 형식·크기·기업 식별 정보를 확인할 수 없습니다.")
            return
        _display_receipt(st, result, online=False)
        # P116: no SEC HTTP, unchanged seven-step arithmetic and Guard.
        if not using_zip and companyfacts_local is None and original_local is None:
            return
        if not using_zip and (submissions is None or
                             companyfacts_local is None or original_local is None):
            st.warning("로컬 매출 검산에는 ticker 목록, submissions, "
                       "CompanyFacts, 같은 10-K 원문 모두 필요합니다.")
            return
        try:
            from .ticker_sec_financial_bridge import _LIMITS
            from .ticker_local_workflow import run_local_ticker_workflow

            if not using_zip:
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
                "engine_b": workflow["engine_b"]["status"],
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
            # Present source-bound A/B/C numeric values only after the
            # existing seven-stage independent local report replay passes.
            from .ticker_local_dashboard import render_local_ticker_dashboard
            render_local_ticker_dashboard(st, workflow)
            if offline_pair_clicked:
                # This is the FIRST packet generation path that needs no
                # earlier approved Premium GET and no preexisting packet.
                # Only safe redacted bytes may appear in a download.
                from .ticker_offline_review_builder import build_offline_initial_review
                try:
                    csv_stock = None
                    csv_index = None
                    if csv_mode:
                        from .local_market_csv_bridge import normalize_market_csv
                        stock_csv_raw = _read_uploaded(offline_stock_csv, 32768)
                        index_csv_raw = _read_uploaded(offline_ndx_csv, 32768)
                        csv_stock = normalize_market_csv(
                            stock_csv_raw, symbol=key, as_of=as_of,
                            is_index=False,
                        )
                        csv_index = normalize_market_csv(
                            index_csv_raw, symbol="NDX", as_of=as_of,
                            is_index=True,
                        )
                        stock_input = csv_stock["normalized_json"]
                        index_input = csv_index["normalized_json"]
                    else:
                        stock_input = _read_uploaded(offline_stock_upload, 262144)
                        index_input = _read_uploaded(offline_ndx_upload, 8388608)
                    result = build_offline_initial_review(
                        ticker=key, as_of=as_of, sources=raw_local,
                        stock_raw=stock_input,
                        index_raw=index_input,
                        market_json=market_data, industry_json=industry_data,
                    )
                    if (csv_mode and result.get("status") ==
                            "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"):
                        from .local_market_csv_bridge import (
                            build_csv_lineage_receipt,
                            inspect_csv_lineage_receipt,
                        )
                        csv_lineage = build_csv_lineage_receipt(
                            stock=csv_stock, index=csv_index,
                            stock_csv_raw=stock_csv_raw,
                            index_csv_raw=index_csv_raw,
                            packet=result["review_packet"],
                        )
                        lineage_check = inspect_csv_lineage_receipt(
                            csv_lineage, packet=result["review_packet"],
                        )
                        if lineage_check.get("status") != "CSV_LINEAGE_MATCHED_RIGHTS_PENDING":
                            raise ValueError("CSV_LINEAGE_REVIEW_FAILED")
                        result["csv_lineage_receipt"] = csv_lineage
                except (TypeError, ValueError, KeyError, OSError,
                        UnicodeError, RecursionError, OverflowError):
                    result = {"status": "BLOCKED",
                              "reason_code": "LOCAL_SOURCE_FILE_READ_INVALID"}
                if result.get("status") != "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED":
                    st.warning("로컬 최초 통합 패키지 생성 불가. 원본·기간·NDX "
                               "지수 형식 또는 검산 근거를 확인하십시오.")
                    st.code(result.get("reason_code", "LOCAL_REPLAY_BLOCKED"),
                            language="text")
                else:
                    st.success("SEC 4원본 + 종목·실제 NDX 오프라인 재계산 PASS (출처 미인증)")
                    st.json({
                        "ticker": result["ticker"],
                        "as_of": result["as_of"],
                        "accession": result["accession"],
                        "matched_sessions": result["matched_sessions"],
                        "guard_policy_preview": "HOLD",
                        "local_replay_verified": True,
                        "market_math_recomputed": True,
                        "source_authenticated": False,
                        "source_rights_verified": False,
                        "market_vintage_authenticated": False,
                        "external_sharing_allowed": False,
                        "network_requests": 0,
                        "trade_executed": False,
                    })
                    st.download_button(
                        "로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)",
                        data=result["review_packet"],
                        file_name="kuodra-offline-a-b-c-review-UNVERIFIED.json",
                        mime="application/json", on_click="ignore", key="kuodra_p167_packet_download",
                    )
                    st.download_button(
                        "원본·이용권한 미확인 항목 JSON 다운로드 (승인 아님)",
                        data=result["source_clearance_report"],
                        file_name="kuodra-source-rights-GAPS-UNVERIFIED.json",
                        mime="application/json", on_click="ignore", key="kuodra_p168_rights_gaps",
                    )
                    if csv_mode:
                        st.download_button(
                            "로컬 CSV 원본·JSON 변환 이력 JSON 다운로드 (미인증)",
                            data=result["csv_lineage_receipt"],
                            file_name="kuodra-csv-lineage-UNVERIFIED.json",
                            mime="application/json", on_click="ignore",
                            key="kuodra_p169_csv_lineage_download",
                        )
                        st.warning("권리 검토표의 시장 응답 해시는 CSV로부터 변환한 JSON의 "
                                   "해시입니다. CSV 원본 해시는 별도 변환 이력 파일에 "
                                   "연결됩니다. 공급자 인증·유료 지수 이용권은 미확인입니다.")
                    from .ticker_reviewer_html import render_reviewer_html
                    try:
                        reviewer_html = render_reviewer_html(
                            review_packet=result["review_packet"],
                            rights_gap_report=result["source_clearance_report"],
                            csv_lineage=(result["csv_lineage_receipt"]
                                         if csv_mode else None),
                        )
                    except (ValueError, TypeError, KeyError,
                            UnicodeError, OverflowError, RecursionError):
                        st.warning("읽기 쉬운 검토 보고서 생성 실패: 연결된 패킷·"
                                   "권리 검토 파일의 무결성을 확인하십시오.")
                        st.code("REVIEW_HTML_SOURCE_LINK_INVALID", language="text")
                    else:
                        st.download_button(
                            "단일 종목 A/B/C HTML 보고서 다운로드 (오프라인·미인증)",
                            data=reviewer_html,
                            file_name="kuodra-single-ticker-review-UNVERIFIED.html",
                            mime="text/html", on_click="ignore",
                            key="kuodra_p170_reviewer_html_download",
                        )
                        # P171: single self-contained ZIP for a reviewer.
                        # Only already validated/redacted files; no originals
                        # or provider data rows are added to the archive.
                        try:
                            from .ticker_review_bundle import (
                                build_review_bundle_bytes,
                                inspect_review_bundle_bytes,
                            )
                            review_zip = build_review_bundle_bytes(
                                review_packet=result["review_packet"],
                                rights_gap_report=result["source_clearance_report"],
                                csv_lineage=(result["csv_lineage_receipt"]
                                             if csv_mode else None),
                            )
                            zip_check = inspect_review_bundle_bytes(review_zip)
                            if zip_check["status"] != (
                                    "INTERNAL_CONTENT_VERIFIED_ORIGIN_RIGHTS_PENDING"):
                                raise ValueError("REVIEW_ZIP_CHECK_FAILED")
                        except (ValueError, TypeError, KeyError, UnicodeError,
                                RecursionError, OverflowError):
                            st.warning("단일 증거 묶음 ZIP 생성 실패. "
                                       "기존 JSON/HTML 파일은 개별 검토하십시오.")
                            st.code("REVIEW_ZIP_SOURCE_LINK_INVALID", language="text")
                        else:
                            st.download_button(
                                "단일 종목 근거 묶음 ZIP 다운로드 (로컬·미인증)",
                                data=review_zip,
                                file_name="kuodra-review-evidence-UNVERIFIED.zip",
                                mime="application/zip", on_click="ignore",
                                key="kuodra_p171_evidence_zip_download",
                            )
                    st.info("원본 8종의 파일 해시와 시장 검토기간, "
                            "발행자 인증·구매 권한·공개/재배포 허가에 필요한 "
                            "미확인 항목을 분리 기록했습니다. 이 확인표도 "
                            "어떠한 이용권리를 부여하지 않습니다.")
                    st.warning("완전한 공급자 인증·이용권한·대표표본 검증이나 "
                               "투자·거래·대회 제출 승인이 아닙니다.")
            if pair_clicked:
                # Never initiate a paid query until source identity, fiscal
                # period and independent local report replay all succeeded.
                guard = original_check.get("guard_preview")
                if type(guard) is not dict or guard.get("decision") != "HOLD":
                    st.warning("Guard REJECT/원문 불일치: Premium 외부 조회를 차단합니다.")
                else:
                    from .market_pair_engine_a import fetch_and_analyze_market_pair
                    # One attempt per analyzed source set in this Streamlit
                    # session; it is recorded BEFORE vendor calls to block
                    # repeated reruns and provider cost spikes.
                    state = getattr(st, "session_state", None)
                    fingerprint = _p154_pair_source_fingerprint(
                        ticker=key, as_of=as_of, receipt=local_receipt,
                        market_json=market_data, industry_json=industry_data,
                    )
                    from .premium_paid_attempts import register_premium_pair_attempt
                    attempt = register_premium_pair_attempt(state, fingerprint)
                    if attempt == "INVALID":
                        # Never risk a duplicate paid call when the session's
                        # previously registered request history is corrupted.
                        st.warning("유료 조회 이력 검증 실패: 추가 API 요청을 차단합니다. "
                                   "새 세션에서만 별도 승인 후 다시 시작할 수 있습니다.")
                    elif attempt == "DUPLICATE":
                        st.warning("중복 조회 차단: 이 세션에서 동일 자료로 이미 유료 조회를 시도했습니다. "
                                   "추가 API 호출 없이 기존 보고서만 확인합니다.")
                        _p153_render_cached_linked_report(
                            st, ticker=key, as_of=as_of,
                            approved=bool(pair_approved and pair_ack and valid),
                            operator_zip=operator_zip, ticker_map=ticker_map,
                            submissions=submissions,
                            companyfacts_local=companyfacts_local,
                            original_local=original_local,
                            market_source=market_source,
                            industry_source=industry_source,
                        )
                    else:
                        # register_premium_pair_attempt wrote the bounded
                        # session ledger BEFORE either supplier HTTP GET.
                        # Build a separate redacted report while the
                        # receipt pair is still in memory. Both the original
                        # seven-step report and Engine A math are replayed.
                        linked_holder = {}
                        def _capture_linked_pair(stock, index):
                            from .ticker_market_pair_evidence import (
                                build_linked_market_evidence,
                                verify_linked_market_evidence,
                            )
                            linked = build_linked_market_evidence(
                                workflow=workflow, sources=raw_local,
                                stock=stock, index=index,
                                market_json=market_data,
                                industry_json=industry_data,
                            )
                            check = verify_linked_market_evidence(
                                linked, workflow=workflow, sources=raw_local,
                                stock=stock, index=index,
                                market_json=market_data,
                                industry_json=industry_data,
                            )
                            if (linked.get("status") ==
                                    "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED"
                                    and check.get("status") == "PASS"):
                                # Serialize at the verification boundary. If a
                                # later exporter contract rejects this result,
                                # the main local report must still be usable.
                                from .ticker_market_pair_evidence import (
                                    linked_evidence_json_bytes,
                                )
                                try:
                                    safe_bytes = linked_evidence_json_bytes(linked)
                                except (ValueError, TypeError, KeyError,
                                        OverflowError, RecursionError):
                                    linked_holder["reason"] = "LINKED_EXPORT_CONTRACT_FAILED"
                                else:
                                    linked_holder["report"] = linked
                                    linked_holder["safe_bytes"] = safe_bytes
                                    from .ticker_review_packet import (
                                        build_review_packet,
                                        review_packet_json_bytes,
                                        verify_review_packet_against_sources,
                                    )
                                    try:
                                        check_bytes = review_packet_json_bytes(
                                            build_review_packet(linked))
                                        linked_holder["packet_source_replay"] = (
                                            verify_review_packet_against_sources(
                                                check_bytes,
                                                workflow=workflow,
                                                sources=raw_local,
                                                stock=stock, index=index,
                                                market_json=market_data,
                                                industry_json=industry_data,
                                            )
                                        )
                                    except (ValueError, TypeError, KeyError,
                                            OverflowError, UnicodeError,
                                            RecursionError):
                                        linked_holder["packet_source_replay"] = {
                                            "status": "FAIL",
                                            "reason_code": "PACKET_REPLAY_INPUT_INVALID",
                                            "local_source_replay_verified": False,
                                            "market_math_recomputed": False,
                                        }
                            else:
                                linked_holder["reason"] = "LINKED_INDEPENDENT_REPLAY_FAILED"
                        market_result = fetch_and_analyze_market_pair(
                            ticker=key, issuer_cik=local_receipt["cik"],
                            filing_date=revenue["filing_date"], as_of=as_of,
                            api_key=os.environ.get("KUODRA_ALPHA_VANTAGE_API_KEY"),
                            benchmark="NASDAQ_100", explicit_click=True,
                            provider_rights_approved=True,
                            premium_entitlement_approved=True,
                            validated_pair_callback=_capture_linked_pair,
                        )
                        st.subheader("실제 종목·NASDAQ-100 자료 기반 Engine A (미인증)")
                        if market_result["status"] == "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED":
                            analyzed = market_result["market_analysis"]
                            st.metric("종목/지수 수익률 (원시 종가)",
                                      str(analyzed["security_return_pct"]) + "% / " +
                                      str(analyzed["benchmark_return_pct"]) + "%")
                            st.metric("OLS 베타 (투자 추천 아님)",
                                      str(analyzed["beta"]) if analyzed["beta"] is not None
                                      else "산출 불가")
                            st.json({
                                "matched_observation_count": market_result["matched_observation_count"],
                                "matched_period_start": market_result["matched_period_start"],
                                "matched_period_end": market_result["matched_period_end"],
                                "as_of": as_of,
                                "filing_date": revenue["filing_date"],
                                "stock_source_sha256": market_result["stock_response_sha256"],
                                "index_source_sha256": market_result["index_response_sha256"],
                                "vendor_requests_attempted": market_result["network_requests"],
                                "source_authenticated": False,
                                "source_rights_verified": False,
                                "guard_executed": False,
                                "ai_agent_executed": False, "trade_executed": False,
                            })
                            if "report" in linked_holder:
                                linked = linked_holder["report"]
                                st.subheader("7단계 SEC·B/C + 실제 지수 Engine A 통합 증거")
                                st.json({
                                    "status": linked["status"],
                                    "local_report_sha256": linked["local_report_sha256"],
                                    "evidence_sha256": linked["evidence_sha256"],
                                    "engine_b": linked["engine_b"]["status"],
                                    "engine_c": linked["engine_c"]["status"],
                                    "matched_period_start": linked["premium_engine_a"]["matched_period_start"],
                                    "matched_period_end": linked["premium_engine_a"]["matched_period_end"],
                                    "market_math_recomputed": True,
                                    "source_authenticated": False,
                                    "source_rights_verified": False,
                                    "full_a_b_c_ready": False,
                                })
                                if state is not None:
                                    try:
                                        current_digest = _p153_uploaded_input_digest(
                                            ticker=key, as_of=as_of,
                                            operator_zip=operator_zip,
                                            ticker_map=ticker_map,
                                            submissions=submissions,
                                            companyfacts_local=companyfacts_local,
                                            original_local=original_local,
                                            market_source=market_source,
                                            industry_source=industry_source,
                                        )
                                    except (ValueError, TypeError, OSError,
                                            UnicodeError, RecursionError):
                                        state.pop(_P153_LINKED_CACHE_KEY, None)
                                    else:
                                        # Keep a small bounded archive so an
                                        # explicitly clicked A -> B -> A source
                                        # switch can redisplay A without a
                                        # duplicate licensed market GET.
                                        from .linked_report_session_cache import (
                                            keep_linked_report,
                                        )
                                        keep_linked_report(
                                            state, current_digest,
                                            linked_holder["safe_bytes"],
                                        )
                                st.download_button(
                                    "통합 검산 근거 JSON (로컬 전용 · 미인증)",
                                    data=linked_holder["safe_bytes"],
                                    file_name="kuodra-local-market-linked-UNVERIFIED.json",
                                    mime="application/json",
                                    key="kuodra_p143_linked_market_report",
                                )
                                _render_p158_source_linked_interpretation(
                                    st, linked,
                                    source_replay=linked_holder.get("packet_source_replay"),
                                )
                            else:
                                # A failed derived export does NOT discard the
                                # independently verified four-source report.
                                st.warning(
                                    "통합 증거 JSON은 독립 검산 또는 출력 계약 오류로 "
                                    "차단했습니다. 아래 로컬 공시 보고서는 별도로 유지됩니다."
                                )
                                st.code(
                                    linked_holder.get("reason", "LINKED_EVIDENCE_UNAVAILABLE"),
                                    language="text",
                                )
                            st.warning("실제 응답 출처·시점·재배포 권리는 별도 검증 필요. "
                                       "통합 보고서는 로컬 수치 재검산만 증명하며 "
                                       "외부 공유·매매·Guard 승인을 허용하지 않습니다.")
                        else:
                            st.warning("적법한 지수·종목 증거 확보 또는 기간 정합성 부족으로 분석 보류.")
                            st.code(market_result["reason_code"], language="text")
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
                if human_review_clicked:
                    from .ticker_human_acknowledgement import (
                        acknowledge_local_ticker_report,
                        acknowledgement_json_bytes,
                    )
                    try:
                        human_receipt = acknowledge_local_ticker_report(
                            local_report, sources=raw_local,
                            reviewer_alias=reviewer_alias,
                            review_note=review_note,
                            explicit_acknowledgement=local_ack,
                            market_json=market_data,
                            industry_json=industry_data,
                        )
                    except (ValueError, TypeError, KeyError, RecursionError):
                        st.warning("검토 확인 차단: 표시명·사유 또는 원본 재검증을 확인하십시오.")
                    else:
                        st.success("로컬 검토 확인 기록 생성 · 신원/원본/권한 미인증")
                        st.json({
                            "status": human_receipt["status"],
                            "report_sha256": human_receipt["report_sha256"],
                            "receipt_sha256": human_receipt["receipt_sha256"],
                            "guard_policy_preview_unchanged":
                                human_receipt["guard_policy_preview_unchanged"],
                            "human_approved": False,
                            "audit_written": False,
                            "source_rights_verified": False,
                            "trade_executed": False,
                        })
                        st.download_button(
                            "로컬 사람 검토 확인 JSON (승인 아님)",
                            data=acknowledgement_json_bytes(human_receipt),
                            file_name="kuodra-local-review-ACK-UNVERIFIED.json",
                            mime="application/json",
                            key="kuodra_p123_ack_download",
                        )
                st.subheader("Engine B · 10-K 회계·현금흐름 검토 (미인증)")
                st.json(workflow["engine_b"])
                st.caption("수익·현금흐름 및 운전자본 비교는 같은 접수번호의 "
                           "로컬 CompanyFacts 기반 설명용 신호입니다. "
                           "공시 출처 미인증이며 회계 사기·투자 판단으로 확정하지 않습니다.")
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
    else:
        # A download-button interaction reruns Streamlit without another
        # network authorization. Redisplay only the bound redacted receipt.
        _p153_render_cached_linked_report(
            st, ticker=key, as_of=as_of,
            approved=bool(pair_approved and pair_ack and valid),
            operator_zip=operator_zip, ticker_map=ticker_map,
            submissions=submissions, companyfacts_local=companyfacts_local,
            original_local=original_local, market_source=market_source,
            industry_source=industry_source,
        )
