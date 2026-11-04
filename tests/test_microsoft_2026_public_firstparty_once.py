"""P202 real firstparty MSFT annual GAAP source vs adjusted release."""
from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from proofinvest import microsoft_2026_public_firstparty_once as p


def sample()->bytes:
    return ("""<html><body><h1>Microsoft Corp. July 29, 2026</h1>
     <h2>Fiscal Year 2026 Results</h2>
     <p>Microsoft Corp. fiscal year ended June 30, 2026</p>
     <h3>Twelve Months Ended June 30</h3>
     <p>2026 2025 As Reported (GAAP) As Adjusted (non-GAAP)</p>
     <table><tr><td>Revenue</td><td>331,839</td><td>281,724</td></tr>
     <tr><td>Net Income</td><td>133,749</td><td>128,786</td>
     <td>101,832</td><td>105,452</td></tr></table>
     <h2>Business Outlook</h2></body></html>""").encode()


class Response(io.BytesIO):
    def __init__(self,body,url=p._URL):
        super().__init__(body)
        self.status=200
        self.url=url
        self.headers={"Content-Type":"text/html","Content-Length":str(len(body))}
    def geturl(self):
        return self.url


class PublicMicrosoftTwoIssuerTests(unittest.TestCase):
    def test_2026_actual_gaap_and_2025_with_non_gaap_separate(self):
        x=p.inspect_microsoft_actual_fy2026_issuer_release(sample())
        self.assertEqual(x["ticker"],"MSFT")
        self.assertEqual(x["fiscal_end_2026"],"2026-06-30")
        self.assertTrue(x["gaap_non_gaap_separated"])
        self.assertEqual(x["gaap_revenue_yoy_pct"],"17.79")
        self.assertEqual(x["gaap_net_income_yoy_pct"],"31.34")
        self.assertFalse(x["sec_edgar_original_authenticated"])
        self.assertFalse(x["rights_for_external_ai_or_commercial_redistribution_proven"])

    def test_corrupt_financial_and_dated_issuer_sections_block(self):
        for old,new in (
            (b"331,839",b"331,840"),(b"281,724",b"281,725"),
            (b"133,749",b"133,748"),(b"101,832",b"101,831"),
            (b"128,786",b"128,787"),(b"105,452",b"105,453"),
            (b"Microsoft Corp.",b"Unknown Ltd."),
            (b"July 29, 2026",b"July 29, 2025"),
            (b"fiscal year ended June 30, 2026",b"fiscal year ended March 31, 2026"),
            (b"As Reported (GAAP)",b"NonGAAP only"),
        ):
            with self.subTest(old=old):
                with self.assertRaises(ValueError):
                    p.inspect_microsoft_actual_fy2026_issuer_release(sample().replace(old,new))

    def test_public_single_get_no_market_or_private_external_use(self):
        calls=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NETWORK")):
            r=p.verify_microsoft_public_annual_release_once(
                opener=lambda req:(calls.append(req),Response(sample()))[1])
        self.assertEqual(len(calls),1)
        self.assertEqual(r["status"],
                         "ACTUAL_SECOND_ISSUER_MSFT_PUBLIC_FY2026_GAAP_FACTS_RECOMPUTED")
        self.assertTrue(r["actual_second_ticker_issuer_financials_verified"])
        self.assertEqual(r["external_sec_requests"],0)
        self.assertEqual(r["paid_requests"],0)
        for flag in ("sec_original_authenticated","same_sector_peer_comparability",
                     "stock_ndx_licensed","external_ai_rights_proven",
                     "trade_executed","raw_html_saved","raw_html_uploaded"):
            self.assertIs(r[flag],False)

    def test_cross_site_redirect_not_followed(self):
        calls=[]
        r=p.verify_microsoft_public_annual_release_once(
            opener=lambda req:(calls.append(req),Response(sample(),"https://www.sec.gov/no"))[1])
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(len(calls),1)
        self.assertEqual(r["redirects_followed"],0)
        self.assertEqual(r["external_sec_requests"],0)


if __name__=="__main__":
    unittest.main()
