"""P207 real primary release working-capital evidence; synthetic adversarial cases."""
from __future__ import annotations
import io
import unittest
from unittest.mock import patch
from proofinvest import dell_working_capital_2026_once as p


def sample() -> bytes:
    def row(name, values):
        return "<tr><td>"+name+"</td>"+ "".join("<td>"+v+"</td>" for v in values)+"</tr>"
    return ("<html><body><h1>Dell Technologies FY 2026 vs FY 2025</h1>"
            "<table><tr><th>As at</th><th>January 30, 2026</th>"
            "<th>January 31, 2025</th></tr>"
            +row("Current assets:", [])
            +row("Accounts receivable, net of allowance of $77 and $63", ["17,585","10,298"])
            +row("Short-term financing receivables", ["8,458","5,304"])
            +row("Inventories", ["10,437","6,716"])
            +row("Total current assets", ["57,602","36,229"])
            +"</table>"
            "<table><tr><th>Three Months Ended</th><th>Fiscal Year Ended</th></tr>"
            "<tr><th>January 30, 2026</th><th>January 31, 2025</th></tr>"
            +row("Cash flows from operating activities:",[])
            +row("Net income",["2,259","1,532","5,936","4,576"])
            +row("Change in cash from operating activities",["4,674","585","11,185","4,521"])
            +"</table></body></html>").encode("utf-8")


class Response(io.BytesIO):
    def __init__(self, data, url=p._URL):
        super().__init__(data)
        self.url=url
        self.status=200
        self.headers={"Content-Type":"text/html","Content-Length":str(len(data))}
    def geturl(self):
        return self.url


class WorkingCapitalTests(unittest.TestCase):
    def test_real_dimension_distinct_from_p206_cfo_and_income(self):
        v=p.parse_issuer_working_capital_release(sample())
        self.assertEqual(v["working_capital"]["trade_receivables"]["growth_pct"],"70.76")
        self.assertEqual(v["working_capital"]["inventories"]["growth_pct"],"55.41")
        self.assertEqual(v["working_capital"]["trade_receivables"]["growth_minus_revenue_pp"],"51.96")
        self.assertEqual(v["working_capital"]["inventories"]["growth_minus_revenue_pp"],"36.60")
        self.assertEqual(v["working_capital"]["current_assets"]["fy2026_usd_millions"],"57602")
        self.assertEqual(v["revenue_growth_pct"],"18.80")
        self.assertEqual(v["source_is_unaudited"],True)
        self.assertFalse(v["misconduct_proven"])
        self.assertIsNone(v["trade_action"])

    def test_forged_assets_and_misordered_period_rejected(self):
        for x in (
            sample().replace(b"17,585",b"17,586"),
            sample().replace(b"10,437",b"10,438"),
            sample().replace(b"36,229",b"36,228"),
            sample().replace(b"January 30, 2026",b"January 30, 2027"),
            sample().replace(b"Accounts receivable, net of allowance",b"Short-term financing receivables, net of allowance"),
            sample()+sample(),
        ):
            with self.subTest(length=len(x)):
                with self.assertRaises(ValueError):
                    p.parse_issuer_working_capital_release(x)

    def test_first_party_not_a_forged_rights_or_origin_attestation(self):
        calls=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NETWORK")):
            out=p.verify_dell_working_capital_once(opener=lambda req:(calls.append(req),Response(sample()))[1])
        self.assertEqual(len(calls),1)
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(out["reason_code"],"P206_ISSUER_ORIGINAL_SOURCE_VERSION_MISMATCH")
        self.assertEqual(out["http_get_budget"],1)
        self.assertEqual(out["sec_http_calls"],0)
        self.assertFalse(out["source_commercial_ai_rights_verified"])
        self.assertFalse(out["full_engine_b_complete"])
        self.assertFalse(out["trade_executed"])
        self.assertFalse(out["raw_saved"])

    def test_wrong_https_origin_not_followed(self):
        out=p.verify_dell_working_capital_once(opener=lambda req:Response(sample(),url="https://other.example.com"))
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(out["reason_code"],"WORKING_CAPITAL_ORIGIN_OR_STATUS_CHANGED")
        self.assertEqual(out["redirects_followed"],0)


if __name__=="__main__":
    unittest.main()
