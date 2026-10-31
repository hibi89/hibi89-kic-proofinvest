"""Deterministic corroboration of 28 manually inspected SEC web statement cells."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from proofinvest.sec_primary_web_replay import EVIDENCE, review_sec_apple_web_cells
from proofinvest.apple_audited_10k_replay import TEN_K
from proofinvest.public_primary_baseline import APPLE, CURATED, _read


class OfficialSecWebCellTests(unittest.TestCase):
    def setUp(self):
        self.source = _read(EVIDENCE)
        self.issuer = _read(TEN_K)
        self.manual = _read(APPLE)
        self.curated = _read(CURATED)

    def check(self, source=None):
        return review_sec_apple_web_cells(
            self.source if source is None else source,
            self.issuer, self.manual, self.curated,
        )

    def test_official_web_text_28_values_reconcile_and_engine_b_runs(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_LIVE_API")) as req:
            out = self.check()
        req.assert_not_called()
        self.assertEqual(out["verified_cell_count"], 28)
        self.assertEqual(out["revenue_growth_pct"], "6.43")
        self.assertEqual(out["receivables_growth_pct"], "19.06")
        self.assertEqual(out["receivables_minus_revenue_growth_pp"], "12.63")
        self.assertEqual(out["operating_cashflow_growth_pct"], "-5.73")
        self.assertEqual(out["free_cashflow_proxy_current_millions"], "98767")
        self.assertEqual(out["fcf_proxy_yoy_pct"], "-9.23")
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["original_sec_bytes_verified"])
        self.assertFalse(out["financial_misconduct_proven"])
        self.assertFalse(out["trade_executed"])

    def test_single_cell_change_and_unearned_original_verification_blocked(self):
        for field, year in (("sales", "current"),
                            ("operating_cashflow", "prior"),
                            ("liabilities", "current")):
            altered=deepcopy(self.source)
            altered[year][field]=str(int(altered[year][field])+1)
            with self.subTest(field=field, year=year), self.assertRaises(ValueError):
                self.check(altered)
        for key in ("source_authenticated", "sec_original_html_byte_sha256_verified",
                    "sec_api_companyfacts_original_verified",
                    "distribution_rights_verified"):
            altered=deepcopy(self.source); altered[key]=True
            with self.subTest(key=key), self.assertRaisesRegex(
                ValueError,"SEC_WEB_EVIDENCE_PROVENANCE"):
                self.check(altered)

    def test_bad_issuer_and_unsafe_origin_urls_blocked(self):
        for key,value in (
            ("official_url","https://example.com/masquerade"),
            ("accession","0000320193-25-000080"),
            ("unit","USD"),
            ("filing_date","2025-10-30")
        ):
            src=deepcopy(self.source);src[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.check(src)


if __name__=="__main__":
    unittest.main()
