"""P194 real first-party reference FY2026 figures; fail-closed time/mix/rights."""
from __future__ import annotations

import unittest
from proofinvest.apple_public_peer_reality import (
    public_primary_revenue_values as values,
    review_public_fiscal_peers as review,
)


class RealPublicReferenceRevenueTests(unittest.TestCase):
    def check(self, **changes):
        args = dict(as_of="2026-11-05", revenue_values=values())
        args.update(changes)
        return review(**args)

    def test_three_real_primary_reported_revenues_with_correct_growth(self):
        x = self.check()
        self.assertEqual(x["status"],
                         "INDICATIVE_REAL_PRIMARY_PUBLIC_YOY_FISCAL_REVENUE_ONLY")
        self.assertEqual(x["reference_count"], 3)
        rows = {row["ticker"]: row for row in x["issuer_rows"]}
        self.assertEqual(set(rows), {"AAPL", "MSFT", "DELL"})
        self.assertEqual(rows["AAPL"]["fy2026_revenue_usd_millions"], "478834")
        self.assertEqual(rows["MSFT"]["fy2026_revenue_usd_millions"], "331839")
        self.assertEqual(rows["DELL"]["fy2026_revenue_usd_millions"], "113538")
        self.assertEqual(rows["AAPL"]["yoy_revenue_growth_pct"], "15.06")
        self.assertEqual(rows["MSFT"]["yoy_revenue_growth_pct"], "17.79")
        self.assertEqual(rows["DELL"]["yoy_revenue_growth_pct"], "18.80")
        self.assertEqual(rows["MSFT"]["fy2026_end"], "2026-06-30")
        self.assertEqual(rows["DELL"]["fy2026_end"], "2026-01-30")
        self.assertTrue(x["fiscal_cutoffs_differ"])
        self.assertTrue(x["business_models_differ"])
        self.assertEqual(x["sector_rank_or_growth_conclusion"],
                         "UNAVAILABLE_UNALIGNED_PERIODS_AND_MIX")
        for forbidden in (
            "source_bytes_authenticated", "provider_peer_license_verified",
            "same_sector_comparability_verified", "aligned_fiscal_periods_verified",
            "full_engine_c_peer_inference_ready", "market_ndx_stock_ready",
            "ai_agent_executed", "trade_executed",
        ):
            self.assertIs(x[forbidden], False, forbidden)
        self.assertEqual(x["external_network_requests"], 0)
        self.assertEqual(x["guard_policy_preview"], "HOLD")

    def test_altered_extra_or_missing_public_revenue_blocks(self):
        for ticker in ("AAPL", "MSFT", "DELL"):
            data = values()
            data[ticker]["2026"] = str(int(data[ticker]["2026"]) + 1)
            with self.subTest(ticker=ticker):
                self.assertEqual(self.check(revenue_values=data)["status"], "BLOCKED")
        for data in (
            {},
            values() | {"GOOG": {"2025": "1", "2026": "2"}},
            {k: v for k, v in values().items() if k != "MSFT"},
            values() | {"DELL": {"2026": "113538"}},
            values() | {"MSFT": {"2025": "281724", "2026": 331839}},
            values() | {"AAPL": {"2025": "416161", "2026": "-478834"}},
        ):
            with self.subTest(data=str(data)[:80]):
                self.assertEqual(self.check(revenue_values=data)["status"], "BLOCKED")

    def test_as_of_catalog_vintage_is_strict_and_no_future_leakage(self):
        for as_of in ("2026-11-03", "2026-11-04", "2026-11-06",
                      "2026-02-30", "2026-11-5", "2027-11-05", None):
            with self.subTest(as_of=as_of):
                self.assertEqual(self.check(as_of=as_of)["status"], "BLOCKED")

    def test_caller_mutation_does_not_change_first_party_catalog(self):
        changed = values()
        changed["DELL"]["2026"] = "123"
        self.assertEqual(values()["DELL"]["2026"], "113538")
        self.assertEqual(self.check()["reference_count"], 3)


if __name__ == "__main__":
    unittest.main()
