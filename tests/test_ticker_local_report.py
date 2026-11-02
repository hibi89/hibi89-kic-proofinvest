"""P117 read-only report: SHA bound, cannot upgrade local data rights."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_report import make_local_report, report_json_bytes
from proofinvest.ticker_local_sources import prepare_local_ticker_sources
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from proofinvest.ticker_market_industry_bridge import evaluate_ticker_a_c
from proofinvest import ticker_sec_transport as transport
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ticker_sec_original_guard_preview import valid_xhtml


def source_case():
    _, raws = valid_case()  # Existing pure mocked HTTP fixture.
    raws["original_10k"] = valid_xhtml()
    receipt = prepare_local_ticker_sources(
        ticker="NVDA", as_of="2025-10-16", sources=raws)
    revenue = inspect_collected_annual_revenue(receipt, raws)
    original = inspect_original_guard_preview(
        receipt, raws, expected_revenue=revenue)
    supplementary = evaluate_ticker_a_c(receipt, raws)
    return receipt, revenue, original, supplementary


class LocalReportTests(unittest.TestCase):
    def test_report_digest_reproduces_and_discloses_only_local_limitations(self):
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("REAL SEC HTTP")) as net:
            evidence = source_case()
            report = make_local_report(*evidence)
            raw = report_json_bytes(report)
        net.assert_not_called()
        self.assertEqual(report["verification"]["growth_pct"], "100.00")
        self.assertEqual(report["guard_policy_preview"], "HOLD")
        self.assertEqual(report["engine_a_status"], "UNAVAILABLE")
        self.assertEqual(report["engine_c_status"], "UNAVAILABLE")
        self.assertEqual(report["limits"]["external_http_requests"], 0)
        self.assertFalse(report["limits"]["audit_written"])
        self.assertFalse(report["limits"]["source_authenticated"])
        self.assertEqual(report, json.loads(raw))
        payload = dict(report)
        digest = payload.pop("report_sha256")
        canonical = (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False) + "\n").encode()
        self.assertEqual(digest, sha256(canonical).hexdigest())
        self.assertEqual(report, make_local_report(*evidence))
        self.assertNotIn("raw_sources", report)
        self.assertNotIn("user_agent", raw.decode())
        self.assertNotIn("<html", raw.decode())

    def test_forged_local_transport_rights_and_guard_fail_closed(self):
        receipt, revenue, original, ac = source_case()
        for attr, mutation in (
            ("receipt", {"http_requests_attempted": 4}),
            ("receipt", {"live_sec_http_called": True}),
            ("receipt", {"source_authenticated": True}),
            ("receipt", {"source_rights_verified": True}),
            ("receipt", {"source_sha256": {"original_10k": "0" * 64}}),
            ("revenue", {"guard_executed": True}),
            ("revenue", {"source_authenticated": True}),
            ("revenue", {"growth_pct": "999", "companyfacts_sha256": "0" * 64}),
            ("original", {"guard_executed": True}),
            ("original", {"source_authenticated": True}),
            ("ac", {"trade_executed": True}),
        ):
            with self.subTest(attr=attr, mutation=mutation):
                entries = list(map(deepcopy, (receipt, revenue, original, ac)))
                entries[{"receipt": 0, "revenue": 1,
                         "original": 2, "ac": 3}[attr]].update(mutation)
                with self.assertRaises(ValueError):
                    make_local_report(*entries)


if __name__ == "__main__":
    unittest.main()
