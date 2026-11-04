"""Real P207 working capital reviewed-source and local Streamlit display checks."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import unittest
from proofinvest import dell_working_capital_review as p

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class ActualWorkingCapitalReviewTests(unittest.TestCase):
    def test_actual_p207_external_ci_receipt_replays_decimal_divergence(self):
        r = p.review_real_working_capital(
            reviewed_as_of="2026-11-05", receipt=p.actual_working_capital_receipt()
        )
        self.assertEqual(r["status"], "P207_ACTUAL_ISSUER_WORKING_CAPITAL_REVIEW_LIMITED")
        self.assertTrue(r["real_issuer_working_capital_source_seen"])
        x = r["evidence"]
        self.assertEqual(x["revenue_growth_pct"],"18.80")
        self.assertEqual(x["asset_rows"]["trade_receivables"]["growth_pct"],"70.76")
        self.assertEqual(x["asset_rows"]["inventories"]["growth_minus_revenue_pp"],"36.60")
        for flag in ("sec_original_identical", "rights_verified",
                     "licensed_market_peer_available", "ai_grounded_real_financials",
                     "full_engine_b_complete", "full_abc_ready", "trade_executed"):
            self.assertFalse(r[flag])
        self.assertEqual(r["guard_policy_preview"],"HOLD")
        self.assertEqual(r["network_requests"],0)

    def test_forged_observation_and_future_asof_do_not_display_data(self):
        for k,v in (("source_sha256","a"*64),("source_bytes",1),
                    ("rights_verified",True),("annual_revenue_usd_millions",("1","1")),
                    ("p206_prior_byte_identical",True)):
            receipt=p.actual_working_capital_receipt()
            receipt[k]=v
            with self.subTest(field=k):
                r=p.review_real_working_capital(reviewed_as_of="2026-11-05",receipt=receipt)
                self.assertEqual(r["status"],"BLOCKED")
                self.assertIsNone(r["evidence"])
        self.assertEqual(p.review_real_working_capital(
            reviewed_as_of="2026-11-06",
            receipt=p.actual_working_capital_receipt())["status"],"BLOCKED")

    def test_native_streamlit_actual_asset_divergence_panel(self):
        from streamlit.testing.v1 import AppTest
        a=AppTest.from_file(str(_APP)).run(timeout=25)
        a.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(a.exception,[str(x.message) for x in a.exception])
        self.assertTrue(any("실제 매출채권·재고" in x.value for x in a.subheader))
        self.assertTrue(any("미감사" in x.value and "투자" in x.value
                            for x in a.warning))
        self.assertFalse(a.error)

    def test_forged_new_asset_gate_only_hides_new_panel_not_old_evidence(self):
        from streamlit.testing.v1 import AppTest
        a=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p,"review_real_working_capital",return_value={"status":"BLOCKED"}):
            a.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(a.exception)
        self.assertFalse(any("실제 매출채권·재고" in x.value for x in a.subheader))
        self.assertTrue(any("SEC 제출 색인" in x.value for x in a.subheader))
        self.assertTrue(any("매출채권·재고" in x.value for x in a.warning))


if __name__=="__main__":
    unittest.main()
