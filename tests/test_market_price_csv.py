"""P47 paired daily price CSV -> trusted local-byte hash -> offline OLS.

Source origin, published_at, vendor license and dividends are NOT verified.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from proofinvest.market_price_csv import market_price_csv_to_json
from proofinvest.market_reality import MAX_UPLOAD_BYTES, analyze_market_reality
from tests.test_market_reality import fixture


def csv_from_fixture() -> bytes:
    data = fixture()
    a = data["security"]["observations"]
    b = data["index"]["observations"]
    rows = ["date,security_close,benchmark_close"]
    rows.extend(f'{x["date"]},{x["value"]},{y["value"]}'
                for x, y in zip(a, b))
    return ("\n".join(rows) + "\n").encode("utf-8")


def convert(raw=None, **changes):
    kw = {
        "issuer_cik": "0000000001", "as_of": "2025-10-16",
        "symbol": "SYNTH", "benchmark": "NASDAQ_100",
        "return_basis": "PRICE_ONLY_CLOSE",
        "source_url": "https://example.org/combined-price-sheet",
        "published_at": "2025-10-15",
    }
    kw.update(changes)
    return market_price_csv_to_json(
        csv_from_fixture() if raw is None else raw, **kw,
    )


class MarketPriceCsvTests(unittest.TestCase):
    def test_csv_to_regression_preserves_real_uploaded_bytes_sha(self):
        original = csv_from_fixture()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as network:
            normalized = convert(original)
            payload = json.loads(normalized)
            report = analyze_market_reality(
                payload, expected_issuer_cik="0000000001", analysis_as_of="2025-10-16")
        network.assert_not_called()
        self.assertEqual(len(payload["security"]["observations"]), 45)
        self.assertEqual(payload["security"]["source"]["sha256"],
                         hashlib.sha256(original).hexdigest())
        self.assertEqual(payload["index"]["source"]["sha256"],
                         hashlib.sha256(original).hexdigest())
        self.assertEqual(report["source"]["stock"]["sha256_reported"],
                         hashlib.sha256(original).hexdigest())
        self.assertAlmostEqual(float(report["beta"]), 1.5, places=3)
        self.assertEqual(report["status"], "REPORTED_UNVERIFIED")
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["audit_included"])
        self.assertFalse(report["trade_signal"])

    def test_bom_and_crlf_allowed_without_source_digest_confusion(self):
        original = b"\xef\xbb\xbf" + csv_from_fixture().replace(b"\n", b"\r\n")
        payload = json.loads(convert(original))
        self.assertEqual(payload["security"]["source"]["sha256"],
                         hashlib.sha256(original).hexdigest())
        self.assertEqual(payload["security"]["observations"][0]["date"], "2025-08-01")

    def test_fail_closed_invalid_headers_rows_and_formulas(self):
        good = csv_from_fixture()
        bads = {
            "missing_col":good.replace(b",benchmark_close", b"", 1),
            "reordered":good.replace(b"date,security_close,benchmark_close",
                                     b"date,benchmark_close,security_close", 1),
            "extra_col":good.replace(b"benchmark_close", b"benchmark_close,hidden", 1),
            "injection":good.replace(b",100,100", b",=HYPERLINK(1),100", 1),
            "negative":good.replace(b",100,100", b",-1,100", 1),
            "zero":good.replace(b",100,100", b",0,100", 1),
            "empty":good.replace(b",100,100", b",,100", 1),
            "extra_data":good.replace(b",100,100", b",100,100,x", 1),
            "bad_utf8":b"\xff" + good,
            "nul":good + b"\0",
            "too_long":good + b"x" * (MAX_UPLOAD_BYTES + 1),
            "invalid_header":b"date,close,index\n" + good.split(b"\n",1)[1],
            "not_enough":b"\n".join(good.split(b"\n")[:15]),
            "too_many":good + (b"2025-10-14,100,100\n" * 501),
            "blank_row":good.replace(b"\n", b"\n\n", 1),
        }
        for name, bad in bads.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                convert(bad)

    def test_future_and_out_of_order_dates_fail(self):
        for edit in ("future", "duplicate", "swap", "weekend"):
            data = csv_from_fixture().decode("utf-8").splitlines()
            if edit == "future":
                data[-1] = "2026-01-05," + data[-1].split(",", 1)[1]
            elif edit == "duplicate":
                data[2] = data[1]
            elif edit == "swap":
                data[4],data[5] = data[5],data[4]
            else:
                data[2] = "2025-08-03," + data[2].split(",", 1)[1]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                convert(("\n".join(data) + "\n").encode())

    def test_missing_source_rights_or_invalid_context_reject(self):
        for change in (
            {"issuer_cik":"0000000000"},
            {"as_of":"2025-09-01"},
            {"benchmark":"FAKE_INDEX"},
            {"return_basis":"GUARANTEED_TOTAL_RETURN"},
            {"symbol":"=2+2"},
            {"source_url":"file:///etc/passwd"},
            {"source_url":"https://example.org/?secret=x"},
            {"published_at":"2025-08-02"},
            {"published_at":"2025-10-17"},
            {"published_at":""},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                convert(**change)

    def test_normalized_output_does_not_create_persistent_files(self):
        payload = json.loads(convert())
        self.assertEqual(set(payload), {
            "schema", "issuer_cik", "as_of", "symbol", "benchmark",
            "return_basis", "security", "index",
        })
        self.assertNotIn("source_authenticated", payload)
        self.assertNotIn("market_bubble_pct", payload)


if __name__ == "__main__":
    unittest.main()
