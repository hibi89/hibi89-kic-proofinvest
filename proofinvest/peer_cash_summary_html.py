"""HTML-only rendering of source-bound P91-P93 peer finance reviewer summary.

For offline evidence review, NOT publisher authentication, fraud, trading,
financial advice, or a merged Guard conclusion.
"""
from __future__ import annotations
from html import escape
import re

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)


def render_cash_peer_section(cash: dict, peer_receipt: dict,
                             issuer: dict, source: dict) -> str:
    """Print per-company and cohort WITHHELD values only after SHA/Guard checks."""
    def require(test, code="HTML_PEER_CASH_INVALID"):
        if not test:
            raise ValueError(code)

    def field(value):
        value = "WITHHELD" if value is None else value
        require(type(value) in (str, int))
        value = str(value)
        require(0 < len(value) <= 160 and all(ord(x) >= 32 for x in value))
        return escape(value, quote=True)

    false_flags = (
        "issuer_source_authenticated", "data_rights_verified",
        "point_in_time_verified", "cross_issuer_accounting_policy_verified",
        "accounting_fraud_proven", "guard_policy_modified",
        "audit_written", "trade_executed", "live_sec_called", "ai_generated",
    )
    require(type(cash) is dict and type(peer_receipt) is dict)
    require(cash.get("schema") == "kuodra.offline-peer-cash-conversion.v1")
    require(cash.get("issuer_cik") == issuer.get("cik")
            and cash.get("as_of") == issuer.get("as_of"))
    require(all(cash.get(x) is False for x in false_flags))
    rows = cash.get("rows")
    peer_rows = peer_receipt.get("peer_records")
    comp = cash.get("period_comparability")
    require(type(rows) is list and type(peer_rows) is list and
            1 <= len(peer_rows) <= 8 and len(rows) == len(peer_rows) + 1)
    require(type(comp) is dict and
            comp.get("schema") == "kuodra.peer-period-comparability-audit.v1")
    require(comp.get("candidate_count") == len(rows) and
            type(comp.get("coverage")) is list and
            len(comp["coverage"]) == len(rows))
    require(all(comp.get(k) is False for k in (
        "cross_issuer_accounting_policy_verified",
        "original_source_authenticated", "historical_vintage_authenticated",
        "data_rights_verified", "guard_policy_modified",
        "audit_written", "trade_executed",
    )))
    require(type(comp.get("current_cash_median_eligible")) is bool and
            type(comp.get("two_year_cash_median_eligible")) is bool)
    statuses = {
        "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED",
        "PERIOD_WINDOW_COMPARISON_WITHHELD",
        "INCOMPLETE_ACCOUNTING_METRICS_COMPARISON_WITHHELD",
    }
    trends = {
        "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED",
        "PERIOD_WINDOW_TWO_YEAR_COMPARISON_WITHHELD",
        "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD",
    }
    require(cash.get("status") in statuses and
            cash.get("two_year_trend_status") in trends)
    current_keys = ("cash_conversion_target_pct",
                    "cash_conversion_peer_median_pct",
                    "target_minus_peer_median_pp")
    trend_keys = ("two_year_target_change_pp",
                  "two_year_peer_median_change_pp",
                  "two_year_target_minus_peer_change_pp")
    current_ok = cash["status"] == "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED"
    trend_ok = cash["two_year_trend_status"] == (
        "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
    require(current_ok == comp["current_cash_median_eligible"] and
            trend_ok == comp["two_year_cash_median_eligible"])
    require(all((type(cash.get(k)) is str) is current_ok
                for k in current_keys))
    require(all((type(cash.get(k)) is str) is trend_ok
                for k in trend_keys))
    receipt_map = {p.get("peer_cik"): p for p in peer_rows
                   if type(p) is dict}
    require(len(receipt_map) == len(peer_rows))
    pieces = []
    seen = set()
    for i, (row, period) in enumerate(zip(rows, comp["coverage"])):
        require(type(row) is dict and type(period) is dict)
        cik = row.get("cik")
        sha = row.get("companyfacts_sha256")
        acc = row.get("accession_operator_supplied")
        require(type(cik) is str and _CIK.fullmatch(cik) is not None and
                cik not in seen and type(sha) is str and
                _SHA.fullmatch(sha) is not None and
                type(acc) is str and _ACC.fullmatch(acc) is not None)
        seen.add(cik)
        require(row.get("role") == ("TARGET" if i == 0 else "PEER") and
                period.get("cik") == cik and
                period.get("companyfacts_sha256") == sha and
                row.get("source_authenticated") is False)
        if i == 0:
            require(cik == issuer.get("cik") and
                    sha == source.get("companyfacts_sha256") and
                    acc == issuer.get("accession"))
        else:
            receipt = receipt_map.get(cik)
            require(type(receipt) is dict and
                    receipt.get("companyfacts_sha256") == sha and
                    receipt.get("accession") == acc)
        traj = row.get("cash_conversion_trend")
        require(type(traj) is dict and
                traj.get("companyfacts_sha256") == sha and
                all(traj.get(x) is False for x in (
                    "source_authenticated", "guard_policy_modified",
                    "trade_executed", "accounting_policy_comparability_verified",
                )))
        pieces.append(
            "<tr><th>" + field(cik) + "</th><td>" + field(acc) +
            "</td><td>" + field(row.get("cash_conversion_pct")) +
            "</td><td>" + field(traj.get("change_pp")) +
            "</td><td>" + field(period.get("withheld_reason") or
                                 row.get("accounting_reason_code")) +
            "</td></tr>"
        )
    require(seen - {issuer["cik"]} == set(receipt_map))
    metrics = (
        ("올해 분석 상태", cash["status"]),
        ("2개 연도 상태", cash["two_year_trend_status"]),
        ("올해 구간 검증", comp["current_status"]),
        ("2개 연도 구간 검증", comp["two_year_status"]),
        ("매출 계정명", comp["revenue_concept_status"]),
        ("선택 기업 CFO/NI (%)", cash["cash_conversion_target_pct"]),
        ("경쟁사 중위 CFO/NI (%)", cash["cash_conversion_peer_median_pct"]),
        ("현금전환율 격차 (pp)", cash["target_minus_peer_median_pp"]),
        ("선택 기업 2개 연도 변화 (pp)", cash["two_year_target_change_pp"]),
        ("경쟁사 변화 중위 (pp)", cash["two_year_peer_median_change_pp"]),
        ("2개 연도 변화 격차 (pp)", cash["two_year_target_minus_peer_change_pp"]),
    )
    table = "".join("<tr><th>" + field(k) + "</th><td>" + field(v) +
                    "</td></tr>" for k, v in metrics)
    return (
        '<section><h2>02F-3 / Engine B × C 경쟁사 현금전환 비교 (로컬)</h2>'
        '<p>선택한 모든 회사의 연간 수치·회계기간이 일치하지 않으면 '
        '중위 비교는 WITHHELD입니다. 로컬 해시 일치는 SEC 원본 출처·'
        '재무제표 회계정책·배포권리 인증이 아닙니다.</p><table>' +
        table + '</table><table><tr><th>CIK</th><td>접수번호</td>'
        '<td>올해 CFO/NI (%)</td><td>2개 연도 변화 (pp)</td>'
        '<td>검토 사유</td></tr>' + "".join(pieces) + '</table></section>'
    )
