"""Offline global issuer B/C review without a Nasdaq/price-input dependency.

Read-only deterministic orchestration of previously verified first-party
publisher receipts. This is NOT an authenticated SEC 10-K, licensed market
data, unrestricted peer evidence, full A/B/C, AI model or investment advice.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from urllib.parse import urlsplit
from typing import Any

from .guard_agent import evaluate_guard
from .real_issuer_ticker_review import review_supported_real_ticker
from .intel_amd_peer_cohort import review_two_official_10k_peers

_SCHEMA = "kuodra.global-fundamentals-marketless.v1"
_AS_OF = "2026-11-05"
_SUPPORTED = frozenset({"NVDA", "DELL"})
_STATUS = "GLOBAL_ISSUER_B_C_LIMITED_GUARD_HOLD"
_GUARD_POLICY = {
    "mode": "DEMO_POLICY",
    "version": "marketless-us-fundamentals-hold-v1",
    "max_debt_to_equity_pct": "200",
}


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "status": "BLOCKED", "reason_code": reason,
        "guard_policy_preview": "HOLD", "market_api_requests": 0,
        "external_sharing_allowed": False, "source_rights_verified": False,
        "full_abc_complete": False, "ai_agent_executed": False,
        "trade_executed": False,
    }


def _publisher_url(url: Any, ticker: str) -> bool:
    if type(url) is not str:
        return False
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)
                or parsed.fragment or parsed.query):
            return False
        host = parsed.hostname.lower()
        domains = {
            "NVDA": ("nvidia.com",),
            "DELL": ("delltechnologies.com", "dell.com"),
            "AMD": ("amd.com",),
            "INTC": ("intc.com",),
        }
        return any(host == d or host.endswith("." + d) for d in domains[ticker])
    except (ValueError, KeyError):
        return False


def build_marketless_global_review(*, ticker: str,
                                   as_of: str = _AS_OF) -> dict[str, Any]:
    """Recalculate an issuer-to-Guard evidence report with zero stock/NDX GET.

    The source receipt uses a fixed reviewed historical vintage; unknown
    issuers or future/unreviewed vintages fail closed, never guess.
    """
    if (type(ticker) is not str or type(as_of) is not str
            or ticker not in _SUPPORTED or as_of != _AS_OF):
        return _blocked("SUPPORTED_ISSUER_AND_PINNED_REVIEW_DATE_REQUIRED")
    try:
        issuer = review_supported_real_ticker(ticker, as_of=as_of)
        if (type(issuer) is not dict
                or issuer.get("status") != "REAL_ISSUER_HUMAN_REVIEW_ONLY"
                or issuer.get("ticker") != ticker
                or issuer.get("review_as_of") != as_of
                or issuer.get("publisher_original_observed") is not True
                or issuer.get("source_authenticated_by_sec") is not False
                or issuer.get("source_rights_verified") is not False
                or issuer.get("market_ndx_peer_licensed") is not False
                or issuer.get("engine_a_complete") is not False
                or issuer.get("full_abc_complete") is not False
                or issuer.get("guard_policy_preview") != "HOLD"
                or issuer.get("network_requests") != 0
                or issuer.get("trade_executed") is not False
                or not _publisher_url(issuer.get("source_url"), ticker)):
            return _blocked("FIRST_PARTY_ISSUER_RECEIPT_UNAVAILABLE")

        metrics = (
            "issuer_revenue_growth_pct",
            "cashflow_to_net_income_ratio",
            "receivables_minus_revenue_growth_pp",
            "inventory_minus_revenue_growth_pp",
        )
        from decimal import Decimal, InvalidOperation
        for key in metrics:
            value = issuer.get(key)
            if type(value) is not str or len(value) > 32:
                return _blocked("ISSUER_METRIC_INVALID")
            try:
                if not Decimal(value).is_finite():
                    return _blocked("ISSUER_METRIC_NONFINITE")
            except InvalidOperation:
                return _blocked("ISSUER_METRIC_NONDECIMAL")
        digest = issuer.get("source_sha256")
        if (type(digest) is not str or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            return _blocked("ISSUER_RECEIPT_DIGEST_INVALID")
        src = {
            "kind": issuer["source_kind"], "publisher_url": issuer["source_url"],
            "publisher_raw_sha256": digest, "actual_publisher_bytes_seen": True,
            "sec_edgar_raw_identity_verified": False,
            "publisher_rights_verified": False,
            "fiscal_latest_end": issuer["fiscal_latest_end"],
            "fiscal_prior_end": issuer["fiscal_prior_end"],
            "ci_source_run": issuer["source_ci_run"],
        }
        engine_b = {
            "status": "FIRST_PARTY_FINANCIAL_ARITHMETIC_REPLAY_LIMITED",
            "revenue_growth_pct": issuer["issuer_revenue_growth_pct"],
            "cashflow_to_net_income_ratio": issuer["cashflow_to_net_income_ratio"],
            "receivables_minus_revenue_growth_pp":
                issuer["receivables_minus_revenue_growth_pp"],
            "inventory_minus_revenue_growth_pp":
                issuer["inventory_minus_revenue_growth_pp"],
            "source_sha256": digest,
            "fraud_proven": False,
            "note": "Historical first-party issuer figures, not SEC original "
                    "authentication or a conclusive financial-risk finding.",
        }

        # Descriptive threshold screening only; this does not infer fraud.
        # Require exact source-linked numeric replay; never use float comparisons.
        review_signals = []
        for key, label in (
            ("receivables_minus_revenue_growth_pp", "RECEIVABLES_GROWTH_GAP"),
            ("inventory_minus_revenue_growth_pp", "INVENTORY_GROWTH_GAP"),
        ):
            gap = Decimal(engine_b[key])
            if gap >= Decimal("10.00"):
                review_signals.append({
                    "code": label, "growth_gap_pp": engine_b[key],
                    "threshold_pp": "10.00",
                    "interpretation": "DESCRIPTIVE_REVIEW_CANDIDATE_NOT_FRAUD",
                })
        engine_b["screening_status"] = (
            "REVIEW_CANDIDATES_PRESENT" if review_signals
            else "NO_SINGLE_PERIOD_THRESHOLD_TRIGGER"
        )
        engine_b["screening_signals"] = review_signals
        engine_b["screening_not_fraud_conclusion"] = True

        peers: list[dict[str, Any]] = []
        engine_c_status = "UNAVAILABLE_NO_SOURCE_BOUND_PEER_COHORT"
        if ticker == "NVDA":
            cohort = review_two_official_10k_peers(
                ticker=ticker, reviewed_as_of=as_of)
            if (type(cohort) is not dict
                    or cohort.get("status") !=
                        "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED"
                    or cohort.get("peer_count") != 2
                    or cohort.get("target_ticker") != ticker
                    or cohort.get("as_of") != as_of
                    or cohort.get("real_nvda_issuer_original_source_sha256") != digest
                    or cohort.get("fiscal_end_offsets_days") !=
                        {"AMD": 29, "INTC": 29}
                    or cohort.get("peer_rights_verified") is not False
                    or cohort.get("peer_sources_raw_byte_verified") is not False
                    or cohort.get("engine_c_complete") is not False
                    or cohort.get("network_requests") != 0
                    or cohort.get("guard_policy_preview") != "HOLD"):
                return _blocked("PEER_SOURCE_CROSSCHECK_FAILED")
            rows = cohort.get("revenue_growth_observations_not_sector_rank")
            if (type(rows) is not list or len(rows) != 3
                    or [r.get("ticker") for r in rows if type(r) is dict]
                    != ["NVDA", "AMD", "INTC"]):
                return _blocked("PEER_ROWS_INVALID")
            if (rows[0].get("actual_source_sha256") != digest
                    or any(r.get("actual_source_sha256") is not None
                           for r in rows[1:])):
                return _blocked("PEER_RAW_ORIGIN_MISLABELED")
            for row in rows[1:]:
                if not _publisher_url(row.get("source_url"), row["ticker"]):
                    return _blocked("PEER_PUBLISHER_URL_INVALID")
                peers.append({
                    "ticker": row["ticker"],
                    "fiscal_latest_end": row["fy_latest"],
                    "revenue_growth_pct": row["revenue_growth_pct"],
                    "publisher_url": row["source_url"],
                    "raw_peer_sha256": None,
                    "original_byte_authenticated": False,
                    "rights_verified": False,
                })
            engine_c_status = "TWO_HISTORICAL_PEER_REFERENCES_RAW_UNVERIFIED"

        guard = evaluate_guard(
            [{"status": "UNAVAILABLE",
              "source_kind": "MANUALLY_CURATED_UNVERIFIED"}],
            policy=dict(_GUARD_POLICY), risk=None)
        if (guard.get("schema") != "proofinvest.guard-decision.v1"
                or guard.get("decision") != "HOLD"
                or guard.get("reason_codes") !=
                    ["CLAIM_UNAVAILABLE", "RISK_UNAVAILABLE"]
                or guard.get("source_authenticated") is not False
                or guard.get("human_approved") is not False
                or guard.get("trade_executed") is not False):
            return _blocked("GUARD_FAIL_CLOSED_INVARIANT_BROKEN")
        report: dict[str, Any] = {
            "schema": _SCHEMA, "status": _STATUS,
            "ticker": ticker, "cik": issuer["cik"], "reviewed_as_of": as_of,
            "source": src,
            "engine_a": {
                "status": "UNAVAILABLE_NO_ENTITLED_MARKET_OR_NDX_DATA",
                "stock_return_pct": None, "beta": None,
                "market_rights_verified": False,
            },
            "engine_b": engine_b,
            "engine_c": {
                "status": engine_c_status, "peers": peers,
                "representative_sector_cohort_verified": False,
                "period_alignment_verified": False,
                "peer_republication_rights_verified": False,
            },
            "guard": guard,
            "trace": [
                {"step": 1, "tool": "review_supported_real_ticker",
                 "result": "PINNED_ISSUER_ORIGINAL_RECALCULATED"},
                {"step": 2, "tool": "review_two_official_10k_peers"
                 if ticker == "NVDA" else "peer_source_gate",
                 "result": engine_c_status},
                {"step": 3, "tool": "evaluate_guard",
                 "result": "HOLD_WITHOUT_AUTHENTICATED_RISK"},
                {"step": 4, "tool": "render_redacted_report",
                 "result": "LOCAL_HUMAN_REVIEW_ONLY"},
            ],
            "guard_policy_preview": "HOLD",
            "publisher_original_observed": True,
            "sec_original_identical": False,
            "market_api_requests": 0, "llm_requests": 0,
            "source_rights_verified": False,
            "external_sharing_allowed": False,
            "full_abc_complete": False, "ai_agent_executed": False,
            "human_approved": False,
            "investment_recommendation": False,
            "trade_executed": False,
            "limitations": [
                "This is a deterministic evidence orchestrator, not a live LLM Agent.",
                "First-party issuer original was observed, but SEC original identity "
                "and commercial/model/contest reuse rights are not established.",
                "Two peers for NVDA are historical manual 10-K references with "
                "unverified exact raw bytes and fiscal/segment comparability.",
                "No licensed stock/index observations; Engine A is unavailable.",
                "Guard HOLD is a safety decision, not a fraud or buy/sell verdict.",
            ],
        }
        raw = _canonical(report)
        if len(raw) > 32768:
            return _blocked("REPORT_TOO_LARGE")
        report["integrity_sha256"] = sha256(raw).hexdigest()
        return report
    except (KeyError, TypeError, ValueError, ArithmeticError,
            UnicodeError, RecursionError, OverflowError):
        return _blocked("SOURCE_OR_MATH_REPLAY_EXCEPTION")


def verify_marketless_global_review(report: Any) -> bool:
    """Independently rebuild all public arithmetic; reject even rehashed edits."""
    if (type(report) is not dict or report.get("status") != _STATUS
            or type(report.get("ticker")) is not str
            or type(report.get("reviewed_as_of")) is not str
            or type(report.get("integrity_sha256")) is not str):
        return False
    try:
        digest = report["integrity_sha256"]
        unsigned = dict(report)
        del unsigned["integrity_sha256"]
        if sha256(_canonical(unsigned)).hexdigest() != digest:
            return False
        return build_marketless_global_review(
            ticker=report["ticker"], as_of=report["reviewed_as_of"]) == report
    except (KeyError, ValueError, TypeError, OverflowError, RecursionError):
        return False


def marketless_global_review_html(report: Any) -> bytes:
    """Escaped source-linked report; refuses modified or unverifiable input."""
    if not verify_marketless_global_review(report):
        raise ValueError("UNVERIFIED_OR_TAMPERED_GLOBAL_REPORT")
    e = escape
    s = report["source"]
    b = report["engine_b"]
    c = report["engine_c"]
    rows = [
        ("A 시장 대비", "UNAVAILABLE — 승인된 주가·지수 없음"),
        ("B 매출 성장률 (%)", b["revenue_growth_pct"]),
        ("B 영업현금흐름/순이익", b["cashflow_to_net_income_ratio"]),
        ("B 매출채권 성장률 차이 (pp)",
         b["receivables_minus_revenue_growth_pp"]),
        ("B 재고 성장률 차이 (pp)",
         b["inventory_minus_revenue_growth_pp"]),
        ("B 검토 후보", ", ".join(
            x["code"] + " (" + x["growth_gap_pp"] + "pp)"
            for x in b["screening_signals"]) or "단일연도 임계값 미초과"),
        ("C 경쟁사", c["status"]),
        ("Guard", "HOLD · 미인증 근거 / 위험자료 부족"),
    ]
    table = "".join("<tr><th>" + e(k) + "</th><td>" + e(v) +
                    "</td></tr>" for k, v in rows)
    peers = "".join("<li>" + e(x["ticker"]) + ": " +
                    e(x["revenue_growth_pct"]) + "% (" +
                    e(x["fiscal_latest_end"]) + ") — " +
                    e(x["publisher_url"]) + "</li>"
                    for x in c["peers"])
    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="referrer" content="no-referrer">'
        '<title>KUODRA · 글로벌 발행사 제한 검산</title>'
        '<style>body{font:16px/1.6 system-ui,sans-serif;'
        'max-width:860px;margin:2rem auto;padding:0 1rem}'
        'table{border-collapse:collapse;width:100%}'
        'th,td{border:1px solid #bbb;padding:.5rem;text-align:left}'
        'th{width:45%}</style></head><body>'
        '<h1>KUODRA · 글로벌 발행사 B/C 검산 · HOLD</h1>'
        '<p>개인 로컬 검토용. SEC 원본 동일성·재이용권·AI 모델 처리권·'
        '시장 시세 권한은 미확인. 외부 배포 및 투자 권고 불가.</p>'
        '<p>종목 ' + e(report["ticker"]) + ' · 자료 기준일 ' +
        e(report["reviewed_as_of"]) + '</p><table>' + table +
        '</table><h2>발행사 원본 출처</h2><p>' +
        e(s["publisher_url"]) + '</p><p>원본 SHA-256: <code>' +
        e(s["publisher_raw_sha256"]) +
        '</code></p><h2>경쟁사 참고 출처 (원본 SHA 미확인)</h2><ul>' +
        peers + '</ul><p>내부 재검산 SHA-256: <code>' +
        e(report["integrity_sha256"]) +
        '</code></p><p>해시는 외부 출처 인증이나 라이선스가 아닙니다.'
        ' Agent/LLM 미실행, 외부 API 0회, 매매 0회.</p></body></html>'
    ).encode("utf-8")
    if len(html) > 32768:
        raise ValueError("LOCAL_HTML_TOO_LARGE")
    return html
