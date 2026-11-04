"""P210 pivot: AMD Newsroom human-visible FY GAAP context + segment invariants."""
from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from proofinvest import amd_newsroom_fy2025_once as p


def section(name,rows):
    return "<h3>"+name+"</h3><table>"+"".join(
        "<tr><td>"+k+"</td>"+"".join("<td>"+v+"</td>" for v in vals)+"</tr>"
        for k,vals in rows)+"</table>"


def sample() -> bytes:
    annual=section(
        "Annual Financial Results",
        [
            ("GAAP / Non-GAAP 2025 2024",[]),
            ("Revenue ($M)",["$34,639","$25,785","Up 34%","$34,639","$25,785","Up 34%"]),
            ("Gross profit ($M)",["17,152","12,725","18,165","13,759"]),
            ("Operating income ($M)",["3,694","1,900","7,768","6,138"]),
            ("Operating margin %",["11%","7%","22%","24%"]),
            ("Net income ($M)",["4,335","1,641","6,831","5,420"]),
            ("Diluted earnings per share",["$2.65","$1.00","$4.17","$3.31"]),
        ],
    )
    seg=section(
        "SELECTED CORPORATE DATA | Segment and Disaggregated Revenue Information (1)",
        [
            ("Net Revenue: December 27, 2025, December 28, 2024",[]),
            ("Data Center Segment",["5,380","4,341","3,859","16,635","12,579"]),
            ("Client and Gaming Segment",[]),
            ("Total net revenue",["10,270","9,246","7,658","34,639","25,785"]),
        ],
    )
    return ("<html><body><h1>AMD Reports Fourth-Quarter and Full-Year 2025 Financial Results</h1>"
            "<p>Feb. 03, 2026</p><p>December 27, 2025 / December 28, 2024</p>"
            +annual+"<h3>Segment Summary</h3><p>2025 2024</p>"
            +seg+"<h3>Operating Income (Loss)</h3></body></html>").encode()


class Response(io.BytesIO):
    def __init__(self, raw, url=p._URL):
        super().__init__(raw)
        self.url=url;self.status=200
        self.headers={"Content-Type":"text/html","Content-Length":str(len(raw))}
    def geturl(self):
        return self.url


class P210NewsroomTests(unittest.TestCase):
    def test_sections_gaap_and_segment_separate_and_actual_annual_values(self):
        res=p.parse_amd_newsroom_2025(sample())
        self.assertEqual(res["gaap"]["revenue_2025"],"34639")
        self.assertEqual(res["gaap"]["revenue_2024"],"25785")
        self.assertEqual(res["gaap"]["net_income_2025"],"4335")
        self.assertEqual(res["gaap"]["operating_income_2025"],"3694")
        self.assertEqual(res["data_center"]["revenue_2025"],"16635")
        self.assertEqual(res["data_center"]["revenue_2024"],"12579")
        self.assertEqual(res["q4_2025_revenue_usdm"],"10270")
        self.assertFalse(res["same_period_and_business_mix_as_nvidia"])
        self.assertFalse(res["gaap_non_gaap_mixed"])
        self.assertFalse(res["quarter_annual_mixed"])

    def test_forged_dates_gaap_non_gaap_segment_and_identity_blocked(self):
        for raw in (
            sample().replace(b"Feb. 03, 2026",b"Feb. 03, 2025"),
            sample().replace(b"December 27, 2025",b"December 27, 2027"),
            sample().replace(b"Annual Financial Results",b"Quarterly Financial Results"),
            sample().replace(b"4,335",b"6,831",1),
            sample().replace(b"34,639",b"34,638",1),
            sample().replace(b"16,635",b"16,634"),
            sample().replace(b"Net Revenue:",b"Quarterly net revenue:"),
        ):
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError):
                    p.parse_amd_newsroom_2025(raw)

    def test_one_get_mocked_fails_closed_without_paid_api_or_rights(self):
        observed=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NET")):
            r=p.fetch_amd_newsroom_once(opener=lambda req:(observed.append(req),Response(sample()))[1])
        self.assertTrue(r["actual_publisher_html_verified"])
        self.assertEqual(r["network_get_attempted"],1)
        self.assertEqual(len(observed),1)
        self.assertEqual(r["guard_preview"],"HOLD")
        for name in ("sec_original_byte_identity","commercial_ai_rights_verified",
                     "peer_market_license_verified","fiscal_windows_identical",
                     "engine_c_final_peer_verdict_available","full_abc_ready",
                     "trade_executed","original_bytes_persisted","raw_uploaded"):
            self.assertFalse(r[name])

    def test_wrong_origin_and_content_rejected(self):
        out=p.fetch_amd_newsroom_once(opener=lambda req:Response(sample(),url="https://fake.invalid/"))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(out["reason_code"],"AMD_NEWSROOM_HOST_OR_STATUS_CHANGED")
        bad=Response(sample());bad.headers["Content-Type"]="application/pdf"
        r=p.fetch_amd_newsroom_once(opener=lambda req:bad)
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["reason_code"],"AMD_NEWSROOM_MIME_INVALID")


if __name__=="__main__":
    unittest.main()
