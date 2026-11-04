"""P209 NVIDIA genuine separate issuer publisher yearly GAAP vs quarterly tests."""
from __future__ import annotations
import io
import unittest
from unittest.mock import patch
from proofinvest import nvidia_issuer_fy2026_once as p


def row(name, vals):
    return "<tr><td>"+name+"</td>"+"".join("<td>"+x+"</td>" for x in vals)+"</tr>"


def sample() -> bytes:
    quarter_year=("<tr><th>Three Months Ended</th><th>Twelve Months Ended</th></tr>"
                  "<tr><th>January 25, 2026</th><th>January 26, 2025</th></tr>")
    return ("<html><body><h1>NVIDIA Announces Financial Results for Fiscal 2026</h1>"
            "<h2>February 25, 2026</h2>"
            "<table>"+quarter_year
            +row("Cost of revenue",["17,034","10,608","62,475","32,639"])
            +row("Gross profit",["51,093","28,723","153,463","97,858"])
            +row("Revenue",["68,127","39,331","215,938","130,497"])
            +row("Net income",["42,960","22,091","120,067","72,880"])
            +"</table><table>"+quarter_year
            +row("Cash flows from operating activities",[])
            +row("Net income",["42,960","22,091","120,067","72,880"])
            +row("Net cash provided by operating activities",["36,190","16,628","102,718","64,089"])
            +"</table><table>"
            "<tr><th>January 25, 2026</th><th>January 26, 2025</th></tr>"
            +row("Accounts receivable, net",["38,466","23,065"])
            +row("Inventories",["21,403","10,080"])
            +row("Total current assets",["125,605","80,126"])
            +"</table></body></html>").encode()


class Reply(io.BytesIO):
    def __init__(self, data, url=p._URL):
        super().__init__(data)
        self.status=200
        self.url=url
        self.headers={"Content-Type":"text/html","Content-Length":str(len(data))}
    def geturl(self):
        return self.url


class P209Tests(unittest.TestCase):
    def test_second_issuer_real_financials_separate_quarter_and_year(self):
        f=p.parse_nvidia_official_fy2026(sample())
        self.assertEqual(f["income"]["q4_2026_revenue"],"68127")
        self.assertEqual(f["income"]["fy2026_revenue"],"215938")
        self.assertEqual(f["income"]["fy2025_revenue"],"130497")
        self.assertEqual(f["income"]["fy2026_net_income"],"120067")
        self.assertEqual(f["cash"]["fy2026_cash_from_operations"],"102718")
        self.assertEqual(f["balance_sheet"]["trade_receivables"]["fy2026"],"38466")
        self.assertEqual(f["balance_sheet"]["inventories"]["fy2025"],"10080")
        self.assertTrue(f["release_is_unaudited"])
        self.assertFalse(f["misconduct_proven"])
        self.assertIsNone(f["trading_action"])

    def test_gaap_period_drift_and_forged_values_fail_closed(self):
        for value in (
            sample().replace(b"215,938",b"215,939"),
            sample().replace(b"120,067",b"116,997"),
            sample().replace(b"102,718",b"102,719"),
            sample().replace(b"38,466",b"38,467"),
            sample().replace(b"January 25, 2026",b"January 25, 2027"),
            sample().replace(b"Twelve Months Ended",b"Nine Months Ended"),
            sample().replace(b"Gross profit",b"Other metric"),
            sample()+sample(),
        ):
            with self.subTest(len=len(value)):
                with self.assertRaises(ValueError):
                    p.parse_nvidia_official_fy2026(value)

    def test_issuer_one_get_explicitly_not_sec_or_license_or_trade(self):
        reqs=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_NETWORK")):
            result=p.nvidia_issuer_one_shot(
                open_once=lambda request:(reqs.append(request),Reply(sample()))[1])
        self.assertEqual(result["status"],"NVDA_REAL_ISSUER_FY2026_2025_GAAP_FINANCIALS_CONFIRMED_LIMITED")
        self.assertEqual(len(reqs),1)
        self.assertEqual(result["http_get_attempted"],1)
        self.assertEqual(result["http_get_budget"],1)
        for key in ("sec_original_byte_identical", "data_commercial_llm_rights_verified",
                    "real_stock_ndx_peer_licensed", "full_abc_ready","trade_executed",
                    "raw_saved","raw_uploaded"):
            self.assertFalse(result[key],key)

    def test_redirect_and_stale_identity_fail_before_financial_success(self):
        forged=p.nvidia_issuer_one_shot(open_once=lambda req:Reply(sample(),url="https://outside.invalid/"))
        self.assertEqual(forged["status"],"BLOCKED")
        self.assertEqual(forged["reason_code"],"NVIDIA_ISSUER_ORIGIN_STATUS_CHANGED")
        old=p.nvidia_issuer_one_shot(
            open_once=lambda req:Reply(sample().replace(b"February 25, 2026",b"February 25, 2025")))
        self.assertEqual(old["status"],"BLOCKED")
        self.assertEqual(old["reason_code"],"NVIDIA_ISSUER_RELEASE_IDENTITY_INVALID")

    def test_negative_units_and_non_gaap_are_not_accepted_as_positive_gaap(self):
        for wrong in (
            sample().replace(b"215,938",b"$215.938"),
            sample().replace(b"38,466",b"(38,466)"),
            sample().replace(b"Net cash provided by operating activities",b"Net cash provided by financing activities"),
        ):
            with self.subTest():
                with self.assertRaises(ValueError):
                    p.parse_nvidia_official_fy2026(wrong)


if __name__=="__main__":
    unittest.main()
