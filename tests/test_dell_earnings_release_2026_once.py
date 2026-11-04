"""P206 fail-closed tests of annual vs quarter figures in two distinct issuer documents."""
from __future__ import annotations
import io
import unittest
from unittest.mock import patch
from proofinvest import dell_earnings_release_2026_once as p


def sample() -> bytes:
    def row(label, vals):
        return '<tr><td>'+label+'</td>'+''.join('<td>'+v+'</td>' for v in vals)+'</tr>'
    return ("<html><head><title>Dell Technologies FY 2026</title></head><body>"
        "<table><tr><th>Three Months Ended</th><th>Fiscal Year Ended</th></tr>"
        "<tr><th>January 30, 2026</th><th>January 31, 2025</th></tr>"
        +row("Cash flows from operating activities:",[])
        +row("Net income",["2,259","1,532","5,936","4,576"])
        +row("Change in cash from operating activities",["4,674","585","11,185","4,521"])
        +"</table></body></html>").encode()


class Reply(io.BytesIO):
    def __init__(self, data, url=p._URL):
        super().__init__(data)
        self.status=200
        self.url=url
        self.headers={"Content-Type":"text/html","Content-Length":str(len(data))}
    def geturl(self):
        return self.url


class DellSecondSourceTests(unittest.TestCase):
    def test_structured_release_two_full_years_not_quarters(self):
        r=p.parse_dell_public_fy2026_release(sample())
        self.assertTrue(r["release_is_unaudited"])
        self.assertEqual(r["fy2026_net_income"],"5936")
        self.assertEqual(r["fy2025_net_income"],"4576")
        self.assertEqual(r["fy2026_cash_from_operations"],"11185")
        self.assertEqual(r["fy2025_cash_from_operations"],"4521")
        self.assertEqual(r["fy2026_cfo_to_net_income"],"1.8843")
        self.assertEqual(r["fy2025_cfo_to_net_income"],"0.9880")

    def test_wrong_fy_quarter_income_cfo_and_header_rejected(self):
        for raw in (
            sample().replace(b"5,936",b"5,935"),
            sample().replace(b"4,521",b"4,522"),
            sample().replace(b"11,185",b"11,186"),
            sample().replace(b"Fiscal Year Ended",b"Quarterly Numbers"),
            sample().replace(b"January 31, 2025",b"January 31, 2024"),
            sample()+sample(),
        ):
            with self.subTest(raw_len=len(raw)):
                with self.assertRaises(ValueError):
                    p.parse_dell_public_fy2026_release(raw)

    def test_one_get_nonmatching_hash_is_not_implied_rights(self):
        requested=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NETWORK")):
            out=p.verify_dell_release_once(opener=lambda req:(requested.append(req),Reply(sample()))[1])
        self.assertEqual(out["status"],"REAL_SECOND_ISSUER_RELEASE_FY_CFO_NI_CROSSCHECKED_LIMITED")
        self.assertEqual(len(requested),1)
        self.assertEqual(out["http_get_attempted"],1)
        self.assertEqual(out["sec_http_calls"],0)
        self.assertFalse(out["issuer_sec_original_bytes_identical"])
        self.assertFalse(out["source_license_commercial_ai_verified"])
        self.assertFalse(out["full_abc_ready"])
        self.assertFalse(out["trade_executed"])
        self.assertFalse(out["raw_saved"])

    def test_forged_origin_blocks(self):
        out=p.verify_dell_release_once(opener=lambda req:Reply(sample(),url="https://example.org/not-dell"))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertIsNone(out["facts"])
        self.assertEqual(out["redirects_followed"],0)


if __name__=="__main__":
    unittest.main()
