"""Bounded workflow's actual tool calls and fail-closed next decisions."""
import copy
import json
import subprocess
import sys
import unittest

from proofinvest.agent_controller import run_offline_controller, run_issuer_manual_demo
from proofinvest.manual_case_demo import make_research_request, read_reviewed_evidence


def samples():
    e = read_reviewed_evidence()
    r = make_research_request(e)
    request = {"issuer_id": "00126380", "report_year": 2024, "claimed_growth_pct": "16.20"}
    return request, r, e


def run(claim="16.20", risk=None, mutate=None):
    req, research, financial = samples()
    req["claimed_growth_pct"] = claim
    if mutate is not None:
        mutate(req, research, financial)
    return run_offline_controller(req, research_request=research,
                                  financial_evidence=financial, risk_facts=risk)


class RuleBasedControllerTests(unittest.TestCase):
    def test_matching_issuer_claim_requires_missing_risk_facts(self):
        result = run()
        self.assertEqual(result["status"], "needs_evidence")
        self.assertEqual(result["reason_code"], "RISK_FACTS_NOT_ELIGIBLE")
        self.assertEqual(result["next_action"], "OBTAIN_CITABLE_LIABILITIES_AND_EQUITY")
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertTrue(result["evidence_chain"]["trace_linked"])
        self.assertEqual(result["evidence_chain"]["verification"]["state"], "verified")
        self.assertFalse(result["evidence_chain"]["risk"]["risk_calculated"])

    def test_contradictory_growth_claim_stops_before_risk(self):
        result = run(claim="30")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason_code"], "GROWTH_CLAIM_CONFLICT")
        self.assertFalse(result["evidence_chain"]["risk"]["risk_calculated"])

    def test_missing_or_malformed_growth_claim_is_withheld(self):
        for claim in ("", "not-a-number", None):
            with self.subTest(claim=claim):
                result = run(claim=claim)
                self.assertEqual(result["reason_code"], "CLAIM_UNAVAILABLE")
                self.assertEqual(result["evidence_chain"]["verification"]["state"], "unavailable")

    def test_invalid_request_shape_skips_all_tools(self):
        for request in (None, [], {}, {"issuer_id": "INVALID", "report_year": 2024},
                        {"issuer_id": "00126380", "report_year": True}):
            with self.subTest(request=request):
                result = run_offline_controller(request)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["tool_calls"], [])
                self.assertIsNone(result["evidence_chain"])

    def test_different_request_issuer_or_year_cannot_reuse_matching_record(self):
        for key, value in (("issuer_id", "00000001"), ("report_year", 2025)):
            with self.subTest(key=key):
                result = run(mutate=lambda req, _r, _f: req.update({key: value}))
                self.assertEqual(result["reason_code"], "ISSUER_YEAR_MISMATCH")
                self.assertEqual(result["tool_calls"], [])

    def test_missing_financial_or_research_inputs_skip_tools(self):
        req, research, e = samples()
        for r, financial in ((None, e), (research, None), ({}, None)):
            with self.subTest(research=r, financial=financial):
                result = run_offline_controller(req, research_request=r, financial_evidence=financial)
                self.assertEqual(result["reason_code"], "EVIDENCE_UNAVAILABLE")
                self.assertEqual(result["tool_calls"], [])

    def test_unrelated_research_citation_blocks_claim(self):
        def changed(_req, research, _financial):
            research["sources"][0]["url"] = "https://example.org/other.pdf"
        result = run(mutate=changed)
        self.assertEqual(result["reason_code"], "UNLINKED_PROVENANCE")
        self.assertFalse(result["evidence_chain"]["trace_linked"])
        self.assertFalse(result["evidence_chain"]["risk"]["risk_calculated"])

    def test_self_reported_dart_authentication_never_trusted(self):
        req, r, e = samples()
        e["dart_filing"] = {"direct_viewer_verified": True}
        result = run_offline_controller(req, research_request=r, financial_evidence=e)
        self.assertFalse(result["authenticated_external_source"])
        self.assertFalse(result["evidence_chain"]["verification"]["dart_viewer_verified"])
        self.assertFalse(result["ai_agent_executed"])
        self.assertFalse(result["live_api_called"])
        self.assertFalse(result["official_contest_submission"])
        self.assertEqual(result["external_tool_calls"], 0)

    def test_even_structurally_calculated_risk_needs_real_authentication(self):
        req, r, e = samples()
        source = e["primary_source"]["url"]
        facts = [
            {"metric": metric, "current_amount": amount, "state": "verified",
             "year": 2024, "fs_div": "CFS", "unit": "KRW",
             "report_code": "11011", "period_end": "2024-12-31",
             "issuer_id": "00126380", "evidence_ref": "SYNTHETIC_USER_INPUT",
             "source_url": source, "source_kind": "MANUAL_PRIMARY_SOURCE_VERIFICATION"}
            for metric, amount in (("liabilities", "80"), ("equity", "30"))
        ]
        result = run_offline_controller(req, research_request=r,
                                        financial_evidence=e, risk_facts=facts)
        self.assertEqual(result["status"], "needs_authentication")
        self.assertEqual(result["reason_code"], "STRUCTURAL_RESULT_ONLY")
        self.assertEqual(result["evidence_chain"]["risk"]["status"], "calculated")
        self.assertFalse(result["authenticated_external_source"])
        self.assertEqual(result["next_action"], "INDEPENDENT_SOURCE_AND_RIGHTS_REVIEW")

    def test_wrong_or_missing_risk_evidence_causes_evidence_request_not_zero_score(self):
        req, r, e = samples()
        risk = [{"metric": "liabilities", "current_amount": "80", "issuer_id": "00126380"}]
        result = run_offline_controller(req, research_request=r,
                                        financial_evidence=e, risk_facts=risk)
        self.assertEqual(result["reason_code"], "RISK_FACTS_NOT_ELIGIBLE")
        self.assertIsNone(result["evidence_chain"]["risk"]["ratio_pct"])

    def test_bounded_deterministic_trace_and_input_unchanged(self):
        req, r, e = samples()
        originals = copy.deepcopy((req, r, e))
        first = run_offline_controller(req, research_request=r, financial_evidence=e)
        second = run_offline_controller(req, research_request=r, financial_evidence=e)
        self.assertEqual(first, second)
        self.assertEqual((req, r, e), originals)
        self.assertEqual([x["step"] for x in first["trace"]],
                         ["PLAN", "EVALUATE", "DECIDE", "REPORT"])
        self.assertEqual(first["tool_budget"], 1)
        self.assertEqual(first["external_tool_calls"], 0)
        self.assertEqual(first["tool_calls"][0]["tool"], "evaluate_offline_chain")

    def test_cli_uses_pinned_manual_case_and_never_claims_live_agent(self):
        for claim, expected in (("16.20", "RISK_FACTS_NOT_ELIGIBLE"),
                                ("30", "GROWTH_CLAIM_CONFLICT")):
            with self.subTest(claim=claim):
                proc = subprocess.run([sys.executable, "-m", "proofinvest.agent_controller",
                                      "--claim", claim],
                                      capture_output=True, text=True, check=True)
                result = json.loads(proc.stdout)
                self.assertEqual(result["reason_code"], expected)
                self.assertFalse(result["ai_agent_executed"])
                self.assertEqual(result["external_tool_calls"], 0)

    def test_manual_case_helper_does_not_write_or_fetch(self):
        from proofinvest.manual_case_demo import EVIDENCE_PATH
        original = EVIDENCE_PATH.read_bytes()
        result = run_issuer_manual_demo()
        self.assertEqual(EVIDENCE_PATH.read_bytes(), original)
        self.assertEqual(result["mode"], "RULE_BASED_OFFLINE_NOT_LLM_AGENT")
        self.assertEqual(result["evidence_chain"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
