"""P210 AMD issuer annual GAAP+Data Center vs nonGAAP and Q4 adversarial checks."""
from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from proofinvest import amd_fy2025_issuer_once as p


def row(label, values):
    return "<tr><td>"+label+"</td>"+ "".join("<td>"+v+"</td>" for v in values)+"</tr>"


def sample() -> bytes:
    gaap = (
        "<table><tr><th>Annual Financial Results</th><th>GAAP 2025</th>"
        "<th>2024</th><th>Non-GAAP 2025</th><th>2024</th></tr>"
        +row("Revenue ($M)",["$","34,639","25,785","Up 34%","34,639","25,785","Up 34%"])
        +row("Operating income ($M)",["3,694","1,900","Up 94%","7,768","6,138","Up 27%"])
        +row("Net income ($M)",["4,335","1,641","Up 164%","6,831","5,420","Up 26%"])
        +"</table>"
    )
    segment = (
        "<table><tr><th>Net Revenue:</th><th>Three Months Ended</th>"
        "<th>Year Ended December 27, 2025 and December 28, 2024</th></tr>"
        +row("Data Center Segment",["5,380","4,341","3,859","16,635","12,579"])
        +row("Total net revenue",["10,270","9,246","7,658","34,639","25,785"])
        +"</table>"
    )
    return ("<html><body><h1>AMD Reports Fourth Quarter and Full Year 2025 Results</h1>"
            "<p>Feb. 03, 2026; Fiscal Year December 27, 2025 and December 28, 2024</p>"
            +gaap+segment+"</body></html>").encode()


class Reply(io.BytesIO):
    def __init__(self, data, url=p._URL):
        super().__init__(data)
        self.status=200;self.url=url
        self.headers={"Content-Type":"text/html","Content-Length":str(len(data))}
    def geturl(self):return self.url


class P210AmdOneShotTests(unittest.TestCase):
    def test_true_annual_gaap_separate_from_non_gaap_and_quarter(self):
        f=p.parse_amd_issuer_2025(sample())
        self.assertEqual(f["annual_gaap"]["revenue_current"],"34639")
        self.assertEqual(f["annual_gaap"]["revenue_prior"],"25785")
        self.assertEqual(f["annual_gaap"]["net_income_current"],"4335")
        self.assertEqual(f["annual_gaap"]["operating_income_current"],"3694")
        self.assertEqual(f["data_center"]["revenue_current"],"16635")
        self.assertEqual(f["data_center"]["revenue_prior"],"12579")
        self.assertFalse(f["gaap_non_gaap_conflated"])
        self.assertFalse(f["quarter_annual_conflated"])
        self.assertFalse(f["peer_same_fiscal_end_as_nvda"])

    def test_values_anchor_periods_and_duplicates_fail_closed(self):
        for f in (
            sample().replace(b"34,639",b"34,638",1),
            sample().replace(b"4,335",b"6,831"),
            sample().replace(b"16,635",b"16,634"),
            sample().replace(b"December 27, 2025",b"December 27, 2026"),
            sample().replace(b"Annual Financial Results",b"Quarterly Financial Results"),
            sample()+sample(),
            sample().replace(b"Data Center Segment",b"Cloud Services Revenue"),
        ):
            with self.subTest(bytes=len(f)):
                with self.assertRaises(ValueError):
                    p.parse_amd_issuer_2025(f)

    def test_one_get_readonly_and_no_licensing_promotion(self):
        req=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NETWORK")):
            result=p.fetch_amd_official_2025_once(
                open_once=lambda r:(req.append(r),Reply(sample()))[1])
        self.assertEqual(len(req),1)
        self.assertTrue(result["actual_issuer_original_observed"])
        self.assertEqual(result["get_attempted"],1)
        self.assertEqual(result["get_budget"],1)
        self.assertEqual(result["guard_preview"],"HOLD")
        for field in ("sec_10k_original_byte_authenticated", "commercial_ai_rights_verified",
                      "licensed_real_peer_feed", "true_ndx_data_licensed",
                      "same_fiscal_cohort_verified","full_engine_c_ready",
                      "trade_executed","source_raw_saved","original_uploaded"):
            self.assertFalse(result[field])

    def test_forged_url_and_content_type_not_permitted(self):
        v=p.fetch_amd_official_2025_once(open_once=lambda req:Reply(sample(),url="https://example.org/"))
        self.assertEqual(v["status"],"BLOCKED")
        self.assertEqual(v["reason_code"],"AMD_URL_OR_STATUS_NOT_TRUSTED")
        r=Reply(sample())
        r.headers["Content-Type"]="application/pdf"
        x=p.fetch_amd_official_2025_once(open_once=lambda req:r)
        self.assertEqual(x["status"],"BLOCKED")
        self.assertEqual(x["reason_code"],"AMD_MIME_UNEXPECTED")


if __name__=="__main__":
    unittest.main()
