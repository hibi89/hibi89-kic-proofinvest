"""Static human-readable local SEC→Guard report. No scripts, links or assets.

This page is not source authentication, investment advice or KIC submission.
Only an existing validated local 3/4-file Guard review is eligible.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping

from .sec_companyfacts import REVENUE_TAGS

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CIK = re.compile(r"[0-9]{10}\Z")
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
_ALLOWED_LIMITS = frozenset({
    "external_source_authenticated", "source_rights_verified",
    "live_api_called", "ai_agent_executed", "trade_executed",
    "simulation_authorized", "official_contest_submission",
})
_CSS = """
:root { color-scheme: light dark; font-family: system-ui, -apple-system, sans-serif; }
* { box-sizing:border-box; }
body { margin:0; background:#edf2f7; color:#14273f; line-height:1.5; }
main { max-width:1080px; margin:32px auto; padding:0 20px 48px; }
header { background:linear-gradient(120deg,#0b2342,#1c4a65);
  color:#fff; padding:30px; border-radius:16px; }
.brand { color:#72e4da; font-weight:800; letter-spacing:.12em; font-size:.78rem; }
h1 { font-size:1.8rem; margin:.45rem 0; letter-spacing:-.03em; }
h2 { font-size:1rem; margin:0 0 14px; }
p { margin:.6rem 0; }
.kicker { color:#c7e0eb; font-size:.9rem; max-width:800px; }
.disclaimer { background:#fff1ed; border-left:5px solid #d95d46; color:#8a2c24;
 padding:15px 17px; border-radius:7px; margin:16px 0; font-weight:650; }
.grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px;
  margin:18px 0; }
section { background:#fff; border:1px solid #d7dfe8; border-radius:12px;
 padding:22px; margin:15px 0; }
.grid section { margin:0; }
.label { color:#5a6b80; font-size:.8rem; font-weight:650; }
.value { font-size:1.4rem; font-weight:800; overflow-wrap:anywhere; }
.state { border-left:5px solid #0c8b82; }
.state.reject { border-color:#d95d46; }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
th,td { padding:10px; text-align:left; border-bottom:1px solid #e5eaf0; vertical-align:top; }
th { width:34%; color:#53677d; font-weight:600; }
code { font-size:.8rem; word-break:break-all; white-space:normal; }
ul { margin:7px 0 0; padding-left:20px; }
footer { margin-top:15px; font-size:.8rem; color:#5a6b80; }
@media(max-width:650px) {
 main { margin:10px auto; padding:0 12px 32px; }
 header { padding:22px; }
 .grid { grid-template-columns:1fr; }
 section { padding:17px; }
}
@media(prefers-color-scheme:dark) {
 body { background:#101b2b; color:#e5eaf0; }
 section { background:#1a2b40; border-color:#385069; }
 th,td { border-color:#385069; }
 th,.label,footer { color:#bdcde0; }
 .disclaimer { background:#492c2a; color:#ffcac0; }
}
"""


def _field(value: Any, limit: int = 160) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("HTML_REPORT_BAD_TEXT_FIELD")
    content = str(value)
    if not 0 < len(content) <= limit or any(ord(c) < 32 for c in content):
        raise ValueError("HTML_REPORT_BAD_TEXT_FIELD")
    return escape(content, quote=True)


def _reasons(value: Any) -> str:
    if (type(value) is not list or len(value) > 20
            or any(not isinstance(x, str) or not 0 < len(x) <= 160
                   for x in value)):
        raise ValueError("HTML_REPORT_BAD_REASONS")
    return "".join("<li>" + _field(x) + "</li>" for x in value) or "<li>none</li>"


def render_local_sec_html(report: Mapping[str, Any]) -> bytes:
    """Escape all caller-derived strings; fail closed on false trust contracts."""
    if (type(report) is not dict
            or report.get("schema") != "proofinvest.local-sec-guard-report.v1"
            or report.get("mode") != "OFFLINE_USER_SUPPLIED_UNAUTHENTICATED"
            or report.get("audit_chain_valid") is not True
            or report.get("human_review_integrity_valid") is not True
            or type(report.get("limits")) is not dict
            or set(report["limits"]) != _ALLOWED_LIMITS
            or any(v is not False for v in report["limits"].values())):
        raise ValueError("HTML_REPORT_UNTRUSTED_CONTRACT")
    issuer, source, fin, risk, guard, audit = (
        report.get(key) for key in
        ("issuer", "source", "verification", "risk", "guard", "audit")
    )
    if any(type(x) is not dict for x in (issuer, source, fin, risk, guard, audit)):
        raise ValueError("HTML_REPORT_MISSING_SECTION")
    if (not isinstance(issuer.get("cik"), str)
            or _CIK.fullmatch(issuer["cik"]) is None
            or not isinstance(issuer.get("accession"), str)
            or _ACCESSION.fullmatch(issuer["accession"]) is None
            # EDGAR accession may identify a submitting agent, not issuer.
            # The upstream Guard evidence is linked using issuer-specific
            # Submissions + CompanyFacts accession membership.
            or guard.get("decision") not in ("HOLD", "REJECT")
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or risk.get("source_authenticated") is not False
            or risk.get("trade_authorized") is not False
            or fin.get("status") not in ("calculated_unverified", "conflict")
            or (fin["status"] == "conflict") != (guard["decision"] == "REJECT")
            or source.get("html_text_node_status") not in (
                "unavailable", "untrusted_html_text_node_literal_located")
            or type(source.get("exact_raw_byte_span_verified")) is not bool
            or source["exact_raw_byte_span_verified"] != (
                source["html_text_node_status"] == "untrusted_html_text_node_literal_located"
            )
            or any(not isinstance(source.get(key), str)
                   or _SHA.fullmatch(source[key]) is None
                   for key in ("submissions_sha256", "companyfacts_sha256",
                               "archived_original_sha256"))
            or not isinstance(audit.get("event_hash"), str)
            or _SHA.fullmatch(audit["event_hash"]) is None):
        raise ValueError("HTML_REPORT_INTEGRITY_BLOCKED")
    # P38: select issuer-owned RECENT or manifest-listed PINNED_HISTORY.
    # A missing or forged fourth SHA must never be represented as evidence.
    index_kind = source.get("source_index_kind")
    hist_digest = source.get("history_page_sha256")
    if (index_kind not in ("RECENT", "PINNED_HISTORY")
            or (index_kind == "RECENT" and hist_digest is not None)
            or (index_kind == "PINNED_HISTORY" and (
                type(hist_digest) is not str or _SHA.fullmatch(hist_digest) is None
            ))
            or fin.get("revenue_concept") not in REVENUE_TAGS
            or fin.get("unit") != "USD"
            or fin.get("filing_date") != issuer.get("filing_date")
            or type(fin.get("prior_period_end")) is not str
            or type(fin.get("current_period_end")) is not str
            or type(fin.get("annual_period_starts")) is not list
            or len(fin["annual_period_starts"]) != 2
            or any(type(x) is not str or len(x) != 10
                   for x in fin["annual_period_starts"])):
        raise ValueError("HTML_REPORT_PROVENANCE_OR_PERIOD_INVALID")
    shares = report.get("share_capital")
    if shares is not None and (
            type(shares) is not dict
            or shares.get("status") not in ("unavailable", "reviewed_unverified")
            or shares.get("source_authenticated") is not False
            or shares.get("guard_policy_modified") is not False
            or shares.get("shares_change_is_not_dilution_or_issuance") is not True):
        raise ValueError("HTML_SHARES_TRUST_CONTRACT_FAILURE")
    share_section = ""
    if shares is not None:
        count = (shares["shares_outstanding"] if shares["status"] == "reviewed_unverified"
                 else "NOT_AVAILABLE")
        basis = shares["basis"] if shares["basis"] is not None else "UNKNOWN"
        share_section = (
            '<section><h2>02A / 발행주식 수 · 제한적 검토</h2><p>'
            + _field(count) + ' shares</p><p>기준: ' + _field(basis)
            + ' / ' + _field(shares["reason_code"]) + '</p>'
            '<p>주식 수 변화는 주식분할·신규 발행·희석 또는 '
            '주요 주주 지분변화를 입증하지 않습니다. 원본은 미인증.</p></section>'
        )
    capital_watch = report.get("capital_filing_watch")
    if capital_watch is not None and (
            type(capital_watch) is not dict
            or capital_watch.get("status") not in (
                "unavailable", "metadata_candidates_unverified",
                "no_candidates_in_limited_issuer_index")
            or capital_watch.get("source_authenticated") is not False
            or capital_watch.get("beneficial_ownership_verified") is not False
            or capital_watch.get("guard_policy_modified") is not False
            or type(capital_watch.get("candidates")) is not list
            or len(capital_watch["candidates"]) > 8):
        raise ValueError("HTML_CAPITAL_WATCH_TRUST_CONTRACT_FAILURE")
    capital_section = ""
    if capital_watch is not None:
        items = "".join(
            "<li>" + _field(item["form"]) + " · "
            + _field(item["filed_at"]) + " · "
            + _field(item["accession"]) + " — "
            + _field(item["review_class"]) + "</li>"
            for item in capital_watch["candidates"]
            if type(item) is dict
        )
        capital_section = (
            '<section><h2>02B / 발행·주요 주주 관련 제출 문서 검토 대기</h2>'
            '<p>' + _field(capital_watch["status"])
            + ' / 검색된 최근 메타데이터 수: '
            + _field(capital_watch["total_matching_recent_metadata"])
            + '</p><p>당일 접수시각 불명 보류: '
            + _field(capital_watch["same_day_without_comparable_acceptance_omitted"])
            + ' · 수집시각 이후 제외: '
            + _field(capital_watch["accepted_after_observation_omitted"])
            + '</p><ul>' + (items or "<li>검색 범위에서 미발견</li>")
            + '</ul><p>원문·타인 CIK의 13D/13G/내부자 신고 및 이전 '
            '페이지를 검색하지 않았습니다. 미발견은 발행·희석·지분변화 '
            '부재의 증명이 아닙니다.</p></section>'
        )
    cashflow = report.get("cashflow")
    if cashflow is not None and (
            type(cashflow) is not dict
            or cashflow.get("status") not in ("unavailable", "reviewed_unverified")
            or cashflow.get("source_authenticated") is not False
            or cashflow.get("risk_authenticated") is not False
            or cashflow.get("guard_policy_modified") is not False
            or cashflow.get("free_cashflow_proxy_is_non_gaap") is not True):
        raise ValueError("HTML_CASHFLOW_TRUST_CONTRACT_FAILURE")
    cash_section = ""
    if cashflow is not None:
        cfo = (cashflow["operating_cashflow_usd"] if
               cashflow["operating_cashflow_usd"] is not None else "NOT_AVAILABLE")
        fcf = (cashflow["free_cashflow_proxy_usd"] if
               cashflow["free_cashflow_proxy_usd"] is not None else "NOT_AVAILABLE")
        cash_section = (
            '<section><h2>02C / 연간 영업현금흐름 · 참고 잉여현금흐름</h2>'
            '<p>영업현금흐름 USD: ' + _field(cfo)
            + ' / 간이 FCF USD: ' + _field(fcf)
            + '</p><p>근거 상태: ' + _field(cashflow["reason_code"])
            + '</p><p>FCF = 영업현금흐름 - 설비투자 지출의 비GAAP 참고치.'
            ' 기업별 정의·현금흐름 세부 항목·원본 진위 및 투자 적격성 미검증.'
            '</p></section>'
        )
    # Optional Engine B; never allow a supplied card to claim proven fraud
    # or to disconnect the displayed numbers from this report's source hash.
    accounting = report.get("accounting_integrity")
    if accounting is not None and (
            type(accounting) is not dict
            or accounting.get("schema") != "kuodra.accounting-integrity-offline.v1"
            or accounting.get("status") not in ("unavailable", "reviewed_unverified")
            or accounting.get("source_authenticated") is not False
            or accounting.get("accounting_fraud_proven") is not False
            or accounting.get("guard_policy_modified") is not False
            or accounting.get("trade_executed") is not False
            or accounting.get("companyfacts_sha256") != source["companyfacts_sha256"]):
        raise ValueError("HTML_ACCOUNTING_TRUST_CONTRACT_FAILURE")
    accounting_section = ""
    if accounting is not None:
        def shown(key):
            val = accounting.get(key)
            return _field(val if val is not None else "NOT_AVAILABLE")
        accounting_section = (
            '<section><h2>02D / Engine B · 이익의 질 · 회계 괴리 검토</h2>'
            '<p>상태: ' + shown("status")
            + ' / 근거: ' + shown("reason_code") + '</p><table>'
            '<tr><th>순이익 (USD)</th><td>' + shown("net_income_usd") + '</td></tr>'
            '<tr><th>영업이익 (USD)</th><td>' + shown("operating_income_usd") + '</td></tr>'
            '<tr><th>영업현금흐름 (USD)</th><td>' + shown("operating_cashflow_usd") + '</td></tr>'
            '<tr><th>순이익 - 영업현금흐름 (USD)</th><td>'
            + shown("earnings_less_cash_usd") + '</td></tr>'
            '<tr><th>현금전환율 (순이익 양수일 때만, %)</th><td>'
            + shown("cash_to_net_income_pct") + '</td></tr>'
            '<tr><th>이익·현금 검토 신호</th><td>'
            + shown("earnings_cash_signal") + '</td></tr>'
            '<tr><th>매출채권 성장률 - 매출 성장률 (pp)</th><td>'
            + shown("receivables_minus_revenue_growth_pp") + '</td></tr>'
            '<tr><th>재고 성장률 - 매출 성장률 (pp)</th><td>'
            + shown("inventory_minus_revenue_growth_pp") + '</td></tr>'
            '<tr><th>운전자본 검토 상태</th><td>'
            + shown("working_capital_review_status") + '</td></tr>'
            '</table><p>관측된 괴리는 회계 부정의 증거가 아닙니다.'
            ' 단일 연도·업종·계절성과 출처 미인증 한계를 고려해야 합니다.</p>'
            '<p>탐색적 운전자본 검토 신호:</p><ul>'
            + _reasons(accounting.get("working_capital_signals")) + '</ul></section>'
        )
    market = report.get("market_reality")
    market_section = ""
    if market is not None:
        if (type(market) is not dict
                or market.get("schema") != "kuodra.market-reality-analysis.v1"
                or market.get("status") not in ("REPORTED_UNVERIFIED", "INSUFFICIENT_MARKET_VARIANCE")
                or market.get("issuer_cik") != issuer["cik"]
                or market.get("as_of") != issuer["as_of"]
                or market.get("source_authenticated") is not False
                or market.get("audit_included") is not False
                or market.get("market_bubble_proven") is not False
                or market.get("sec_growth_caused_price_move") is not False
                or market.get("guard_policy_modified") is not False
                or market.get("trade_signal") is not False
                or market.get("ai_generated") is not False
                or type(market.get("source")) is not dict
                or type(market["source"].get("upload_sha256")) is not str
                or _SHA.fullmatch(market["source"]["upload_sha256"]) is None):
            raise ValueError("HTML_MARKET_REALITY_TRUST_BLOCKED")
        context = market.get("sec_revenue_context")
        if context is not None and (
                type(context) is not dict
                or context.get("source_authenticated") is not False
                or context.get("companyfacts_sha256") != source["companyfacts_sha256"]
                or context.get("growth_pct_calculated_unverified") != fin["growth_pct"]
                or context.get("current_period_end") != fin["current_period_end"]
                or context.get("filing_date") != issuer["filing_date"]):
            raise ValueError("HTML_MARKET_SEC_CONTEXT_MISMATCH")
        def market_text(field):
            v = market.get(field)
            return _field(v if v is not None else "NOT_CALCULATED")
        market_section = (
            '<section><h2>02E / Engine A · 시장 회귀 (입력가격 · 미인증)</h2>'
            '<p>비교 종목: ' + market_text("symbol")
            + ' / 시장지수: ' + market_text("benchmark") + '</p><table>'
            '<tr><th>회귀 상태</th><td>' + market_text("status") + '</td></tr>'
            '<tr><th>수익률 정의</th><td>' + market_text("return_basis") + '</td></tr>'
            '<tr><th>종목 기간 수익률 (%)</th><td>' + market_text("security_return_pct") + '</td></tr>'
            '<tr><th>시장 기간 수익률 (%)</th><td>' + market_text("benchmark_return_pct") + '</td></tr>'
            '<tr><th>Beta</th><td>' + market_text("beta") + '</td></tr>'
            '<tr><th>일별 OLS 절편 (%)</th><td>' + market_text("regression_intercept_daily_pct") + '</td></tr>'
            '<tr><th>표본내 R²</th><td>' + market_text("r_squared") + '</td></tr>'
            '<tr><th>관측 수</th><td>' + market_text("observation_count") + '</td></tr>'
            '</table><p>해당 회귀결과는 유동성 기여분이나 거품 비율이 아닙니다.'
            ' SEC 연매출 변화율과의 병행 표시는 인과관계가 아닙니다.</p>'
            '<p>선택 SEC 매출 변화율 (%): '
            + _field(context["growth_pct_calculated_unverified"] if context is not None
                     else "NO_LINKED_SEC_CONTEXT")
            + '</p><p>업로드 SHA256: '
            + _field(market["source"]["upload_sha256"])
            + '</p><p>Guard 감사 체인에 시장 회귀 결과가 포함되지는 않았습니다.'
            ' 출처 인증·이용권리·미래정보 누출 및 회귀 표본 적합성 미확인.</p></section>'
        )
    state = _field(guard["decision"])
    decision_class = " reject" if guard["decision"] == "REJECT" else ""
    history_kind = ("4개 원본 · 이력 페이지" if index_kind == "PINNED_HISTORY"
                    else "3개 원본 · 최근 제출 목록")
    names = [
        ("Issuer Submissions JSON", source["submissions_sha256"]),
        ("CompanyFacts JSON", source["companyfacts_sha256"]),
        ("Original Filing", source["archived_original_sha256"]),
    ]
    if index_kind == "PINNED_HISTORY":
        names.append(("SEC Historical Page JSON", hist_digest))
    digests = "".join(
        "<tr><th>" + _field(name) + "</th><td><code>" + _field(digest) +
        "</code></td></tr>" for name, digest in names
    )
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; '
        'base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<title>KUODRA | OFFLINE UNVERIFIED Review</title><style>'
        + _CSS + '</style></head><body><main>'
        '<header><div class="brand">KUODRA / EVIDENCE REVIEW</div>'
        '<h1>공시 근거 기반 재무 검산 · Guard 판단</h1>'
        '<p class="kicker">' + _field(history_kind) +
        ' · 비인증 USD 수치 · 위험 근거 점검 · Guard · 임시 감사</p></header>'
        '<div class="disclaimer">UNVERIFIED LOCAL FILES — 실제 SEC 원문 진위·'
        '출처 권리·투자 적격성 검증이 아닙니다. 외부 요청·투자 주문·'
        '공식 KIC 접수는 수행하지 않았습니다.</div>'
        '<div class="grid"><section class="state' + decision_class +
        '"><div class="label">Guard 결정</div><div class="value">' + state +
        '</div><p>Human review only · 실거래 불가</p></section>'
        '<section><div class="label">연매출 변화율 (로컬 수치)</div><div class="value">'
        + _field(fin["growth_pct"]) +
        '%</div><p>산술: ' + _field(fin["status"]) + '</p></section>'
        '<section><div class="label">출처 인증 상태</div>'
        '<div class="value">미인증</div><p>로컬 해시 일치 ≠ 발행사 인증</p></section></div>'
        '<section><h2>01 / 검토 대상 · 기준일</h2><table>'
        '<tr><th>CIK</th><td>' + _field(issuer["cik"]) + '</td></tr>'
        '<tr><th>접수번호</th><td>' + _field(issuer["accession"]) + '</td></tr>'
        '<tr><th>검토 기준일</th><td>' + _field(issuer["as_of"]) + '</td></tr>'
        '<tr><th>공시 접수일 (원본 메타데이터)</th><td>' +
        _field(issuer["filing_date"]) + '</td></tr>'
        '<tr><th>공시 인덱스</th><td>' + _field(index_kind) + '</td></tr>'
        '</table></section>'
        '<section><h2>02 / SEC 형식 수치 검산 (USD · 미인증)</h2><table>'
        '<tr><th>수익 항목 (US GAAP)</th><td>' + _field(fin["revenue_concept"]) + '</td></tr>'
        '<tr><th>이전 연도 기간</th><td>' +
        _field(fin["annual_period_starts"][0]) + ' ~ ' +
        _field(fin["prior_period_end"]) + '</td></tr>'
        '<tr><th>이전 연도 · USD</th><td>' + _field(fin["prior_amount"]) + '</td></tr>'
        '<tr><th>현재 연도 기간</th><td>' +
        _field(fin["annual_period_starts"][1]) + ' ~ ' +
        _field(fin["current_period_end"]) + '</td></tr>'
        '<tr><th>현재 연도 · USD</th><td>' + _field(fin["current_amount"]) + '</td></tr>'
        '<tr><th>수치 비교 방식</th><td>(현재 / 이전 - 1) × 100, Decimal 소수점 둘째 자리 반올림</td></tr>'
        '<tr><th>비교 사유</th><td>' + _field(fin["reason_code"]) + '</td></tr>'
        '</table></section>'
        + share_section + capital_section + cash_section + accounting_section + market_section +
        '<section><h2>03 / 근거 바이트 · 출처 상태</h2><table>'
        + digests +
        '<tr><th>HTML 본문 인용 검증</th><td>' +
        _field(source["html_text_node_status"]) +
        '</td></tr></table><p class="label">SHA-256은 로컬 바이트의 '
        '동일성만 확인하며 발행사 출처를 인증하지 않습니다.</p></section>'
        '<section><h2>04 / Risk · Guard</h2><p>Risk: ' +
        _field(risk["status"]) + '</p><ul>' +
        _reasons(risk["reason_codes"]) +
        '</ul><p>Guard 사유:</p><ul>' + _reasons(guard["reason_codes"]) +
        '</ul></section>'
        '<section><h2>05 / 감사 기록</h2><table>'
        '<tr><th>감사 이벤트 ID</th><td>' + _field(audit["event_id"]) + '</td></tr>'
        '<tr><th>감사 SHA-256</th><td><code>' + _field(audit["event_hash"]) +
        '</code></td></tr><tr><th>체인 / 사람 검토 무결성</th>'
        '<td>PASS / PASS (로컬 SQLite만)</td></tr></table></section>'
        '<footer>KUODRA OFFLINE_UNAUTHENTICATED · '
        '외부 SEC 인증 없음 · 투자 권고/거래 승인 없음 · '
        'DAKER 제출 영수증 아님</footer></main></body></html>'
    )
    encoded = page.encode("utf-8")
    if len(encoded) > 90000:
        raise ValueError("HTML_REPORT_OVERSIZED")
    return encoded
