"""Offline verification against a manually checked primary financial statement.

The input is NOT fetched from OpenDART. A "verified" status asserts that a
claim agrees with two manually transcribed values in the evidence record,
not that the underlying PDF or its licensing has been independently audited.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .engine import amount

SOURCE_KIND = "MANUAL_PRIMARY_SOURCE_VERIFICATION"
SCOPE = "Claim arithmetic against a manually reviewed issuer PDF; no live document authentication"
EVIDENCE_PATH = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "samsung_2024_cfs_revenue.json"


def _valid_url(value: Any) -> bool:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        u = urlsplit(value)
        return u.scheme == "https" and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("missing period date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid period date") from exc


def _evidence_amounts(evidence: Any) -> tuple[Decimal, Decimal, str, int]:
    if not isinstance(evidence, Mapping):
        raise ValueError("missing evidence record")
    if evidence.get("evidence_type") != SOURCE_KIND:
        raise ValueError("unsupported evidence provenance")
    if evidence.get("report_type") != "ANNUAL" or evidence.get("financial_statement") != "CFS":
        raise ValueError("not one annual consolidated financial statement")
    if evidence.get("metric") != "revenue" or evidence.get("unit") != "KRW_MILLIONS":
        raise ValueError("wrong metric or incompatible unit")
    if not isinstance(evidence.get("subject"), str) or not evidence["subject"].strip():
        raise ValueError("issuer identity missing")
    report_year = evidence.get("report_year")
    if type(report_year) is not int or not 2015 <= report_year <= 2100:
        raise ValueError("invalid business year")
    current, previous = evidence.get("current"), evidence.get("previous")
    if not isinstance(current, Mapping) or not isinstance(previous, Mapping):
        raise ValueError("missing annual values")
    if current.get("fiscal_year") != report_year or previous.get("fiscal_year") != report_year - 1:
        raise ValueError("not consecutive fiscal years")
    for period, expected_year in ((current, report_year), (previous, report_year - 1)):
        begin, end = _date(period.get("period_start")), _date(period.get("period_end"))
        if begin != date(expected_year, 1, 1) or end != date(expected_year, 12, 31):
            raise ValueError("noncomparable annual periods")
    a, b = amount(current.get("amount")), amount(previous.get("amount"))
    if a is None or b is None or a < 0 or b <= 0:
        raise ValueError("missing, negative or zero-denominator revenue")
    source = evidence.get("primary_source")
    if not isinstance(source, Mapping) or source.get("visual_verified") is not True:
        raise ValueError("issuer PDF not manually reviewed")
    url = source.get("url")
    if not _valid_url(url) or not urlsplit(url).path.lower().endswith(".pdf"):
        raise ValueError("missing issuer PDF HTTPS URL")
    if not isinstance(source.get("publisher"), str) or not source["publisher"].strip():
        raise ValueError("source publisher missing")
    result = evidence.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("stored calculation missing")
    growth = ((a - b) / b * 100).quantize(Decimal("0.01"))
    expected_delta, expected_growth = amount(result.get("absolute_change")), amount(result.get("growth_pct_rounded_2dp"))
    if expected_delta != a - b or expected_growth != growth:
        raise ValueError("stored calculation disagrees with transcribed amounts")
    return a, b, url, report_year


def verify_growth_claim(evidence: Any, claim_pct: Any) -> dict[str, Any]:
    """Return verified/conflict/unavailable WITHOUT fetching any URL.

    verified = arithmetic agreement with provided manually reviewed evidence;
    NEVER an assertion of live OpenDART validation or independent PDF authenticity.
    """
    base: dict[str, Any] = {
        "metric": "revenue_yoy_pct",
        "state": "unavailable",
        "source_kind": SOURCE_KIND,
        "verification_scope": SCOPE,
        "statement": "CFS",
        "unit": "KRW_MILLIONS",
        "claim_pct": str(claim_pct) if claim_pct is not None else None,
        "computed_pct": None,
        "source_url": None,
        "dart_viewer_verified": False,
        "reason": "Evidence not validated",
    }
    try:
        current, previous, url, year = _evidence_amounts(evidence)
    except ValueError as exc:
        base["reason"] = str(exc)
        return base
    base["source_url"] = url
    base["fiscal_year"] = year
    # This path only reads caller-supplied JSON; it never opens the DART
    # viewer. A self-reported "direct_viewer_verified": true can be forged
    # and MUST NOT upgrade independent source authentication.
    # A future live verifier must produce a separately authenticated receipt.
    base["dart_viewer_verified"] = False
    computed = (current - previous) / previous * 100
    base["computed_pct"] = str(computed.quantize(Decimal("0.01")))
    claim = amount(claim_pct)
    if claim is None:
        base["reason"] = "Missing or malformed percentage claim"
        return base
    if abs(claim - computed) <= Decimal("0.1"):
        base["state"] = "verified"
        base["reason"] = "Numeric claim agrees with manually reviewed issuer statement (not independent authentication)"
    else:
        base["state"] = "conflict"
        base["reason"] = "Numeric claim differs from calculated growth by more than 0.1 percentage points"
    return base


def three_scenarios(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """A single traceable manual real-data input; third path has no evidence."""
    return {
        "mode": "OFFLINE_MANUAL_EVIDENCE",
        "scenarios": {
            "matching_claim": verify_growth_claim(evidence, "16.20"),
            "incorrect_claim": verify_growth_claim(evidence, "30"),
            "no_evidence": verify_growth_claim(None, "16.20"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline real-company evidence demo; no live API")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = three_scenarios(evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    expected = {"matching_claim": "verified", "incorrect_claim": "conflict", "no_evidence": "unavailable"}
    if {key: val["state"] for key, val in result["scenarios"].items()} != expected:
        raise SystemExit("Evidence scenario gate failed; inspect data before reporting")


if __name__ == "__main__":
    main()
