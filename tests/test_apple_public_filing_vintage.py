"""P187 first-party listing metadata cannot be promoted to source authenticity."""
import unittest
from proofinvest.apple_public_filing_vintage import (
    check_apple_public_filing_vintage as check,
)


class ApplePublicFilingVintageTests(unittest.TestCase):
    def call(self, *, as_of="2026-11-05",
             accession="0000320193-26-000026",
             fiscal_period_end="2026-09-26", ticker="AAPL"):
        return check(ticker=ticker, as_of=as_of,
                     accession=accession, fiscal_period_end=fiscal_period_end)

    def test_new_actual_2026_filing_metadata_by_nov_5_never_authenticates_bytes(self):
        result = self.call()
        self.assertEqual(result["status"],
                         "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED")
        self.assertEqual(result["filing_date"], "2026-11-03")
        self.assertEqual(result["cik"], "0000320193")
        self.assertEqual(result["date_only_as_of"], "2026-11-05")
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["fiscal_filing_original_bytes_verified"])
        self.assertFalse(result["data_downloaded"])
        self.assertEqual(result["external_network_requests"], 0)

    def test_2025_is_historical_after_2026_filing_became_available(self):
        self.assertEqual(self.call(
            accession="0000320193-25-000079",
            fiscal_period_end="2025-09-27")["status"], "BLOCKED")
        result = self.call(
            as_of="2026-11-03", accession="0000320193-25-000079",
            fiscal_period_end="2025-09-27")
        self.assertEqual(result["status"],
                         "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED")
        self.assertEqual(result["date_only_availability_rule"],
                         "AVAILABLE_ONLY_DAY_AFTER_FILING")
        self.assertEqual(self.call(
            as_of="2026-11-03")["status"], "BLOCKED")

    def test_future_hindsight_and_unknown_listing_are_fail_closed(self):
        for kwargs in (
            {"as_of": "2026-11-06"},
            {"as_of": "2025-10-31"},
            {"as_of": "2026-11-04", "accession": "0000320193-25-000079",
             "fiscal_period_end": "2025-09-27"},
            {"ticker": "NVDA"},
            {"ticker": "aapl"},
            {"accession": "https://sec.gov/../"},
            {"fiscal_period_end": "2025-09-27"},
            {"as_of": "not-a-date"},
            {"as_of": "2026-02-29"},
            {"as_of": None},
        ):
            with self.subTest(kwargs=kwargs):
                r = self.call(**kwargs)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertFalse(r["source_authenticated"])
                self.assertFalse(r["trade_executed"])

    def test_historical_2025_filing_allowed_only_after_filing_date(self):
        r = self.call(as_of="2026-02-01",
                      accession="0000320193-25-000079",
                      fiscal_period_end="2025-09-27")
        self.assertEqual(r["status"],
                         "PUBLIC_FILING_VINTAGE_METADATA_MATCHED_ORIGINAL_UNVERIFIED")
        self.assertFalse(r["fiscal_filing_original_bytes_verified"])


if __name__ == "__main__":
    unittest.main()
