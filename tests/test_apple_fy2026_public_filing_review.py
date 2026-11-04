"""P190 actual public financial text arithmetic, rights and guard regression."""
import json
import unittest
from unittest.mock import patch
from proofinvest.apple_fy2026_public_filing_review import (
    public_2026_values, review_apple_2026_public_financials as review,
)


class ApplePublicFinancialTests(unittest.TestCase):
    def call(self, **overrides):
        args = dict(ticker="AAPL", accession="0000320193-26-000026",
                    as_of="2026-11-05", values=public_2026_values())
        args.update(overrides)
        return review(**args)

    def test_official_public_statement_arithmetic(self):
        r = self.call()
        self.assertEqual(r["status"], "PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED")
        m = r["derived_metrics"]
        self.assertEqual(m["revenue_growth_pct"], "15.06")
        self.assertEqual(m["net_income_growth_pct"], "18.00")
        self.assertEqual(m["operating_cash_flow_to_net_income_2026"], "1.0978")
        self.assertEqual(m["free_cash_flow_2026_usd_millions_unverified"], "136056")
        self.assertEqual(m["free_cash_flow_2025_usd_millions_unverified"], "98767")
        self.assertEqual(m["inventory_growth_pct"], "154.30")
        self.assertEqual(r["fiscal_period_ends"]["2026"], "2026-09-26")
        self.assertIn("INVENTORY_GROWTH_OUTPACED_REVENUE_HUMAN_REVIEW", r["signals"])
        self.assertEqual(r["guard_policy_preview"], "HOLD")
        for flag in ("source_rights_verified", "publisher_origin_authenticated",
                     "original_bytes_authenticated", "fraud_proven", "trade_executed"):
            self.assertFalse(r[flag])

    def test_tampered_values_rejected(self):
        for metric, value in (("net_sales", "478835"), ("inventory", "0"),
                              ("net_income", "132175.0"),
                              ("operating_cash_flow", 145097),
                              ("capital_expenditure", "1e4")):
            data = public_2026_values()
            data[metric]["2026"] = value
            with self.subTest(metric=metric):
                r = self.call(values=data)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertIsNone(r["derived_metrics"])

    def test_wrong_ticker_accession_time_or_future_source(self):
        for change in ({"ticker": "NVDA"}, {"ticker": "aapl"},
                       {"accession": "0000320193-25-000079"},
                       {"as_of": "2026-11-03"}, {"as_of": "2026-11-06"},
                       {"as_of": "2026-02-30"}, {"as_of": None}):
            with self.subTest(change=change):
                r = self.call(**change)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertFalse(r["trade_executed"])

    def test_missing_extra_or_nonstring_numeric(self):
        original = public_2026_values()
        for data in (None, {}, {k:v for k,v in original.items() if k != "inventory"},
                     original | {"untrusted": {"2026":"1","2025":"1"}},
                     original | {"net_sales": {"2026":"478834"}},
                     original | {"net_sales": {"2026":"478834","2025":"416161","2024":"391035"}},
                     original | {"inventory": {"2026":"14541","2025":5718.0}}):
            with self.subTest(case=str(data)[:50]):
                self.assertEqual(self.call(values=data)["status"], "BLOCKED")

    def test_copy_integrity_and_zero_network(self):
        copy = public_2026_values()
        copy["net_sales"]["2026"] = "0"
        self.assertEqual(public_2026_values()["net_sales"]["2026"], "478834")
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO HTTP")) as get:
            r = self.call()
        get.assert_not_called()
        self.assertEqual(r["external_network_requests"], 0)
        self.assertFalse(r["raw_original_downloaded"])
        self.assertFalse(r["ai_agent_executed"])
        self.assertFalse(r["market_ndx_peer_ready"])
        self.assertNotIn("licensed_data_receipt", json.dumps(r))


if __name__ == "__main__":
    unittest.main()
