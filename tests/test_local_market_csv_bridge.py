"""P169 offline stock/true NDX CSV adapter, original-byte lineage and rights HOLD."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.local_market_csv_bridge import (
    normalize_market_csv, build_csv_lineage_receipt,
    inspect_csv_lineage_receipt,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.ticker_source_clearance_packet import inspect_source_clearance_packet
from tests.test_ticker_offline_review_builder import payload
from tests.test_ticker_market_pair_evidence import _body


def local_csv(symbol: str, start: int = 100) -> bytes:
    provider_shape = json.loads(_body(symbol, start))
    series = provider_shape["Time Series (Daily)"]
    rows = ["symbol,date,close"] + [
        f"{symbol},{day},{series[day]['4. close']}"
        for day in sorted(series)
    ]
    return ("\n".join(rows) + "\n").encode()


def local_csv_result():
    args = payload()
    stock_raw = local_csv("NVDA")
    index_raw = local_csv("NDX", 10000)
    stock = normalize_market_csv(
        stock_raw, symbol="NVDA", as_of=args["as_of"], is_index=False,
    )
    ndx = normalize_market_csv(
        index_raw, symbol="NDX", as_of=args["as_of"], is_index=True,
    )
    review = build_offline_initial_review(
        **{**args, "stock_raw": stock["normalized_json"],
           "index_raw": ndx["normalized_json"]}
    )
    assert review["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED", review
    return args, stock_raw, index_raw, stock, ndx, review


class MarketCsvInputTests(unittest.TestCase):
    def test_correct_stock_and_ndx_csv_drive_same_strict_a_b_c_math_without_http(self):
        with (
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO_VENDOR_HTTP")) as provider,
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NO_SEC_HTTP")) as sec,
        ):
            args, rawstock, rawndx, stock, ndx, review = local_csv_result()
            receipt = build_csv_lineage_receipt(
                stock=stock, index=ndx, packet=review["review_packet"],
                stock_csv_raw=rawstock, index_csv_raw=rawndx,
            )
        provider.assert_not_called()
        sec.assert_not_called()
        self.assertEqual(review["matched_sessions"], 65)
        self.assertEqual(review["guard_policy_preview"], "HOLD")
        self.assertEqual(review["status"], "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED")
        self.assertEqual(stock["rows"], 65)
        self.assertEqual(ndx["rows"], 65)
        self.assertEqual(ndx["raw_csv_sha256"], sha256(rawndx).hexdigest())
        self.assertEqual(ndx["publisher_origin_authenticated"], False)
        self.assertEqual(ndx["rights_verified"], False)
        self.assertEqual(
            inspect_csv_lineage_receipt(
                receipt, packet=review["review_packet"])["status"],
            "CSV_LINEAGE_MATCHED_RIGHTS_PENDING",
        )
        self.assertFalse(inspect_source_clearance_packet(
            review["source_clearance_report"],
            review_packet=review["review_packet"])["source_rights_verified"])
        self.assertNotIn(b"Time Series (Daily)", receipt)
        self.assertNotIn(b"close_observations", receipt)
        self.assertNotIn(b"symbol,date,close", receipt)

    def test_unsuitable_symbols_and_mixed_stock_ndx_fail_closed(self):
        cases = [
            (local_csv("QQQ", 10000), "NDX", True),
            (local_csv("SPY", 10000), "NDX", True),
            (local_csv("NDX", 10000), "NVDA", False),
            (local_csv("NDX", 10000), "NDX", False),
            (local_csv("NVDA"), "NVDA", True),
        ]
        for raw, expected, is_index in cases:
            with self.subTest(expected=expected, index=is_index,
                              raw=raw[:18]), self.assertRaises(ValueError):
                normalize_market_csv(
                    raw, symbol=expected, as_of="2026-02-01", is_index=is_index,
                )

    def test_future_duplicated_unsorted_formula_empty_and_hidden_columns_rejected(self):
        base = local_csv("NDX", 10000).decode()
        lines = base.splitlines()
        cases = [
            base.replace("symbol,date,close", "date,close"),
            base.replace("symbol,date,close", "symbol,date,adjusted_close"),
            base.replace("symbol,date,close", "symbol,date,close,secret"),
            base.replace("NDX,", "QQQ,", 1),
            "\n".join([lines[0], lines[2], lines[1]] + lines[3:]) + "\n",
            base.replace(lines[1], lines[1]+"\n"+lines[1], 1),
            base.replace(lines[1], "NDX,2030-01-01,10000", 1),
            base.replace(lines[1], "NDX,2025-11-03,=1+1", 1),
            base.replace(lines[1], "NDX,2025-11-03,0", 1),
            base + "NDX,2026-02-02,12000\n",
            "symbol,date,close\n" + "\n".join(lines[1:10]) + "\n",
        ]
        for raw in cases:
            with self.subTest(hint=raw[:65]), self.assertRaises(ValueError):
                normalize_market_csv(
                    raw.encode(), symbol="NDX", as_of="2026-02-01", is_index=True,
                )
        with self.assertRaises(ValueError):
            normalize_market_csv(
                b"x"*32769, symbol="NDX", as_of="2026-02-01", is_index=True,
            )

    def test_original_csv_changed_after_normalization_cannot_be_paired_with_packet(self):
        _, rawstock, rawndx, stock, ndx, review = local_csv_result()
        with self.assertRaises(ValueError):
            build_csv_lineage_receipt(
                stock=stock, index=ndx, packet=review["review_packet"],
                stock_csv_raw=rawstock + b" ", index_csv_raw=rawndx,
            )
        changed = deepcopy(ndx)
        changed["normalized_json"] = ndx["normalized_json"] + b" "
        with self.assertRaises(ValueError):
            build_csv_lineage_receipt(
                stock=stock, index=changed, packet=review["review_packet"],
                stock_csv_raw=rawstock, index_csv_raw=rawndx,
            )

    def test_resigned_lineage_cannot_claim_provider_or_redistribution_rights(self):
        _, rawstock, rawndx, stock, ndx, review = local_csv_result()
        packet = review["review_packet"]
        original = json.loads(build_csv_lineage_receipt(
            stock=stock, index=ndx, packet=packet,
            stock_csv_raw=rawstock, index_csv_raw=rawndx,
        ))
        for field, value in (
            ("source_rights_verified", True),
            ("public_submission_allowed", True),
            ("stock_normalized_json_sha256", "f"*64),
            ("index_original_csv_sha256", "B"*64),
            ("ticker", "AAPL"),
        ):
            modified = deepcopy(original)
            modified[field] = value
            modified.pop("receipt_sha256")
            canonical = lambda o: (
                json.dumps(o, ensure_ascii=False, sort_keys=True,
                           allow_nan=False, separators=(",", ":"))+"\n").encode()
            modified["receipt_sha256"] = sha256(canonical(modified)).hexdigest()
            with self.subTest(field=field), self.assertRaises(ValueError):
                inspect_csv_lineage_receipt(canonical(modified), packet=packet)


if __name__ == "__main__":
    unittest.main()
