"""Real local 7-stage workflow -> A/B/C displayed scalar contract integration.

Uses established repository test fixtures, not synthetic snapshots of a report.
No network or issuer authentication claim.
"""
from __future__ import annotations

import os
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest.ticker_local_dashboard import (
    summarize_local_ticker_dashboard, render_local_ticker_dashboard,
)
from tests.test_ticker_market_industry_bridge import scenario
from tests.test_ticker_local_report_replay import report_case
from tests.test_ticker_research_ui import FakeSt, Uploaded
from proofinvest import ticker_research_ui as ui


class LiveLocalPipelineDashboardTests(unittest.TestCase):
    def test_actual_seven_stage_abc_replay_to_visible_metrics(self):
        _, raw, market, industry = scenario()
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("SEC NETWORK FORBIDDEN")) as net:
            workflow = run_local_ticker_workflow(
                ticker="NVDA", as_of="2026-02-01", sources=raw,
                market_json=json.dumps(market).encode("utf-8"),
                industry_json=json.dumps(industry).encode("utf-8"),
            )
            dashboard = summarize_local_ticker_dashboard(workflow)
            st = FakeSt()
            render_local_ticker_dashboard(st, workflow)
        net.assert_not_called()
        self.assertEqual(workflow["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(dashboard["status"], "LOCAL_SOURCE_REPLAYED_UNVERIFIED",
                         dashboard)
        self.assertEqual(dashboard["engine_a"]["status"], "REPORTED_UNVERIFIED")
        self.assertEqual(dashboard["engine_c"]["status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertEqual(dashboard["engine_c"]["growth_gap_to_industry_pp"], "80.00")
        self.assertEqual(dashboard["guard_policy"], "HOLD")
        self.assertTrue(any(kind == "metric" for kind, _ in st.messages))
        self.assertFalse(dashboard["source_authenticated"])
        self.assertFalse(dashboard["source_rights_verified"])
        self.assertFalse(dashboard["trade_executed"])

    def test_actual_source_replay_with_missing_optional_market_industry(self):
        _, raw = report_case()
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("SEC NETWORK FORBIDDEN")) as net:
            workflow = run_local_ticker_workflow(
                ticker="NVDA", as_of="2025-10-16", sources=raw)
            dashboard = summarize_local_ticker_dashboard(workflow)
        net.assert_not_called()
        self.assertEqual(workflow["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertEqual(dashboard["status"], "LOCAL_SOURCE_REPLAYED_UNVERIFIED",
                         dashboard)
        self.assertEqual(dashboard["engine_a"]["status"], "UNAVAILABLE")
        self.assertIsNone(dashboard["engine_a"]["beta"])
        self.assertIsNone(dashboard["engine_c"]["peer_median_growth_pct"])


    def test_real_ticker_ui_click_displays_abc_metrics_after_offline_replay(self):
        _, raw, market, industry = scenario()
        uploads = {
            "kuodra_p100_ticker_map": Uploaded(raw["ticker_map"]),
            "kuodra_p100_submissions": Uploaded(raw["submissions"]),
            "kuodra_p116_companyfacts": Uploaded(raw["companyfacts"]),
            "kuodra_p116_original": Uploaded(raw["original_10k"]),
            "kuodra_p104_market_json": Uploaded(json.dumps(market).encode("utf-8")),
            "kuodra_p104_industry_json": Uploaded(json.dumps(industry).encode("utf-8")),
        }
        st = FakeSt(
            clicked="로컬 원본으로 출처 계획 확인",
            values={"kuodra_p100_ticker": "NVDA",
                    "kuodra_p100_as_of": "2026-02-01"},
            uploads=uploads,
        )
        with (
            patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
            patch.object(transport, "_open_once",
                         side_effect=AssertionError("SEC NETWORK FORBIDDEN")) as net,
        ):
            ui.render_single_ticker_search(st)
        net.assert_not_called()
        metrics = [value for kind, value in st.messages if kind == "metric"]
        self.assertTrue(any(label == "OLS 베타 (인과관계 아님)"
                            and value != "자료 없음"
                            for label, value in metrics),
                        st.messages)
        self.assertTrue(any(label == "산업 대비 성장률 격차"
                            and value == "80.00pp"
                            for label, value in metrics),
                        st.messages)
        self.assertFalse(any(kind == "error" for kind, _ in st.messages))


if __name__ == "__main__":
    unittest.main()
