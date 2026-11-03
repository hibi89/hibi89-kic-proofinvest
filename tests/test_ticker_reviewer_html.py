"""P170 printable source-linked A/B/C report: verified bytes, no active HTML."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.ticker_reviewer_html import render_reviewer_html, _e
from proofinvest.ticker_source_clearance_packet import inspect_source_clearance_packet
from tests.test_ticker_offline_review_builder import payload
from tests.test_local_market_csv_bridge import (
    local_csv, normalize_market_csv, build_csv_lineage_receipt,
)


class ReviewerHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = payload()
        cls.review = build_offline_initial_review(**cls.inputs)
        assert cls.review["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"

    def test_offline_report_has_a_b_c_real_recomputed_metrics_and_hold(self):
        with (
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO_PROVIDER_NETWORK")) as provider,
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NO_SEC_NETWORK")) as sec,
        ):
            raw = render_reviewer_html(
                review_packet=self.review["review_packet"],
                rights_gap_report=self.review["source_clearance_report"],
            )
        provider.assert_not_called()
        sec.assert_not_called()
        content = raw.decode("utf-8")
        self.assertLessEqual(len(raw), 80_000)
        for expected in (
            "<!DOCTYPE html>", "Content-Security-Policy", "default-src 'none'",
            "Engine A", "Engine B", "Engine C",
            "NDX", "2026-02-01", "GUARD", "HOLD",
            "source", "SHA-256", "미인증",
            "PROVIDER_ACCOUNT_AND_PREMIUM_NDX_ENTITLEMENT",
            sha256(self.review["review_packet"]).hexdigest(),
            sha256(self.review["source_clearance_report"]).hexdigest(),
        ):
            with self.subTest(token=expected):
                self.assertIn(expected.lower(), content.lower())
        for forbidden in (
            "<script", "<iframe", "<img", "<form",
            "href=", "src=", "http://", "https://",
            "close_observations", "Time Series (Daily)",
            "api_key", "apikey", "SYNTHETIC ISSUER",
        ):
            self.assertNotIn(forbidden.lower(), content.lower())
        self.assertEqual(raw, render_reviewer_html(
            review_packet=self.review["review_packet"],
            rights_gap_report=self.review["source_clearance_report"],
        ))

    def test_wrong_rights_gap_packet_mismatch_and_extra_bytes_fail_closed(self):
        packet = self.review["review_packet"]
        gap = self.review["source_clearance_report"]
        cases = (
            (packet + b" ", gap),
            (packet, gap + b" "),
            (packet, b"{}"),
            (b"{}", gap),
            (packet, b"x" * 9217),
        )
        for p, r in cases:
            with self.subTest(packet=len(p), rights=len(r)), self.assertRaises(ValueError):
                render_reviewer_html(review_packet=p, rights_gap_report=r)

    def test_csv_lineage_is_optional_but_when_supplied_must_link(self):
        inputs = payload()
        stock_raw = local_csv("NVDA")
        index_raw = local_csv("NDX", 10000)
        stock = normalize_market_csv(
            stock_raw, symbol="NVDA", as_of=inputs["as_of"], is_index=False,
        )
        index = normalize_market_csv(
            index_raw, symbol="NDX", as_of=inputs["as_of"], is_index=True,
        )
        reviewed = build_offline_initial_review(
            **{**inputs, "stock_raw": stock["normalized_json"],
               "index_raw": index["normalized_json"]},
        )
        self.assertEqual(reviewed["status"], "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED")
        lineage = build_csv_lineage_receipt(
            stock=stock, index=index, packet=reviewed["review_packet"],
            stock_csv_raw=stock_raw, index_csv_raw=index_raw,
        )
        html = render_reviewer_html(
            review_packet=reviewed["review_packet"],
            rights_gap_report=reviewed["source_clearance_report"],
            csv_lineage=lineage,
        ).decode("utf-8")
        self.assertIn("CSV 원본→정규화 JSON 계보 연결: PASS", html)
        for mutated in (lineage + b" ", b"{}", b"x"*3073):
            with self.subTest(size=len(mutated)), self.assertRaises(ValueError):
                render_reviewer_html(
                    review_packet=reviewed["review_packet"],
                    rights_gap_report=reviewed["source_clearance_report"],
                    csv_lineage=mutated,
                )

    def test_untrusted_strings_are_html_escaped(self):
        self.assertEqual(_e("<script>alert('X')</script>"),
                         "&lt;script&gt;alert(&#x27;X&#x27;)&lt;/script&gt;")
        self.assertEqual(_e('A&B"'), "A&amp;B&quot;")
        self.assertEqual(_e(None), "UNAVAILABLE")
        for untrusted in (3.14, {"foo": "bar"}, ["x"], True):
            with self.subTest(value=untrusted), self.assertRaises(ValueError):
                _e(untrusted)


if __name__ == "__main__":
    unittest.main()
