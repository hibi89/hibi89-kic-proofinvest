"""P29: never mix supplemental CompanyFacts from a different filing date."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html

END = "2025-09-30"
BASE_FILED = "2025-10-15"
OTHER_FILED = "2025-10-16"
CFO = "NetCashProvidedByUsedInOperatingActivities"
CAPEX = "PaymentsToAcquirePropertyPlantAndEquipment"


def annual(value, filed):
    return {
        "accn": SYNTHETIC_ACCESSION, "form": "10-K",
        "start": "2024-10-01", "end": END,
        "filed": filed, "val": value,
    }


def instant(value, filed, *, end=END):
    return {
        "accn": SYNTHETIC_ACCESSION, "form": "10-K",
        "end": end, "filed": filed, "val": value,
    }


def three_panels(*, balance=BASE_FILED, shares=BASE_FILED, cash=BASE_FILED):
    doc = synthetic_companyfacts()
    gaap = doc["facts"]["us-gaap"]
    for tag, value in (("Assets", 300), ("Liabilities", 100),
                       ("StockholdersEquity", 200)):
        gaap[tag] = {"units": {"USD": [instant(value, balance)]}}
    gaap["CommonStockSharesOutstanding"] = {
        "units": {"shares": [instant(1000, shares)]},
    }
    gaap[CFO] = {"units": {"USD": [annual(250, cash)]}}
    gaap[CAPEX] = {"units": {"USD": [annual(50, cash)]}}
    return json.dumps(doc, separators=(",", ":")).encode()


def run(companyfacts, audit_db, *, intent=None):
    return review_local_sec_with_guard(
        submissions_json=synthetic_submissions(),
        companyfacts_json=companyfacts,
        original_filing=SYNTHETIC_HTML,
        cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        as_of=AS_OF, collected_at=COLLECTED_AT,
        current_end=END, prior_end="2024-09-30", needle=PHRASE,
        audit_db_path=audit_db, run_id="p29-coherence-1",
        required_review_intent=intent,
    )


class FilingDateCoherenceP29Tests(unittest.TestCase):
    def test_all_three_matching_panels_survive_guard_and_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("urllib.request.build_opener", side_effect=AssertionError("NO_HTTP")) as net:
                x = run(three_panels(), Path(tmp) / "audit.sqlite")
            net.assert_not_called()
            self.assertEqual(x["guard"]["decision"], "HOLD")
            self.assertEqual(x["balance_sheet"]["status"], "reviewed_unverified")
            self.assertEqual(x["share_capital"]["status"], "reviewed_unverified")
            self.assertEqual(x["cashflow"]["free_cashflow_proxy_usd"], "200")
            self.assertTrue(GuardAuditStore(Path(tmp) / "audit.sqlite").verify_chain())
            self.assertIn("간이 FCF USD: 200", render_local_sec_html(x).decode())

    def test_three_different_dates_are_withheld_without_destroying_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.sqlite"
            x = run(three_panels(balance=OTHER_FILED, shares=OTHER_FILED,
                                 cash=OTHER_FILED), path)
            self.assertEqual(x["verification"]["filing_date"], BASE_FILED)
            self.assertEqual(x["guard"]["decision"], "HOLD")
            self.assertTrue(GuardAuditStore(path).verify_chain())
            for key in ("balance_sheet", "share_capital", "cashflow"):
                with self.subTest(card=key):
                    self.assertEqual(x[key]["status"], "unavailable")
                    self.assertEqual(x[key]["reason_code"],
                                     "AUXILIARY_10K_FILING_DATE_MISMATCH")
                    self.assertIsNone(x[key]["filing_date"])
            self.assertIsNone(x["balance_sheet"]["inputs_usd"])
            self.assertIsNone(x["balance_sheet"]["liabilities_to_equity_pct"])
            self.assertIsNone(x["share_capital"]["shares_outstanding"])
            self.assertIsNone(x["share_capital"]["shares_change_pct"])
            self.assertIsNone(x["cashflow"]["operating_cashflow_usd"])
            self.assertIsNone(x["cashflow"]["free_cashflow_proxy_usd"])
            self.assertEqual(x["cashflow"]["free_cashflow_proxy_status"], "unavailable")
            html = render_local_sec_html(x).decode()
            self.assertIn("간이 FCF USD: NOT_AVAILABLE", html)
            self.assertNotIn("간이 FCF USD: 200", html)

    def test_mismatched_cash_does_not_suppress_matching_balance_or_shares(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = run(three_panels(cash=OTHER_FILED), Path(tmp) / "audit.sqlite")
            self.assertEqual(x["cashflow"]["status"], "unavailable")
            self.assertEqual(x["balance_sheet"]["status"], "reviewed_unverified")
            self.assertEqual(x["share_capital"]["shares_outstanding"], "1000")

    def test_mismatched_balance_does_not_suppress_other_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = run(three_panels(balance=OTHER_FILED), Path(tmp) / "audit.sqlite")
            self.assertEqual(x["balance_sheet"]["status"], "unavailable")
            self.assertEqual(x["cashflow"]["free_cashflow_proxy_usd"], "200")
            self.assertEqual(x["share_capital"]["status"], "reviewed_unverified")

    def test_mismatched_shares_does_not_suppress_other_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            x = run(three_panels(shares=OTHER_FILED), Path(tmp) / "audit.sqlite")
            self.assertEqual(x["share_capital"]["status"], "unavailable")
            self.assertEqual(x["share_capital"]["shares_change_status"], "unavailable")
            self.assertEqual(x["balance_sheet"]["status"], "reviewed_unverified")
            self.assertEqual(x["cashflow"]["free_cashflow_proxy_usd"], "200")

    def test_required_risk_review_cannot_use_wrong_filing_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "audit.sqlite"
            with self.assertRaisesRegex(ValueError, "RISK_REVIEW_RECONCILED_BALANCE_REQUIRED"):
                run(three_panels(balance=OTHER_FILED), dest, intent="RISK_CHECK")
            self.assertFalse(dest.exists())

    def test_core_submissions_and_revenue_disagreement_blocks_before_audit(self):
        from proofinvest import local_sec_guard_report as mod
        original_build = mod.build_local_sec_review_packet

        def tampered(*args, **kwargs):
            packet = original_build(*args, **kwargs)
            packet["issuer"]["filing_date"] = OTHER_FILED
            return packet

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "audit.sqlite"
            with patch.object(mod, "build_local_sec_review_packet", side_effect=tampered):
                with self.assertRaisesRegex(ValueError, "CORE_10K_FILING_DATE_MISMATCH"):
                    run(three_panels(), dest)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
