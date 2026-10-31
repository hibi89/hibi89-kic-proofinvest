"""Static offline KUODRA operator-replay report, without unsafe user HTML.

Only a *completed*, provenance-limited, SQLite-audited P7 result is eligible.
This renderer never reads originals, executes code, writes files or calls APIs.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

from .sec_companyfacts import REVENUE_TAGS

_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)
_INTENTS = frozenset(("GROWTH_CHECK", "SOURCE_REVIEW", "RISK_CHECK"))


def _clean(value: Any, *, limit: int = 128) -> str:
    if type(value) not in (str, int):
        raise ValueError("HTML_UNSAFE_FIELD_TYPE")
    string = str(value)
    if not 0 < len(string) <= limit or any(ord(x) < 32 or ord(x) == 127 for x in string):
        raise ValueError("HTML_UNSAFE_FIELD_VALUE")
    return escape(string, quote=True)


def _reasons(obj: Any) -> str:
    if not isinstance(obj, list) or len(obj) > 20:
        raise ValueError("HTML_INVALID_GUARD_REASONS")
    return "".join("<li>" + _clean(x, limit=160) + "</li>" for x in obj)


def _optional_display(card: dict[str, Any], field: str, *, suffix: str = "") -> str:
    """Unavailable numeric fields must never be imputed or shown as None."""
    if card["status"] != "reviewed_unverified" or card.get(field) is None:
        return "Unavailable"
    return _clean(card[field]) + suffix


def render_kuodra_operator_html(report: Any) -> bytes:
    """Safely render a human-auditable, NON-AUTHENTICATED research receipt."""
    if (type(report) is not dict
            or report.get("schema") != "kuodra.operator-gated-offline-proposal.v1"
            or report.get("status") != "completed"
            or report.get("model_proposal_accepted") is not True
            or report.get("audit_written") is not True
            or report.get("local_tool_attempts") != 1
            or report.get("max_local_tool_attempts") != 1
            or report.get("selected_intent") not in _INTENTS
            or report.get("network_calls") != 0
            or report.get("external_tool_calls") != 0
            or any(report.get(flag) is not False for flag in (
                "source_authenticated", "source_rights_verified",
                "ai_agent_executed", "live_model_called", "live_sec_called",
                "trade_executed", "official_contest_submission",
            ))):
        raise ValueError("HTML_UNTRUSTED_RESULT_CONTRACT")
    issuer, source, finance, balance, guard, audit = (
        report.get(key) for key in (
            "issuer", "source_review", "verification",
            "balance_sheet", "guard", "audit"
        )
    )
    if any(type(x) is not dict for x in
           (issuer, source, finance, balance, guard, audit)):
        raise ValueError("HTML_RESULT_SECTION_MISSING")
    cik, acc, asof = (issuer.get(k) for k in ("cik", "accession", "as_of"))
    if (type(cik) is not str or _CIK.fullmatch(cik) is None
            or type(acc) is not str or _ACC.fullmatch(acc) is None
            # Subject CIK comes from the linked report, not submitter prefix.
            or type(asof) is not str or _DATE.fullmatch(asof) is None
            or guard.get("decision") not in ("HOLD", "REJECT")
            or guard.get("source_authenticated") is not False
            or guard.get("trade_executed") is not False
            or finance.get("status") not in ("calculated_unverified", "conflict")
            or (finance["status"] == "conflict") != (guard["decision"] == "REJECT")
            or finance.get("revenue_concept") not in REVENUE_TAGS
            or balance.get("source_authenticated") is not False
            or balance.get("risk_authenticated") is not False
            or balance.get("guard_policy_modified") is not False
            or balance.get("status") not in ("reviewed_unverified", "unavailable")
            or source.get("source_authenticated") is not False
            or source.get("source_rights_verified") is not False
            or type(source.get("exact_raw_byte_span_verified")) is not bool
            or any(type(source.get(k)) is not str or
                   _SHA.fullmatch(source[k]) is None for k in (
                       "submissions_sha256", "companyfacts_sha256",
                       "archived_original_sha256",
                   ))
            or type(audit.get("event_hash")) is not str
            or _SHA.fullmatch(audit["event_hash"]) is None):
        raise ValueError("HTML_REVIEW_INTEGRITY_FAILED")
    # P33: operator receipts now expose panels already computed inside
    # the exact same offline replay. They are descriptive ONLY, must carry
    # the original unverified policy flags and cannot change Guard.
    risk, shares, cashflow, capital = (
        report.get(k) for k in (
            "risk", "share_capital", "cashflow", "capital_filing_watch"
        )
    )
    if any(type(x) is not dict for x in (risk, shares, cashflow, capital)):
        raise ValueError("HTML_AUXILIARY_SECTION_MISSING")
    if (risk.get("status") not in ("reviewed_unverified", "unavailable")
            or any(risk.get(k) is not False for k in (
                "source_authenticated", "investment_recommendation", "trade_authorized"))
            or shares.get("status") not in ("reviewed_unverified", "unavailable")
            or shares.get("shares_change_is_not_dilution_or_issuance") is not True
            or any(shares.get(k) is not False for k in (
                "source_authenticated", "source_rights_verified",
                "ownership_verified", "guard_policy_modified", "trade_executed"))
            or cashflow.get("status") not in ("reviewed_unverified", "unavailable")
            or cashflow.get("free_cashflow_proxy_is_non_gaap") is not True
            or any(cashflow.get(k) is not False for k in (
                "source_authenticated", "source_rights_verified",
                "risk_authenticated", "guard_policy_modified", "trade_executed"))
            or capital.get("status") not in (
                "metadata_candidates_unverified",
                "no_candidates_in_limited_issuer_index", "unavailable"
            )
            or capital.get("issuer_recent_window_only") is not True
            or capital.get("other_filers_cik_not_queried") is not True
            or any(capital.get(k) is not False for k in (
                "source_authenticated", "source_rights_verified",
                "beneficial_ownership_verified", "filing_contents_verified",
                "guard_policy_modified", "trade_executed"))):
        raise ValueError("HTML_AUXILIARY_TRUST_CONTRACT_VIOLATION")
    if report["selected_intent"] == "RISK_CHECK" and balance["status"] != "reviewed_unverified":
        raise ValueError("HTML_REQUIRED_RISK_UNAVAILABLE")
    if (report["selected_intent"] == "SOURCE_REVIEW"
            and source["exact_raw_byte_span_verified"] is not True):
        raise ValueError("HTML_REQUIRED_SOURCE_SPAN_UNAVAILABLE")

    # Only escape bounded scalars and short guard-generated reason codes.
    fields = [
        ("CIK", _clean(cik)),
        ("SEC accession", _clean(acc)),
        ("As-of (self-reported)", _clean(asof)),
        ("Intent", _clean(report["selected_intent"])),
        ("Revenue concept", _clean(finance["revenue_concept"])),
        ("Prior revenue USD", _clean(finance.get("prior_amount"))),
        ("Current revenue USD", _clean(finance.get("current_amount"))),
        ("Revenue growth (unverified)", _clean(finance.get("growth_pct")) + "%"),
        ("Balance calculation status", _clean(balance["status"])),
        ("Total liabilities / equity", (
            _clean(balance["liabilities_to_equity_pct"]) + "%"
            if balance.get("liabilities_to_equity_pct") is not None else "Unavailable"
        )),
        ("Equity denominator basis", (
            _clean(balance["equity_denominator_basis"])
            if balance.get("equity_denominator_basis") is not None else "Unavailable"
        )),
        ("Original visible text span checked", (
            "YES (local bytes only)" if source["exact_raw_byte_span_verified"]
            else "NO"
        )),
        ("Guard HOLD/REJECT", _clean(guard["decision"])),
        ("Audit event ID", _clean(audit.get("event_id"))),
        ("Audit SHA-256", _clean(audit["event_hash"])),
        ("Submissions SHA-256", _clean(source["submissions_sha256"])),
        ("CompanyFacts SHA-256", _clean(source["companyfacts_sha256"])),
        ("Original filing SHA-256", _clean(source["archived_original_sha256"])),
    ]
    table = "".join(
        "<tr><th>" + escape(label) + "</th><td>" + value + "</td></tr>"
        for label, value in fields
    )
    extra = [
        ("Local risk review status", _clean(risk["status"])),
        ("Share snapshot status", _clean(shares["status"])),
        ("Shares outstanding (not ownership)", _optional_display(shares, "shares_outstanding")),
        ("Share count change (not dilution)", _optional_display(shares, "shares_change_pct", suffix="%")),
        ("Operating cash flow USD", _optional_display(cashflow, "operating_cashflow_usd")),
        ("Capex payments USD", _optional_display(cashflow, "capex_payments_usd")),
        ("Free cash flow proxy USD (NON-GAAP)", (
            _optional_display(cashflow, "free_cashflow_proxy_usd")
            if cashflow.get("free_cashflow_proxy_status")
            == "same_10k_period_non_gaap_unverified" else "Unavailable"
        )),
        ("Issuer capital metadata status", _clean(capital["status"])),
        ("Recent issuer metadata candidates", (
            _clean(capital.get("total_matching_recent_metadata"))
            if capital["status"] in (
                "metadata_candidates_unverified",
                "no_candidates_in_limited_issuer_index"
            ) else "Unavailable"
        )),
    ]
    # A missing/invalid panel cannot become a numeric success merely because
    # some other section of the same 10-K was reviewable.
    extra_table = "".join(
        "<tr><th>" + escape(label) + "</th><td>" + value + "</td></tr>"
        for label, value in extra
    )
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src '
        "&#39;none&#39;; style-src &#39;unsafe-inline&#39;; "
        'base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<title>KUODRA — Offline Evidence Review</title>'
        '<style>body{font:16px/1.6 system-ui,sans-serif;background:#f4f7fb;'
        'color:#182e46;margin:0}main{max-width:900px;margin:32px auto;'
        'padding:0 20px}header{padding:26px;background:#15344f;color:white;'
        'border-radius:12px}h1{font-size:1.7rem}section{background:white;'
        'padding:22px;border-radius:12px;margin-top:16px}'
        'table{width:100%;border-collapse:collapse}th,td{padding:10px;'
        'border-bottom:1px solid #dde3eb;text-align:left;overflow-wrap:anywhere}'
        'th{width:36%}.warning{border-left:6px solid #a75233}'
        'code{font-size:.85em}ul{margin-top:8px}</style></head>'
        '<body><main><header><h1>KUODRA — Offline Research Receipt</h1>'
        '<p>Financial calculations · source hashes · Guard · SQLite audit</p>'
        '</header><section class="warning"><strong>UNVERIFIED LOCAL SOURCE</strong>'
        '<p>These local files and self-reported observation times are NOT '
        'SEC-authenticated. No investment recommendation, trade authorization, '
        'live model, network API, or official contest submission. '
        'HOLD means review remains blocked, NOT approved.</p></section>'
        '<section><h2>Review facts</h2><table>' + table +
        '</table></section><section><h2>Additional local research panels</h2>'
        '<p>Untrusted issuer-format numbers only. Share-count change does '
        'not establish issuance, dilution or beneficial ownership. '
        'Free cash flow is a simplified NON-GAAP proxy, not cash available '
        'for distribution. Issuer recent metadata omits older and '
        'other-filer filings; zero candidates proves nothing.</p>'
        '<table>' + extra_table + '</table></section>'
        '<section><h2>Guard reasons</h2><ul>' +
        _reasons(guard.get("reason_codes")) + '</ul></section>'
        '<footer><p>SHA-256 checks local bytes only; source rights are '
        'not independently verified. Human review required.</p></footer>'
        '</main></body></html>'
    )
    raw = page.encode("utf-8")
    if len(raw) > 50_000:
        raise ValueError("HTML_REPORT_OVERSIZED")
    return raw
