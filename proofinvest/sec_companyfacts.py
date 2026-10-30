"""Offline, fail-closed SEC CompanyFacts revenue verification (NOT live API/LLM)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import json
import re
from typing import Any, Mapping

TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
# Alternative total-revenue concepts, not components and not additive.
REVENUE_TAGS = (TAG, "Revenues", "SalesRevenueNet")
MAX_ROWS = 10_000
MAX_AMOUNT = 10**17


def _date(raw: Any) -> date | None:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        d = date.fromisoformat(raw)
        return d if d.isoformat() == raw else None
    except ValueError:
        return None


def _out(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema": "proofinvest.sec-companyfacts-offline.v1",
        "source_kind": "CALLER_SUPPLIED_SEC_FORMAT_NOT_AUTHENTICATED",
        "status": "unavailable", "reason_code": reason,
        "current_usd": None, "prior_usd": None, "growth_pct": None,
        "sec_filing_index": None, "live_api_called": False,
        "authenticated_external_source": False, "source_rights_verified": False,
        "ai_agent_executed": False, "risk_calculated": False,
        "official_contest_submission": False, **extra,
    }


def _verify_one_revenue_concept(
    companyfacts: Any, *, cik: str, accession: str,
    current_end: str, prior_end: str, as_of: str,
    claimed_growth_pct: str | None = None, concept: str = TAG,
) -> dict[str, Any]:
    """Compare annual USD values of ONE SEC concept from ONE 10-K, as-of.

    Supplied JSON is untrusted; syntactically valid SEC links do NOT authenticate
    its source. This function performs no network, model or trading action.
    """
    if (not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik)
            or not isinstance(accession, str)
            or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession)
            or accession[:10] != cik):
        return _out("INVALID_INPUT")
    asof, curr, prev = _date(as_of), _date(current_end), _date(prior_end)
    if not all((asof, curr, prev)) or not prev < curr:
        return _out("INVALID_INPUT")
    if not 330 <= (curr - prev).days <= 380:
        return _out("NONCONSECUTIVE_FISCAL_YEARS")
    if not isinstance(companyfacts, Mapping):
        return _out("INVALID_INPUT")
    issuer = companyfacts.get("cik")
    if (type(issuer) not in (int, str) or not str(issuer).isascii()
            or not str(issuer).isdecimal() or len(str(issuer)) > 10
            or str(int(issuer)).zfill(10) != cik):
        return _out("CIK_MISMATCH")
    root = companyfacts.get("facts")
    usgaap = root.get("us-gaap") if isinstance(root, Mapping) else None
    tag = usgaap.get(concept) if isinstance(usgaap, Mapping) else None
    units = tag.get("units") if isinstance(tag, Mapping) else None
    rows = units.get("USD") if isinstance(units, Mapping) else None
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        return _out("MISSING_OR_OVERSIZED_REVENUE_RECORDS")
    if set(units) != {"USD"}:
        return _out("UNSUPPORTED_OR_MIXED_UNITS")
    matches: dict[date, list[tuple[int, date, date]]] = {curr: [], prev: []}
    future = False
    for item in rows:
        if not isinstance(item, Mapping):
            return _out("INVALID_FACT_RECORD")
        if item.get("accn") != accession or item.get("form") != "10-K":
            continue
        end = _date(item.get("end"))
        if end not in matches:
            continue
        start, filed = _date(item.get("start")), _date(item.get("filed"))
        if start is None or filed is None or not start < end or not 330 <= (end - start).days <= 380:
            return _out("INVALID_ANNUAL_PERIOD_OR_FILING_DATE")
        if filed < end:
            return _out("INVALID_FILING_CHRONOLOGY")
        if filed > asof:
            future = True
            continue
        value = item.get("val")
        if type(value) is not int or not 0 <= value <= MAX_AMOUNT:
            return _out("INVALID_USD_REVENUE")
        matches[end].append((value, start, filed))
    if any(not values for values in matches.values()):
        return _out("FILING_AFTER_AS_OF" if future else "ANNUAL_FACTS_UNAVAILABLE")
    if any(len(set(values)) != 1 for values in matches.values()):
        return _out("AMBIGUOUS_ANNUAL_FACTS")
    current, previous = [next(iter(set(matches[d]))) for d in (curr, prev)]
    if current[2] != previous[2]:
        return _out("MIXED_FILING_DATES")
    if not 1 <= (current[1] - prev).days <= 8:
        return _out("FISCAL_PERIOD_GAP")
    if previous[0] == 0:
        return _out("ZERO_PRIOR_REVENUE")
    try:
        growth = (Decimal(current[0]) / Decimal(previous[0]) - 1) * 100
        shown = str(growth.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ArithmeticError, OverflowError, ZeroDivisionError):
        return _out("ARITHMETIC_UNREPRESENTABLE")
    state, reason = "calculated_unverified", "STRUCTURAL_NUMERIC_COMPARISON_ONLY"
    if claimed_growth_pct is not None:
        if not isinstance(claimed_growth_pct, str) or re.fullmatch(r"[+-]?\d{1,5}(?:\.\d{1,4})?", claimed_growth_pct) is None:
            return _out("INVALID_GROWTH_CLAIM")
        try:
            if abs(growth - Decimal(claimed_growth_pct)) > Decimal("0.10"):
                state, reason = "conflict", "GROWTH_CLAIM_CONFLICT"
        except InvalidOperation:
            return _out("INVALID_GROWTH_CLAIM")
    return {
        **_out(reason), "status": state,
        "current_usd": str(current[0]), "prior_usd": str(previous[0]),
        "growth_pct": shown,
        "sec_filing_index": "https://www.sec.gov/Archives/edgar/data/"
                            f"{int(cik)}/{accession.replace('-', '')}/"
                            f"{accession}-index.htm",
        "cik": cik, "accession": accession, "as_of": as_of,
        "annual_period_ends": [prior_end, current_end],
        "annual_period_starts": [previous[1].isoformat(), current[1].isoformat()],
        "filing_date": current[2].isoformat(),
        "revenue_concept": concept,
    }


def _target_concept_rows(tag: Any, *, accession: str,
                         current_end: str, prior_end: str) -> bool:
    """Whether an incomplete alternative claims this accession/period.

    Do not silently ignore a partial same-filing concept in favor of another.
    """
    if not isinstance(tag, Mapping):
        return True
    units = tag.get("units")
    if not isinstance(units, Mapping) or set(units) != {"USD"}:
        return True
    rows = units.get("USD")
    if not isinstance(rows, list):
        return True
    for row in rows:
        if not isinstance(row, Mapping):
            return True
        if (row.get("accn") == accession and row.get("form") == "10-K"
                and row.get("end") in (current_end, prior_end)):
            return True
    return False


def verify_sec_annual_revenue(
    companyfacts: Any, *, cik: str, accession: str,
    current_end: str, prior_end: str, as_of: str,
    claimed_growth_pct: str | None = None,
) -> dict[str, Any]:
    """Select exactly one allowlisted total-revenue concept, fail closed.

    All complete concepts for this ONE accession must agree on both annual
    amounts and filing date. A partial/invalid concept on these same periods
    blocks the fallback; we never combine periods or components across tags.
    Earlier single-concept behavior and claim thresholds are preserved.
    """
    args = dict(cik=cik, accession=accession, current_end=current_end,
                prior_end=prior_end, as_of=as_of)
    usgaap = None
    if isinstance(companyfacts, Mapping):
        facts = companyfacts.get("facts")
        if isinstance(facts, Mapping):
            candidate = facts.get("us-gaap")
            if isinstance(candidate, Mapping):
                usgaap = candidate
    present = [concept for concept in REVENUE_TAGS
               if usgaap is not None and concept in usgaap]
    if not present:
        return _verify_one_revenue_concept(
            companyfacts, **args, claimed_growth_pct=claimed_growth_pct
        )
    reviewed = {
        concept: _verify_one_revenue_concept(companyfacts, **args, concept=concept)
        for concept in present
    }
    # An explicit primary tag must not be silently overridden by a fallback
    # when it is invalid or incomplete for the selected issuer.
    if (TAG in reviewed
            and reviewed[TAG]["status"] != "calculated_unverified"
            and _target_concept_rows(
                usgaap[TAG], accession=accession,
                current_end=current_end, prior_end=prior_end,
            )):
        return _verify_one_revenue_concept(
            companyfacts, **args, concept=TAG,
            claimed_growth_pct=claimed_growth_pct
        )
    good = [c for c in present if reviewed[c]["status"] == "calculated_unverified"]
    if not good:
        return reviewed[present[0]]
    chosen = good[0]
    chosen_facts = reviewed[chosen]
    for concept in present:
        if concept == chosen:
            continue
        alternative = reviewed[concept]
        if alternative["status"] == "calculated_unverified":
            if any(alternative.get(key) != chosen_facts.get(key) for key in
                   ("current_usd", "prior_usd", "filing_date",
                    "annual_period_starts")):
                return _out("REVENUE_CONCEPT_CONFLICT")
        elif _target_concept_rows(
            usgaap[concept], accession=accession,
            current_end=current_end, prior_end=prior_end,
        ):
            return _out("REVENUE_CONCEPT_INCOMPLETE_OR_INVALID")
    return _verify_one_revenue_concept(
        companyfacts, **args, concept=chosen,
        claimed_growth_pct=claimed_growth_pct,
    )


def run_curated_apple_demo(*, as_of: str = "2025-11-01",
                           claimed_growth_pct: str | None = None) -> dict[str, Any]:
    """Real calculation on *human-curated*, public 10-K numbers, not SEC API bytes."""
    path = Path(__file__).resolve().parents[1] / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
    if path.stat().st_size > 100_000:
        raise ValueError("Curated SEC-format excerpt exceeds safe bound")
    record = json.loads(path.read_text(encoding="utf-8"))
    result = verify_sec_annual_revenue(
        record, cik="0000320193", accession="0000320193-25-000079",
        current_end="2025-09-27", prior_end="2024-09-28",
        as_of=as_of, claimed_growth_pct=claimed_growth_pct,
    )
    return {**result, "demonstration_source": "HUMAN_CURATED_FROM_PUBLIC_SEC_10K_NOT_RAW_API"}
