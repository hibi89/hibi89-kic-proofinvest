"""P210 bounded same-industry *public text*, not falsely authenticated AMD raw."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import unittest

from proofinvest import amd_nvidia_public_reference as p
from proofinvest import nvidia_real_issuer_review as nv

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"


class P210PublicSemiconductorReferenceTests(unittest.TestCase):
    def compare(self, **kwargs):
        return p.compare_nvda_amd_public_annual_reference(
            reviewed_as_of="2026-11-05",
            amd_receipt=p.actual_amd_public_newsroom_receipt(),
            nvidia_receipt=nv.actual_nvidia_issuer_receipt(), **kwargs,
        )

    def test_new_actual_raw_vs_public_text_different_fiscal_end_growth(self):
        x=self.compare()
        self.assertEqual(x["status"],"HUMAN_REFERENCE_NVDA_AMD_GAAP_GROWTH_DIFFERENT_PERIODS")
        self.assertTrue(x["actual_nvda_issuer_raw_verified"])
        self.assertTrue(x["amd_web_text_reference_validated"])
        r=x["evidence"]
        self.assertEqual(r["current_fiscal_end_gap_days"],29)
        self.assertEqual(r["prior_fiscal_end_gap_days"],29)
        self.assertEqual([e["annual_gaap_revenue_growth_pct"] for e in r["issuer_rows"]],
                         ["65.47","34.34"])
        self.assertEqual(r["amd_data_center_revenue_latest_usdm"],"16635")
        self.assertEqual(r["amd_data_center_growth_pct"],"32.24")
        self.assertEqual(r["revenue_growth_difference_pp_observed_not_sector_rank"],"31.14")
        self.assertTrue(r["fiscal_periods_differ"])
        self.assertEqual(r["peer_conclusion"],"WITHHELD_DIFFERENT_PERIOD_ENDS_AND_SEGMENT_MIX")
        self.assertIsNone(r["issuer_rows"][1]["original_sha256"])
        self.assertEqual(len(r["issuer_rows"][0]["original_sha256"]),64)
        for key in ("amd_original_raw_bytes_verified","originals_sec_byte_identical",
                    "source_commercial_ai_rights_verified","licensed_representative_same_sector_peer",
                    "cross_issuer_accounting_policy_compatible","fiscal_windows_identical",
                    "price_ndx_available","engine_c_completed","full_abc_ready",
                    "ai_agent_executed","trade_executed"):
            self.assertFalse(x[key],key)
        self.assertEqual(x["guard_policy_preview"],"HOLD")
        self.assertEqual(x["network_requests"],0)

    def test_forged_amd_numbers_metadata_rights_and_nvidia_raw_hash_blocked(self):
        for k,v in (
            ("official_public_page","https://example.org/forgery"),
            ("fiscal_latest_end","2026-01-25"),
            ("published","2025-01-01"),
            ("commercial_ai_rights_verified",True),
            ("publisher_original_bytes_verified",True),
            ("facts",{**p.actual_amd_public_newsroom_receipt()["facts"],
                      "revenue_2025":"6831"}),
        ):
            receipt=p.actual_amd_public_newsroom_receipt()
            receipt[k]=v
            with self.subTest(k=k):
                x=p.compare_nvda_amd_public_annual_reference(
                    reviewed_as_of="2026-11-05",amd_receipt=receipt,
                    nvidia_receipt=nv.actual_nvidia_issuer_receipt())
                self.assertEqual(x["status"],"BLOCKED")
                self.assertIsNone(x["evidence"])
        bad_nvidia=nv.actual_nvidia_issuer_receipt()
        bad_nvidia["source_sha256"]="0"*64
        x=p.compare_nvda_amd_public_annual_reference(
            reviewed_as_of="2026-11-05",
            amd_receipt=p.actual_amd_public_newsroom_receipt(),
            nvidia_receipt=bad_nvidia)
        self.assertEqual(x["status"],"BLOCKED")
        self.assertIsNone(x["evidence"])

    def test_review_vintage_and_unverified_peer_rights_cannot_be_promoted(self):
        x=p.compare_nvda_amd_public_annual_reference(
            reviewed_as_of="2026-11-06",
            amd_receipt=p.actual_amd_public_newsroom_receipt(),
            nvidia_receipt=nv.actual_nvidia_issuer_receipt())
        self.assertEqual(x["status"],"BLOCKED")
        self.assertFalse(x["licensed_representative_same_sector_peer"])

    def test_user_sees_per_company_source_class_and_29_day_warning(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception,[str(x.message) for x in at.exception])
        self.assertTrue(any("AMD·NVIDIA 공식 공개 GAAP" in x.value for x in at.subheader))
        self.assertTrue(any("29일" in x.value and "Guard HOLD" in x.value
                            for x in at.warning))
        self.assertFalse(at.error)

    def test_tampered_peer_hides_only_peer_not_verified_nvidia_panel(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(p,"compare_nvda_amd_public_annual_reference",
                          return_value={"status":"BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception)
        self.assertTrue(any("NVIDIA 실제 발행사" in x.value for x in at.success))
        self.assertFalse(any("AMD·NVIDIA 공식 공개 GAAP" in x.value for x in at.subheader))
        self.assertTrue(any("비교 수치를 표시하지 않습니다" in x.value for x in at.warning))


if __name__ == "__main__":
    unittest.main()
