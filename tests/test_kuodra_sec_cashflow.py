"""P28 offline annual CFO/capex reconciled to one 10-K, no policy change."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_sec_cashflow import review_sec_annual_cashflow
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.guard_audit import GuardAuditStore

_CFO="NetCashProvidedByUsedInOperatingActivities"
_CAPEX="PaymentsToAcquirePropertyPlantAndEquipment"
_END="2025-09-30"


def fact(value, *, tag=_CFO, start="2024-10-01", filed="2025-10-15",
         accession=SYNTHETIC_ACCESSION):
    return {"accn":accession,"form":"10-K","start":start,
            "end":_END,"filed":filed,"val":value}


def fixture(cfo=200, capex=30):
    doc=synthetic_companyfacts()
    if cfo is not None:
        doc["facts"]["us-gaap"][_CFO]={"units":{"USD":[fact(cfo)]}}
    if capex is not None:
        doc["facts"]["us-gaap"][_CAPEX]={"units":{"USD":[fact(capex,tag=_CAPEX)]}}
    return doc


def review(doc, *, asof=AS_OF):
    return review_sec_annual_cashflow(
        json.dumps(doc).encode(),cik=SYNTHETIC_CIK,
        accession=SYNTHETIC_ACCESSION,period_end=_END,as_of=asof,
    )


class OfflineCashflowP28Tests(unittest.TestCase):
    def test_annual_operating_and_capex_equal_period_yields_nongaap_proxy(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as net:
            x=review(fixture())
        net.assert_not_called()
        self.assertEqual(x["status"],"reviewed_unverified")
        self.assertEqual(x["operating_cashflow_usd"],"200")
        self.assertEqual(x["capex_payments_usd"],"30")
        self.assertEqual(x["free_cashflow_proxy_usd"],"170")
        self.assertTrue(x["free_cashflow_proxy_is_non_gaap"])
        self.assertFalse(x["source_authenticated"])
        self.assertFalse(x["risk_authenticated"])
        self.assertFalse(x["guard_policy_modified"])

    def test_negative_operating_cashflow_negative_proxy_not_safe_score(self):
        x=review(fixture(cfo=-25,capex=30))
        self.assertEqual(x["free_cashflow_proxy_usd"],"-55")
        self.assertEqual(x["status"],"reviewed_unverified")
        self.assertFalse(x["financial_claim_authenticated"])

    def test_cfo_only_withholds_fcf_when_capex_missing(self):
        x=review(fixture(capex=None))
        self.assertEqual(x["operating_cashflow_usd"],"200")
        self.assertIsNone(x["free_cashflow_proxy_usd"])
        self.assertEqual(x["reason_code"],"CFO_ONLY_CAPEX_NOT_REPORTED")

    def test_missing_annual_cashflow_and_wrong_accession_not_invented(self):
        self.assertEqual(review(fixture(cfo=None,capex=30))["status"],"unavailable")
        x=fixture()
        x["facts"]["us-gaap"][_CFO]["units"]["USD"][0]["accn"]="0000000001-25-000099"
        self.assertEqual(review(x)["status"],"unavailable")

    def test_quarterly_in_annual_10k_is_not_mixed_into_annual_amount(self):
        x=fixture()
        x["facts"]["us-gaap"][_CFO]["units"]["USD"].insert(
            0,fact(90,start="2025-07-01"))
        self.assertEqual(review(x)["free_cashflow_proxy_usd"],"170")
        x["facts"]["us-gaap"][_CFO]["units"]["USD"].pop()
        self.assertEqual(review(x)["status"],"unavailable")

    def test_duplicate_annual_value_and_mixed_currency_fail_closed(self):
        x=fixture()
        x["facts"]["us-gaap"][_CFO]["units"]["USD"].append(fact(201))
        self.assertEqual(review(x)["reason_code"],"CASHFLOW_AMBIGUOUS_ANNUAL_FACT")
        x=fixture()
        x["facts"]["us-gaap"][_CAPEX]["units"]["EUR"]=[]
        self.assertEqual(review(x)["reason_code"],"CASHFLOW_FACT_MISSING_OR_MIXED_UNITS")

    def test_boolean_and_negative_capex_not_recognized(self):
        for val in (True,-1,10**18):
            with self.subTest(value=val):
                self.assertEqual(review(fixture(capex=val))["status"],"unavailable")

    def test_asof_future_filing_and_bad_issuer_fail_closed(self):
        x=fixture()
        x["facts"]["us-gaap"][_CFO]["units"]["USD"][0]["filed"]="2025-10-17"
        self.assertEqual(review(x)["reason_code"],"CASHFLOW_FILING_AFTER_AS_OF")
        x=fixture()
        x["cik"]=2
        self.assertEqual(review(x)["reason_code"],"CASHFLOW_ISSUER_MISMATCH")

    def test_mixed_fiscal_start_or_filing_date_withholds_proxy(self):
        x=fixture()
        x["facts"]["us-gaap"][_CAPEX]["units"]["USD"][0]["start"]="2024-09-30"
        v=review(x)
        self.assertEqual(v["status"],"reviewed_unverified")
        self.assertEqual(v["reason_code"],"CFO_CAPEX_PERIOD_OR_FILING_MISMATCH_NO_FCF")
        self.assertIsNone(v["free_cashflow_proxy_usd"])
        x=fixture()
        x["facts"]["us-gaap"][_CAPEX]["units"]["USD"][0]["filed"]="2025-10-16"
        self.assertIsNone(review(x)["free_cashflow_proxy_usd"])

    def test_guard_sqlite_replay_and_html_show_cash_without_trading(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p28-") as folder:
            db=Path(folder)/"audit.sqlite"
            inputs=fixture()
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_EXTERNAL")) as net:
                out=review_local_sec_with_guard(
                    submissions_json=synthetic_submissions(),
                    companyfacts_json=json.dumps(inputs).encode(),
                    original_filing=SYNTHETIC_HTML, cik=SYNTHETIC_CIK,
                    accession=SYNTHETIC_ACCESSION,as_of=AS_OF,
                    collected_at=COLLECTED_AT,current_end=_END,
                    prior_end="2024-09-30",needle=PHRASE,
                    audit_db_path=db,run_id="p28-cash-1",
                )
            net.assert_not_called()
            self.assertEqual(out["guard"]["decision"],"HOLD")
            self.assertEqual(out["cashflow"]["free_cashflow_proxy_usd"],"170")
            self.assertTrue(GuardAuditStore(db).verify_chain())
            html=render_local_sec_html(out).decode()
            self.assertIn("연간 영업현금흐름",html)
            self.assertIn("간이 FCF USD: 170",html)
            self.assertIn("비GAAP 참고치",html)
            self.assertFalse(out["limits"]["external_source_authenticated"])


if __name__=="__main__":
    unittest.main()
