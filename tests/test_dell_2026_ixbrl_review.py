"""P199 real source XBRL review and native Streamlit UI fail-closed checks."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch
from proofinvest import dell_2026_ixbrl_review as p

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class RealIssuerXBRLReviewTests(unittest.TestCase):
    def test_real_raw_p195_matches_p198_context_and_revenue(self):
        r=p.review_observed_real_dell_ixbrl(as_of="2026-11-05",
                                             receipt=p.observed_ixbrl_receipt())
        self.assertEqual(r["status"], "PUBLISHER_IXBRL_REAL_ANNUAL_REVENUE_CONFIRMED_LIMITED")
        self.assertTrue(r["publisher_xbrl_fact_correctly_replayed"])
        e=r["evidence"]
        self.assertEqual(e["xbrl_concept"], "us-gaap:revenues")
        self.assertEqual(e["xbrl_facts"]["FY2026"]["context"], "c-1")
        self.assertEqual(e["xbrl_facts"]["FY2025"]["context"], "c-14")
        self.assertEqual(e["annual_revenue_growth_pct"], "18.80")
        for key in ("sec_edgar_original_authenticated",
                    "source_commercial_rights_verified", "price_true_ndx_available",
                    "sector_peer_period_aligned", "model_grounded_issuer_numeric_accurate",
                    "full_abc_ready", "trade_executed"):
            self.assertFalse(r[key])
        self.assertEqual(r["guard_policy_preview"], "HOLD")

    def test_modified_proof_or_asof_fails_closed(self):
        for field, value in (
            ("source_sha256", "0"*64),
            ("source_bytes", 3610308),
            ("xbrl_concept", "us-gaap:netincome"),
            ("origin_sec_edgar_byte_identical", True),
            ("source_rights_verified", True),
        ):
            receipt=p.observed_ixbrl_receipt()
            receipt[field]=value
            with self.subTest(field=field):
                self.assertEqual(p.review_observed_real_dell_ixbrl(
                    as_of="2026-11-05", receipt=receipt)["status"], "BLOCKED")
        for d in ("2026-11-04", "2026-11-06", None):
            self.assertEqual(p.review_observed_real_dell_ixbrl(
                as_of=d, receipt=p.observed_ixbrl_receipt())["status"], "BLOCKED")

    def test_app_displays_real_xbrl_issuer_context_rows(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception, [str(e.message) for e in at.exception])
        self.assertTrue(any("Inline XBRL" in s.value for s in at.subheader))
        self.assertTrue(any("us-gaap:revenues" in s.value for s in at.caption))
        self.assertFalse(at.error)

    def test_app_blocks_untrusted_xbrl_and_never_displays_tag(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p, "review_observed_real_dell_ixbrl",
                          return_value={"status":"BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertTrue(any("XBRL 회계기간" in e.value for e in at.error))
        self.assertFalse(any("Inline XBRL" in s.value for s in at.subheader))


if __name__ == "__main__":
    unittest.main()
