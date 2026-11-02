"""P116 local source fallback: zero I/O, never authenticates issuer data."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_sources import prepare_local_ticker_sources
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from proofinvest import ticker_sec_transport as transport
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ticker_sec_original_guard_preview import valid_xhtml


class LocalFourSourceTests(unittest.TestCase):
    def case(self, *, original=None):
        _live, raws = valid_case()  # Existing mocked HTTP, no network.
        if original is not None:
            raws = dict(raws, original_10k=original)
        receipt = prepare_local_ticker_sources(
            ticker="NVDA", as_of="2025-10-16", sources=raws)
        return receipt, raws

    def test_four_sources_enable_only_unverified_same_filing_arithmetic(self):
        receipt, raws = self.case()
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("NO SEC HTTP")) as fetch:
            revenue = inspect_collected_annual_revenue(receipt, raws)
        fetch.assert_not_called()
        self.assertEqual(receipt["status"], "local_four_sources_unverified")
        self.assertEqual(receipt["http_requests_attempted"], 0)
        self.assertEqual(receipt["network_requests"], 0)
        self.assertFalse(receipt["live_sec_http_called"])
        self.assertFalse(receipt["source_authenticated"])
        self.assertEqual(revenue["status"], "REVENUE_CALCULATED_UNVERIFIED", revenue)
        self.assertEqual(revenue["growth_pct"], "100.00")
        self.assertFalse(revenue["source_authenticated"])
        self.assertFalse(revenue["guard_executed"])

    def test_original_ixbrl_context_and_guard_hold_without_authentication(self):
        receipt, raws = self.case(original=valid_xhtml())
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("NO SEC HTTP")) as fetch:
            original = inspect_original_guard_preview(receipt, raws)
        fetch.assert_not_called()
        self.assertEqual(original["status"], "ORIGINAL_CONTEXT_MATCH_UNVERIFIED", original)
        self.assertEqual(original["guard_preview"]["decision"], "HOLD")
        self.assertFalse(original["source_authenticated"])
        self.assertFalse(original["guard_executed"])
        self.assertFalse(original["audit_written"])
        self.assertFalse(original["trade_executed"])

    def test_missing_extra_or_oversize_input_is_denied(self):
        _receipt, raws = self.case()
        for altered in (None, {}, {"ticker_map": raws["ticker_map"]},
                        dict(raws, extra=b"x"),
                        dict(raws, original_10k=b""),
                        dict(raws, ticker_map=b"x" * (3_000_001))):
            with self.subTest(source_keys=list(altered) if isinstance(altered, dict) else None):
                out = prepare_local_ticker_sources(ticker="NVDA",
                         as_of="2025-10-16", sources=altered)
                self.assertEqual(out["status"], "unavailable")
                self.assertNotIn("source_sha256", out)
                self.assertEqual(out["network_requests"], 0)

    def test_cross_issuer_unknown_ticker_and_unmatched_filing_fail_closed(self):
        _receipt, raws = self.case()
        for ticker, cutoff in (("AAPL", "2025-10-16"), ("NVDA", "2024-01-01"),
                               ("../../NVDA", "2025-10-16")):
            with self.subTest(ticker=ticker, cutoff=cutoff):
                out = prepare_local_ticker_sources(
                    ticker=ticker, as_of=cutoff, sources=raws)
                self.assertEqual(out["status"], "unavailable")

    def test_changed_bytes_and_forged_online_semantics_denied_by_bridge(self):
        receipt, raws = self.case()
        for key in raws:
            changed = dict(raws, **{key: raws[key] + b" "})
            with self.subTest(name=key):
                out = inspect_collected_annual_revenue(receipt, changed)
                self.assertEqual(out["status"], "UNAVAILABLE")
        for change in ({"http_requests_attempted": 4},
                       {"live_sec_http_called": True},
                       {"source_authenticated": True},
                       {"network_requests": 1},
                       {"schema": "kuodra.single-ticker-sec-transport.v1"}):
            with self.subTest(change=change):
                out = inspect_collected_annual_revenue(receipt | change, raws)
                self.assertEqual(out["status"], "UNAVAILABLE")
                self.assertIsNone(out["growth_pct"])

    def test_receipt_is_deterministic_and_does_not_modify_inputs(self):
        _, raws = self.case()
        original = deepcopy(raws)
        left = prepare_local_ticker_sources(ticker="NVDA",
                                          as_of="2025-10-16", sources=raws)
        right = prepare_local_ticker_sources(ticker="NVDA",
                                           as_of="2025-10-16", sources=raws)
        self.assertEqual(left, right)
        self.assertEqual(raws, original)
        self.assertEqual(left["source_sha256"]["companyfacts"],
                         sha256(raws["companyfacts"]).hexdigest())
        self.assertNotIn("raw_sources", left)


if __name__ == "__main__":
    unittest.main()
