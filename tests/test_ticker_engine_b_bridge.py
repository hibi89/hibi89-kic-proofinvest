"""P124 binds existing Engine B to the same locally uploaded 10-K."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_engine_b_bridge import inspect_ticker_engine_b
from proofinvest.ticker_local_sources import prepare_local_ticker_sources
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest.ticker_local_report import verify_local_report
from tests.test_ticker_local_report_replay import report_case, _reseal


def source_with_accounting_facts():
    _, raw = report_case()
    doc = json.loads(raw["companyfacts"])
    gaap = doc["facts"]["us-gaap"]
    a = "0001045810-25-000020"
    common = {"accn": a, "form": "10-K", "filed": "2025-10-15"}
    def annual(value):
        return dict(common, start="2024-10-01", end="2025-09-30", val=value)
    def instant(value, end):
        return dict(common, end=end, val=value)
    for name, value in (
        ("NetIncomeLoss", 60),
        ("NetCashProvidedByUsedInOperatingActivities", 20),
        ("OperatingIncomeLoss", 80),
    ):
        gaap[name] = {"units": {"USD": [annual(value)]}}
    for name, now, old in (
        ("AccountsReceivableNetCurrent", 90, 20),
        ("InventoryNet", 60, 40),
    ):
        gaap[name] = {"units": {"USD": [
            instant(now, "2025-09-30"), instant(old, "2024-09-30"),
        ]}}
    return dict(raw, companyfacts=json.dumps(doc, sort_keys=True).encode())


class SameTickerEngineBTests(unittest.TestCase):
    def test_positive_earnings_cash_gap_and_receivables_are_source_bound(self):
        sources = source_with_accounting_facts()
        receipt = prepare_local_ticker_sources(
            ticker="NVDA", as_of="2025-10-16", sources=sources)
        revenue = inspect_collected_annual_revenue(receipt, sources)
        original = inspect_original_guard_preview(
            receipt, sources, expected_revenue=revenue)
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("NO SEC HTTP")) as network:
            b = inspect_ticker_engine_b(
                receipt, sources, expected_revenue=revenue,
                expected_original=original)
        network.assert_not_called()
        self.assertEqual(b["status"], "REVIEWED_UNVERIFIED", b)
        self.assertEqual(b["net_income_usd"], "60")
        self.assertEqual(b["operating_cashflow_usd"], "20")
        self.assertEqual(b["cash_to_net_income_pct"], "33.33")
        self.assertEqual(b["earnings_cash_signal"], "CFO_BELOW_POSITIVE_EARNINGS")
        self.assertEqual(b["receivables_minus_revenue_growth_pp"], "250.00")
        self.assertIn("RECEIVABLES_OUTPACED_REVENUE",
                      b["working_capital_signals"])
        self.assertFalse(b["accounting_fraud_proven"])
        self.assertFalse(b["source_authenticated"])
        self.assertFalse(b["source_rights_verified"])
        self.assertFalse(b["guard_executed"])
        self.assertEqual(b["external_http_requests"], 0)

    def test_real_workflow_and_report_replay_with_engine_b(self):
        raw = source_with_accounting_facts()
        original = deepcopy(raw)
        workflow = run_local_ticker_workflow(
            ticker="NVDA", as_of="2025-10-16", sources=raw)
        self.assertEqual(workflow["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(workflow["engine_b"]["status"], "REVIEWED_UNVERIFIED")
        self.assertEqual(workflow["tool_calls_executed"], 7)
        self.assertEqual(workflow["report"]["engine_b"]["cash_to_net_income_pct"],
                         "33.33")
        self.assertEqual(workflow["report"]["guard_policy_preview"], "HOLD")
        self.assertEqual(verify_local_report(
            workflow["report"], sources=raw)["status"], "PASS")
        self.assertEqual(raw, original)

    def test_missing_cash_flow_is_not_determined_healthy(self):
        _, raw = report_case()
        wf = run_local_ticker_workflow(
            ticker="NVDA", as_of="2025-10-16", sources=raw)
        self.assertEqual(wf["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(wf["engine_b"]["status"], "UNAVAILABLE")
        self.assertIsNone(wf["engine_b"]["cash_to_net_income_pct"])
        self.assertEqual(wf["engine_b"]["working_capital_signals"], [])
        self.assertEqual(wf["report"]["engine_b"]["status"], "UNAVAILABLE")
        self.assertEqual(verify_local_report(
            wf["report"], sources=raw)["status"], "PASS")

    def test_rehashed_accounting_flag_and_numbers_cannot_be_accepted(self):
        raw = source_with_accounting_facts()
        wf = run_local_ticker_workflow(
            ticker="NVDA", as_of="2025-10-16", sources=raw)
        for path, value in (
            ("cash_to_net_income_pct", "9999.99"),
            ("status", "UNAVAILABLE"),
            ("accounting_fraud_proven", True),
            ("source_authenticated", True),
        ):
            with self.subTest(field=path):
                forged = deepcopy(wf["report"])
                forged["engine_b"][path] = value
                _reseal(forged)
                self.assertEqual(
                    verify_local_report(forged, sources=raw)["status"], "FAIL")

    def test_changed_raw_facts_or_future_cashflow_cannot_verify(self):
        raw = source_with_accounting_facts()
        wf = run_local_ticker_workflow(
            ticker="NVDA", as_of="2025-10-16", sources=raw)
        changed = dict(raw, companyfacts=raw["companyfacts"] + b" ")
        self.assertEqual(
            verify_local_report(wf["report"], sources=changed)["status"],
            "FAIL")
        facts = json.loads(raw["companyfacts"])
        facts["facts"]["us-gaap"][
            "NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"][0][
                "filed"] = "2025-11-01"
        unavailable = run_local_ticker_workflow(
            ticker="NVDA", as_of="2025-10-16",
            sources=dict(raw, companyfacts=json.dumps(facts).encode()))
        self.assertEqual(unavailable["engine_b"]["status"], "UNAVAILABLE")
        self.assertEqual(unavailable["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertFalse(unavailable["report"]["limits"]["source_authenticated"])

    def test_legacy_report_without_engine_b_can_still_be_replayed(self):
        old, raw = report_case()
        self.assertNotIn("engine_b", old)
        self.assertEqual(verify_local_report(old, sources=raw)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
