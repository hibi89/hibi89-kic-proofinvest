"""P139: fail-closed single-ticker A/B/C dashboard tests, offline synthetic only."""
from __future__ import annotations

from copy import deepcopy
from unittest import TestCase, main

from proofinvest.ticker_local_dashboard import (
    render_local_ticker_dashboard, summarize_local_ticker_dashboard,
)

SHA = "a" * 64
REPORT = "b" * 64


def reviewed_workflow():
    issuer = {"ticker": "NVDA", "cik": "0001045810",
              "accession": "0001045810-25-000020", "as_of": "2026-02-01"}
    return {
        "schema": "kuodra.local-ticker-workflow.v1",
        "mode": "DETERMINISTIC_LOCAL_TOOLS_NOT_LLM_AGENT",
        "status": "READY_FOR_HUMAN_REVIEW_UNVERIFIED",
        "tool_budget": 7, "tool_calls_executed": 7,
        "tool_trace": [{"step": i} for i in range(7)],
        "source_authenticated": False, "source_rights_verified": False,
        "guard_executed": False, "audit_written": False,
        "human_approved": False, "trade_executed": False,
        "ai_agent_executed": False, "official_contest_submission": False,
        "network_requests": 0,
        "receipt": {"ticker": "NVDA", "cik": "0001045810",
                    "selected_10k_accession": "0001045810-25-000020",
                    "requested_as_of": "2026-02-01",
                    "source_sha256": {"companyfacts": SHA, "original_10k": "c" * 64}},
        "revenue": {"ticker": "NVDA", "issuer_cik": "0001045810",
                    "accession": "0001045810-25-000020", "status": "REVENUE_CALCULATED_UNVERIFIED",
                    "companyfacts_sha256": SHA, "growth_pct": "100.00"},
        "original": {"guard_preview": {"decision": "HOLD"},
                     "companyfacts_sha256": SHA},
        "supplementary": {"source_authenticated": False, "source_rights_verified": False,
            "engine_a": {"status": "REPORTED_UNVERIFIED", "input_sha256": "d" * 64,
                         "source_authenticated": False, "provider_rights_verified": False,
                         "security_return_pct": "12.50", "benchmark_return_pct": "8.00",
                         "beta": "1.10", "r_squared": "0.25"},
            "engine_c": {"status": "OBSERVED_COMPARISON_UNVERIFIED",
                         "peer_count": 1,
                         "cohort_source_scope": "DISJOINT_SOURCE_CLAIMS_ONLY_UNVERIFIED",
                         "input_sha256": "e" * 64, "source_authenticated": False,
                         "provider_rights_verified": False,
                         "peer_median_growth_pct": "15.00",
                         "growth_gap_to_industry_pp": "80.00"}},
        "engine_b": {"status": "REVIEWED_UNVERIFIED", "companyfacts_sha256": SHA,
                     "source_authenticated": False, "source_rights_verified": False,
                     "cash_to_net_income_pct": "95.00"},
        "report": {"issuer": issuer, "source_sha256": {"companyfacts": SHA, "original_10k": "c" * 64},
                   "report_sha256": REPORT, "verification": {"growth_pct": "100.00"},
                   "guard_policy_preview": "HOLD", "engine_a_status": "REPORTED_UNVERIFIED",
                   "engine_c_status": "OBSERVED_COMPARISON_UNVERIFIED",
                   "engine_a_input_sha256": "d" * 64, "engine_c_input_sha256": "e" * 64,
                   "source_rights_ledger": {
                        "status": "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED",
                        "external_sharing_allowed": False,
                        "commercial_reuse_allowed": False},
                   "limits": {"source_authenticated": False, "source_rights_verified": False,
                              "ai_agent_executed": False, "guard_executed": False,
                              "audit_written": False, "human_approved": False,
                              "trade_executed": False, "official_contest_submission": False,
                              "external_http_requests": 0}},
    }


class FakeStreamlit:
    def __init__(self):
        self.events = []
    def subheader(self, value): self.events.append(("subheader", value))
    def metric(self, *args): self.events.append(("metric", args))
    def json(self, value): self.events.append(("json", value))
    def warning(self, value): self.events.append(("warning", value))
    def code(self, value, **_): self.events.append(("code", value))


class DashboardUnitTests(TestCase):
    def test_three_engines_render_actual_bounded_values(self):
        workflow = reviewed_workflow()
        result = summarize_local_ticker_dashboard(workflow)
        self.assertEqual(result["status"], "LOCAL_SOURCE_REPLAYED_UNVERIFIED")
        self.assertEqual(result["engine_a"]["beta"], "1.10")
        self.assertEqual(result["engine_b"]["cash_to_net_income_pct"], "95.00")
        self.assertEqual(result["engine_c"]["growth_gap_to_industry_pp"], "80.00")
        self.assertEqual(result["engine_c"]["peer_count"], 1)
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["investment_recommendation"])
        st = FakeStreamlit()
        render_local_ticker_dashboard(st, workflow)
        self.assertIn(("metric", ("OLS 베타 (인과관계 아님)", "1.10")), st.events)
        self.assertIn(("metric", ("입력 동종기업 표본 수", "1")), st.events)
        self.assertTrue(any(k == "warning" and "표본이 1개뿐" in v for k, v in st.events))
        self.assertFalse(any(k == "code" for k, _ in st.events))

    def test_missing_market_industry_are_unavailable_not_zero(self):
        w = reviewed_workflow()
        for name in ("a", "c"):
            w["supplementary"]["engine_" + name] = {
                "status": "UNAVAILABLE", "input_sha256": None,
                "source_authenticated": False, "provider_rights_verified": False}
            w["report"]["engine_" + name + "_status"] = "UNAVAILABLE"
            w["report"]["engine_" + name + "_input_sha256"] = None
        result = summarize_local_ticker_dashboard(w)
        self.assertEqual(result["status"], "LOCAL_SOURCE_REPLAYED_UNVERIFIED")
        self.assertIsNone(result["engine_a"]["beta"])
        self.assertIsNone(result["engine_c"]["peer_median_growth_pct"])
        st = FakeStreamlit()
        render_local_ticker_dashboard(st, w)
        self.assertTrue(any(k == "metric" and "자료 없음" in v for k, v in st.events))

    def test_guard_reject_blocks_all_numeric_metrics(self):
        w = reviewed_workflow()
        w["original"]["guard_preview"]["decision"] = "REJECT"
        w["report"]["guard_policy_preview"] = "REJECT"
        result = summarize_local_ticker_dashboard(w)
        self.assertEqual(result["reason_code"], "GUARD_REJECTS_ORIGINAL_CONTEXT")
        st = FakeStreamlit()
        render_local_ticker_dashboard(st, w)
        self.assertFalse(any(k == "metric" for k, _ in st.events))

    def test_fake_rights_source_or_guard_is_blocked(self):
        for route in ("rights", "receipt", "guard", "engine_b", "report", "ticker", "trace"):
            w = reviewed_workflow()
            if route == "rights": w["report"]["source_rights_ledger"]["external_sharing_allowed"] = True
            if route == "receipt": w["receipt"]["source_sha256"]["companyfacts"] = "0" * 64
            if route == "guard": w["guard_executed"] = True
            if route == "engine_b": w["engine_b"]["source_authenticated"] = True
            if route == "report": w["report"]["report_sha256"] = "invalid"
            if route == "ticker": w["report"]["issuer"]["ticker"] = "<script>"
            if route == "trace": w["tool_calls_executed"] = 3
            with self.subTest(route=route):
                self.assertEqual(summarize_local_ticker_dashboard(w)["status"], "BLOCKED")

    def test_market_rights_or_digest_tamper_blocks(self):
        for key, val in (("provider_rights_verified", True),
                         ("input_sha256", "0" * 64),
                         ("beta", "NaN")):
            w = reviewed_workflow()
            w["supplementary"]["engine_a"][key] = val
            with self.subTest(key=key):
                out = summarize_local_ticker_dashboard(w)
                if key == "beta":
                    self.assertEqual(out["status"], "LOCAL_SOURCE_REPLAYED_UNVERIFIED")
                    self.assertIsNone(out["engine_a"]["beta"])
                else:
                    self.assertEqual(out["status"], "BLOCKED")

    def test_invalid_peer_sample_count_or_source_scope_blocks_metrics(self):
        for key, bad in (
            ("peer_count", -1), ("peer_count", 9),
            ("peer_count", "1"), ("cohort_source_scope", "VERIFIED"),
        ):
            workflow = reviewed_workflow()
            workflow["supplementary"]["engine_c"][key] = bad
            with self.subTest(key=key, bad=bad):
                result = summarize_local_ticker_dashboard(workflow)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason_code"],
                                 "ENGINE_C_PEER_COHORT_CONTRACT_INVALID")

    def test_bad_structures_fail_closed_not_crash(self):
        for value in (None, {}, "wrong", reviewed_workflow() | {"tool_trace": None},
                      reviewed_workflow() | {"receipt": {"source_sha256": "bad"}},
                      reviewed_workflow() | {"original": {"guard_preview": "bad"}}):
            with self.subTest(type=type(value)):
                self.assertEqual(summarize_local_ticker_dashboard(value)["status"], "BLOCKED")


if __name__ == "__main__":
    main()
