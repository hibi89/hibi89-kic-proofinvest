"""Isolated Korean stock price demo regression, all synthetic test input."""
from __future__ import annotations
from datetime import date,timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch
from proofinvest.kr_stock_demo import analyze_kr_prices

def fixture(n=40, flat=False):
    day=date(2026,8,3)
    stock,index=Decimal("70000"),Decimal("3000")
    rows=["date,stock_close,benchmark_close"]
    for i in range(n):
        while day.weekday()>4: day+=timedelta(days=1)
        if i:
            change=Decimal("0") if flat else (Decimal("0.01") if i%2 else Decimal("-0.01"))
            index*=1+change
            stock*=1+Decimal("1.4")*change
        rows.append(f"{day.isoformat()},{stock:.8f},{index:.8f}")
        day+=timedelta(days=1)
    return ("\n".join(rows)+"\n").encode()

def run(raw,**kw):
    args={"ticker":"005930","benchmark":"KOSPI","as_of":"2026-11-06"}
    args.update(kw)
    return analyze_kr_prices(raw,**args)

class KrStockTests(TestCase):
    def test_offline_beta_and_guard(self):
        with patch("urllib.request.urlopen",side_effect=AssertionError("NETWORK")) as call:
            result=run(fixture())
        call.assert_not_called()
        self.assertAlmostEqual(float(result["beta"]),1.4,places=3)
        self.assertEqual(result["network_requests"],0)
        self.assertEqual(result["guard_policy_preview"],"HOLD")
        for f in ("source_authenticated","source_rights_verified",
                  "external_sharing_allowed","full_a_b_c_ready","market_bubble_proven"):
            self.assertIs(result[f],False)
    def test_variance_zero_fails_closed(self):
        result=run(fixture(flat=True))
        self.assertEqual(result["status"],"INSUFFICIENT_VARIANCE")
        self.assertIsNone(result["beta"])
    def test_ticker_and_benchmark_not_confused_with_us(self):
        for kwargs in ({"ticker":"AAPL"},{"benchmark":"NASDAQ_100"},
                       {"as_of":"2026-01-01"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run(fixture(),**kwargs)
    def test_malformed_and_short_inputs_blocked(self):
        for raw in (b"",fixture(30),fixture(502),
                    fixture().replace(b"stock_close",b"adj_close",1),
                    fixture().replace(b",70000.00000000,",b",-1,",1)):
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError):
                run(raw)
