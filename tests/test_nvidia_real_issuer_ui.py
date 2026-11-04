"""P209 actual second issuer NVDA source receipt and independent UI evidence gates."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch
from proofinvest import nvidia_real_issuer_review as p

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"


class P209ActualNvidiaUiTests(unittest.TestCase):
    def test_real_ci_original_receipt_recomputes_non_gaap_independent_gaap_metrics(self):
        r=p.review_nvidia_actual_release(
            as_of="2026-11-05", receipt=p.actual_nvidia_issuer_receipt())
        self.assertEqual(r["status"],"REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED")
        self.assertTrue(r["issuer_original_publisher_seen"])
        m=r["evidence"]["metrics"]
        self.assertEqual(m["revenue_growth_pct"],"65.47")
        self.assertEqual(m["inventory_growth_pct"],"112.33")
        self.assertEqual(m["inventory_growth_minus_revenue_pp"],"46.86")
        self.assertEqual(m["ar_growth_minus_revenue_pp"],"1.30")
        self.assertEqual(m["cfo_to_net_income_2026"],"0.8555")
        for key in ("sec_original_identical","commercial_ai_rights_verified",
                    "licensed_stock_ndx_peer_available","full_abc_ready",
                    "ai_agent_executed","trade_executed"):
            self.assertFalse(r[key])
        self.assertEqual(r["guard_policy_preview"],"HOLD")
        self.assertEqual(r["network_requests"],0)

    def test_source_receipt_and_period_forgery_fail_closed(self):
        for field,bad in (("source_sha256","0"*64),
                          ("source_bytes",1),("ticker","AAPL"),
                          ("commercial_ai_rights_verified",True),
                          ("fiscal_2026_end","2027-01-25")):
            receipt=p.actual_nvidia_issuer_receipt()
            receipt[field]=bad
            with self.subTest(field=field):
                r=p.review_nvidia_actual_release(as_of="2026-11-05",receipt=receipt)
                self.assertEqual(r["status"],"BLOCKED")
                self.assertIsNone(r["evidence"])
        self.assertEqual(p.review_nvidia_actual_release(
            as_of="2026-11-06",receipt=p.actual_nvidia_issuer_receipt())["status"],"BLOCKED")

    def test_actual_nvidia_source_select_and_only_first_party_real_fy_panel(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        self.assertFalse(at.exception,[str(x.message) for x in at.exception])
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception,[str(x.message) for x in at.exception])
        self.assertTrue(any("NVIDIA 실제 발행사" in x.value for x in at.success))
        self.assertTrue(any("NVIDIA 발행사 재무제표" in x.value for x in at.subheader))
        self.assertTrue(any("미감사" in x.value and "HOLD" in x.value for x in at.warning))
        self.assertFalse(at.error)

    def test_forged_nvidia_receipt_blocks_all_success_and_numeric_metrics(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p,"review_nvidia_actual_release",return_value={"status":"BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception)
        self.assertFalse(at.success)
        self.assertFalse(at.metric)
        self.assertTrue(any("원문 검증 증거" in x.value for x in at.error))


if __name__=="__main__":
    unittest.main()
