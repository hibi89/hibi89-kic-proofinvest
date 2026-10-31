"""Engine B synthetic issuer/filed-at accounting-quality regression tests."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from proofinvest.kic_dl_demo import SYNTHETIC_CIK, SYNTHETIC_ACCESSION, AS_OF, synthetic_companyfacts
from proofinvest.accounting_integrity import review_accounting_integrity

END, PRIOR = "2025-09-30", "2024-09-30"
NI = "NetIncomeLoss"
OI = "OperatingIncomeLoss"
CFO = "NetCashProvidedByUsedInOperatingActivities"
AR = "AccountsReceivableNetCurrent"
INV = "InventoryNet"


def _annual(amount, end=END, start="2024-10-01", accession=SYNTHETIC_ACCESSION,
            filed="2025-10-15"):
    return {"accn": accession, "form": "10-K", "start": start, "end": end,
            "filed": filed, "val": amount}


def _instant(amount, end=END, accession=SYNTHETIC_ACCESSION,
             filed="2025-10-15"):
    return {"accn": accession, "form": "10-K", "end": end,
            "filed": filed, "val": amount}


def fixture(*, ni=60, cfo=20, ar_now=90, ar_old=20, inventory_now=60,
            inventory_old=40, accession=SYNTHETIC_ACCESSION):
    data = synthetic_companyfacts()
    gaap = data["facts"]["us-gaap"]
    for tag, value in ((NI, ni), (OI, 80), (CFO, cfo)):
        if value is not None:
            gaap[tag] = {"units": {"USD": [_annual(value, accession=accession)]}}
    for tag, now, old in ((AR, ar_now, ar_old),
                          (INV, inventory_now, inventory_old)):
        if now is not None:
            gaap[tag] = {"units": {"USD": [_instant(now, accession=accession),
                                           _instant(old, end=PRIOR, accession=accession)]}}
    return data


def review(data, accession=SYNTHETIC_ACCESSION, asof=AS_OF):
    return review_accounting_integrity(
        json.dumps(data).encode(), cik=SYNTHETIC_CIK, accession=accession,
        current_end=END, prior_end=PRIOR, as_of=asof,
    )


class AccountingIntegrityTests(unittest.TestCase):
    def test_positive_income_low_cfo_and_receivables_gap(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO NETWORK")) as net:
            out = review(fixture())
        net.assert_not_called()
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertEqual(out["net_income_usd"], "60")
        self.assertEqual(out["operating_income_usd"], "80")
        self.assertEqual(out["operating_cashflow_usd"], "20")
        self.assertEqual(out["earnings_less_cash_usd"], "40")
        self.assertEqual(out["cash_to_net_income_pct"], "33.33")
        self.assertEqual(out["earnings_cash_signal"], "CFO_BELOW_POSITIVE_EARNINGS")
        self.assertEqual(out["receivables_growth_pct"], "350.00")
        self.assertEqual(out["revenue_growth_pct"], "100.00")
        self.assertEqual(out["receivables_minus_revenue_growth_pp"], "250.00")
        self.assertEqual(out["inventory_minus_revenue_growth_pp"], "-50.00")
        self.assertEqual(out["working_capital_signals"], ["RECEIVABLES_OUTPACED_REVENUE"])
        self.assertEqual(out["working_capital_review_status"], "REVIEWED_UNVERIFIED")
        for key in ("source_authenticated", "accounting_fraud_proven",
                    "guard_policy_modified", "ai_generated", "trade_executed",
                    "live_api_called"):
            self.assertIs(out[key], False)

    def test_positive_earnings_negative_cash_is_review_candidate_not_fraud(self):
        out = review(fixture(ni=45, cfo=-25))
        self.assertEqual(out["earnings_cash_signal"], "POSITIVE_EARNINGS_NEGATIVE_CFO")
        self.assertEqual(out["earnings_less_cash_usd"], "70")
        self.assertFalse(out["accounting_fraud_proven"])

    def test_non_positive_income_withholds_cash_ratio(self):
        for income in (-10, 0):
            with self.subTest(income=income):
                out = review(fixture(ni=income, cfo=20))
                self.assertEqual(out["status"], "reviewed_unverified")
                self.assertIsNone(out["cash_to_net_income_pct"])
                self.assertEqual(out["earnings_cash_signal"],
                                 "NON_POSITIVE_NET_INCOME_RATIO_UNDEFINED")

    def test_missing_net_income_never_invents_earnings(self):
        out = review(fixture(ni=None))
        self.assertEqual(out["status"], "unavailable")
        self.assertIsNone(out["earnings_less_cash_usd"])

    def test_bad_optional_inventory_is_partial_not_safe(self):
        data = fixture()
        data["facts"]["us-gaap"][INV]["units"]["USD"][0]["filed"] = "2025-10-16"
        out = review(data)
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertEqual(out["working_capital_review_status"], "PARTIAL_OR_CONFLICT")
        self.assertIsNone(out["inventory_growth_pct"])
        self.assertIn("RECEIVABLES_OUTPACED_REVENUE", out["working_capital_signals"])

    def test_optional_missing_tags_are_not_healthy(self):
        out = review(fixture(ar_now=None, inventory_now=None))
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertEqual(out["working_capital_review_status"], "UNAVAILABLE")
        self.assertEqual(out["working_capital_signals"], [])

    def test_zero_previous_balance_never_divides(self):
        out = review(fixture(ar_old=0))
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertIsNone(out["receivables_growth_pct"])
        self.assertEqual(out["working_capital_review_status"], "PARTIAL_OR_CONFLICT")

    def test_future_income_filing_cannot_be_used(self):
        doc = fixture()
        doc["facts"]["us-gaap"][NI]["units"]["USD"][0]["filed"] = "2025-10-17"
        out = review(doc)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["reason_code"], "CASHFLOW_FILING_AFTER_AS_OF")

    def test_mismatched_period_income_vs_cfo_is_blocked(self):
        doc = fixture()
        doc["facts"]["us-gaap"][NI]["units"]["USD"][0]["start"] = "2024-10-02"
        out = review(doc)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["reason_code"], "MIXED_ANNUAL_PERIOD_OR_FILING_DATE")

    def test_wrong_issuer_or_invalid_accession(self):
        doc = fixture()
        doc["cik"] = 2
        self.assertEqual(review(doc)["reason_code"], "COMPANYFACTS_CIK_MISMATCH")
        self.assertEqual(review(fixture(), accession="invalid")["reason_code"], "INVALID_INPUT")

    def test_third_party_submitter_accession_is_valid_with_exact_issuer_facts(self):
        agent = "0009999999-25-000123"
        doc = fixture(accession=agent)
        for row in doc["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]:
            row["accn"] = agent
        out = review(doc, accession=agent)
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertEqual(out["net_income_usd"], "60")
        self.assertFalse(out["source_authenticated"])

    def test_bad_cfo_annual_period_withholds(self):
        doc = fixture()
        doc["facts"]["us-gaap"][CFO]["units"]["USD"][0]["start"] = "2025-07-01"
        self.assertEqual(review(doc)["status"], "unavailable")

    def test_mixed_currency_optional_rejected_not_assumed_empty(self):
        doc = fixture()
        doc["facts"]["us-gaap"][AR]["units"]["EUR"] = []
        out = review(doc)
        self.assertEqual(out["working_capital_review_status"], "PARTIAL_OR_CONFLICT")
        self.assertIsNone(out["receivables_growth_pct"])

    def test_boolean_value_and_duplicate_income_fail(self):
        doc = fixture()
        doc["facts"]["us-gaap"][NI]["units"]["USD"][0]["val"] = True
        self.assertEqual(review(doc)["status"], "unavailable")
        doc = fixture()
        doc["facts"]["us-gaap"][NI]["units"]["USD"].append(_annual(61))
        self.assertEqual(review(doc)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
