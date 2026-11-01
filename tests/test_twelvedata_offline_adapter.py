"""P109 Twelve Data offline response-to-P108 bridge: no provider HTTP/key."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import csv
from io import StringIO
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest import twelvedata_offline_adapter as td
from tests.test_market_price_csv import csv_from_fixture


def _fixtures():
    rows = list(csv.DictReader(StringIO(csv_from_fixture().decode("utf-8"))))
    def make(symbol, kind, col):
        return {
            "status": "ok",
            "meta": {"symbol": symbol, "type": kind, "interval": "1day",
                     "exchange_timezone": "America/New_York",
                     "currency": "USD"},
            "values": [
                {"datetime": r["date"], "close": r[col]}
                for r in reversed(rows)
            ],
        }
    return make("NVDA", "Common Stock", "security_close"), make(
        "NDX", "Index", "benchmark_close")


def _raw(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode()


def _test(stock=None, index=None, **changes):
    a, b = _fixtures()
    return td.run_private_twelvedata_p108(
        _raw(a if stock is None else stock),
        _raw(b if index is None else index),
        as_of="2025-10-16", retrieved_at="2025-10-16",
        acknowledged_internal_test=True, **changes)


class TwelveDataOfflineAdapterTests(unittest.TestCase):
    def test_internal_response_goes_into_real_p108_ols_without_any_provider_calls(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NETWORK")) as net:
            out = _test()
        net.assert_not_called()
        self.assertEqual(out["status"], "OFFLINE_MARKET_MATH_ONLY_UNAUTHENTICATED")
        self.assertEqual(out["analysis"]["engine_a"]["status"], "REPORTED_UNVERIFIED")
        self.assertEqual(out["analysis"]["engine_b"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(out["analysis"]["engine_c"]["status"], "UNAVAILABLE")
        self.assertEqual(out["intake"]["observation_count"], 45)
        self.assertEqual(out["intake"]["first_date"], "2025-08-01")
        self.assertEqual(out["intake"]["stock_symbol"], "NVDA")
        self.assertEqual(out["intake"]["index_symbol"], "NDX")
        self.assertEqual(out["guard_decision"], "HOLD")
        self.assertEqual(out["external_requests_executed"], 0)
        self.assertFalse(out["intake"]["commercial_display_permitted"])
        self.assertFalse(out["full_real_data_pipeline_verified"])
        self.assertNotIn("market_csv", out["intake"])
        self.assertAlmostEqual(float(out["analysis"]["engine_a"]["beta"]), 1.5, places=3)

    def test_operator_license_gate_required(self):
        a, b = _fixtures()
        with self.assertRaisesRegex(ValueError, "TEST_ONLY_USAGE_ACK_REQUIRED"):
            td.prepare_private_twelvedata_pair(_raw(a), _raw(b))
        with self.assertRaisesRegex(ValueError, "TEST_ONLY_USAGE_ACK_REQUIRED"):
            td.run_private_twelvedata_p108(_raw(a), _raw(b))

    def test_etf_proxy_wrong_index_type_ticker_stock_or_currency_blocked(self):
        a, b = _fixtures()
        cases = []
        c = deepcopy(b); c["meta"]["type"] = "ETF"; cases.append((a, c))
        c = deepcopy(b); c["meta"]["symbol"] = "QQQ"; cases.append((a, c))
        c = deepcopy(a); c["meta"]["symbol"] = "AAPL"; cases.append((c, b))
        c = deepcopy(a); c["meta"]["currency"] = "EUR"; cases.append((c, b))
        c = deepcopy(b); c["meta"]["interval"] = "1week"; cases.append((a, c))
        c = deepcopy(b); c["meta"]["exchange_timezone"] = "Etc/UTC"; cases.append((a, c))
        for stock, index in cases:
            with self.subTest(case=index["meta"]), self.assertRaises(ValueError):
                _test(stock, index)
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_INDEX_SYMBOL"):
            _test(index_symbol="QQQ")

    def test_bad_provider_error_nonfinite_duplicate_bodies(self):
        a, b = _fixtures()
        for raw in (
            b'{"status":"error","message":"API credits exceeded"}',
            b'{"status":"ok","status":"ok"}',
            b'{"meta":NaN,"values":[],"status":"ok"}',
            b"\xff",
            b"z" * (td.MAX_RESPONSE_BYTES + 1),
        ):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                td.prepare_private_twelvedata_pair(
                    _raw(a), raw, as_of="2025-10-16",
                    retrieved_at="2025-10-16", acknowledged_internal_test=True)

    def test_duplicate_dates_wrong_calendar_and_wrong_order(self):
        a, b = _fixtures()
        changes=[]
        c=deepcopy(a); c["values"][1] = deepcopy(c["values"][0]); changes.append((c,b))
        c=deepcopy(b); c["values"].pop(); changes.append((a,c))
        c=deepcopy(a); c["values"] = list(reversed(c["values"])); changes.append((c,b))
        c=deepcopy(b); c["values"][0]["datetime"] = "2025-08-03"; changes.append((a,c))
        for x,y in changes:
            with self.subTest(changes=y["values"][0]), self.assertRaises(ValueError):
                _test(x,y)

    def test_invalid_prices_and_future_or_pre_ir_rows(self):
        a, b = _fixtures()
        for close in ("0", "-2", "NaN", "Infinity", "=2+2", "100000000000.0"):
            c=deepcopy(a); c["values"][0]["close"]=close
            with self.subTest(close=close), self.assertRaises(ValueError):
                _test(c,b)
        for when in ("2025-02-26", "2028-02-01", "not-a-date"):
            c=deepcopy(a); c["values"][-1]["datetime"]=when
            with self.subTest(day=when), self.assertRaises(ValueError):
                _test(c,b)

    def test_retrieval_after_asof_and_future_refused(self):
        a,b=_fixtures()
        for received,asof in (("2025-10-17","2025-10-16"),
                              ("2100-01-01","2100-01-01"),
                              ("2025-10-16","2025-10-15")):
            with self.subTest(received=received), self.assertRaises(ValueError):
                td.prepare_private_twelvedata_pair(
                    _raw(a), _raw(b), as_of=asof,
                    retrieved_at=received, acknowledged_internal_test=True)

    def test_keyless_canonical_url_hashes_are_raw_responses(self):
        a,b=_fixtures()
        raw1, raw2 = _raw(a), _raw(b)
        pair=td.prepare_private_twelvedata_pair(
            raw1,raw2,as_of="2025-10-16",
            retrieved_at="2025-10-16",acknowledged_internal_test=True)
        self.assertEqual(pair["stock_response_sha256"],sha256(raw1).hexdigest())
        self.assertEqual(pair["index_response_sha256"],sha256(raw2).hexdigest())
        self.assertEqual(pair["paired_csv_sha256"],sha256(pair["market_csv"]).hexdigest())
        self.assertEqual(pair["source_url_no_credentials"],
                         "https://api.twelvedata.com/time_series")

    def test_cli_no_files_never_http_or_input_echo(self):
        cmd=[sys.executable,"-B","-m","proofinvest.twelvedata_offline_adapter"]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            stock,index=_fixtures()
            (p/"stock.json").write_bytes(_raw(stock))
            (p/"index.json").write_bytes(_raw(index))
            base=cmd+["--stock-response",str(p/"stock.json"),
                      "--index-response",str(p/"index.json"),
                      "--as-of","2025-10-16","--retrieved-at","2025-10-16"]
            denied=subprocess.run(base,capture_output=True,text=True)
            self.assertEqual(denied.returncode,2)
            ok=subprocess.run(base+["--confirm-internal-test-only"],
                              capture_output=True,text=True)
            self.assertEqual(ok.returncode,0,ok.stdout+ok.stderr)
            parsed=json.loads(ok.stdout)
            self.assertEqual(parsed["analysis"]["engine_a"]["status"],"REPORTED_UNVERIFIED")
            self.assertFalse(parsed["intake"]["provider_rights_verified"])
            self.assertFalse(parsed["analysis"]["full_abc_authenticated"])
            self.assertEqual(parsed["external_requests_executed"],0)
            self.assertNotIn('"market_csv"',ok.stdout)
            self.assertNotIn('"values"',ok.stdout)


if __name__ == "__main__":
    unittest.main()
