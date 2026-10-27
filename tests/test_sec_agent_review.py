"""SEC post-verification decision tests; no network or external data."""
import copy
import unittest

from proofinvest.sec_agent_review import review_sec_verdict

_BASE = {
    "schema": "proofinvest.sec-companyfacts-offline.v1",
    "status": "calculated_unverified",
    "reason_code": "STRUCTURAL_NUMERIC_COMPARISON_ONLY",
    "source_kind": "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED",
    "live_api_called": True, "http_request_attempted": True,
    "authenticated_external_source": False, "source_rights_verified": False,
    "ai_agent_executed": False, "official_contest_submission": False,
    "risk_calculated": False, "growth_pct": "6.43",
    "current_usd": "416161000000", "prior_usd": "391035000000",
}


class SecPostVerificationTests(unittest.TestCase):
    def test_structural_success_requires_human_authentication(self):
        r = review_sec_verdict(_BASE)
        self.assertEqual(r["status"], "needs_authentication")
        self.assertEqual(r["reason_code"], "SEC_STRUCTURAL_RESULT_ONLY")
        self.assertEqual(r["next_action"], "INDEPENDENT_SEC_SOURCE_AND_RIGHTS_REVIEW")
        self.assertEqual([t["step"] for t in r["trace"]],
                         ["PLAN", "EVALUATE", "DECIDE", "REPORT"])
        self.assertEqual(r["external_tool_calls"], 0)
        self.assertFalse(r["ai_agent_executed"])

    def test_conflict_blocks_regardless_of_live_transport(self):
        r = review_sec_verdict(_BASE | {
            "status": "conflict", "reason_code": "GROWTH_CLAIM_CONFLICT",
        })
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["reason_code"], "SEC_GROWTH_CLAIM_CONFLICT")

    def test_filed_after_as_of_and_missing_annual_facts_are_human_holds(self):
        for reason in ("FILING_AFTER_AS_OF", "ANNUAL_FACTS_UNAVAILABLE"):
            with self.subTest(reason=reason):
                payload = _BASE | {
                    "status": "unavailable", "reason_code": reason,
                    "growth_pct": None, "current_usd": None,
                    "prior_usd": None, "sec_filing_index": None,
                }
                verdict = review_sec_verdict(payload)
                self.assertEqual(verdict["status"], "blocked")
                self.assertEqual(verdict["reason_code"], "SEC_VERIFICATION_UNAVAILABLE")
                self.assertEqual(verdict["next_action"], "REVIEW_FILING_DATE_PERIOD_OR_SOURCE")
                self.assertEqual(verdict["external_tool_calls"], 0)

    def test_verifier_hold_rejects_fabricated_or_residual_numbers(self):
        base = _BASE | {
            "status": "unavailable", "reason_code": "FILING_AFTER_AS_OF",
            "growth_pct": None, "current_usd": None,
            "prior_usd": None, "sec_filing_index": None,
        }
        for invalid in (
            {"reason_code": "CLAIM_UNVERIFIED_BY_MAGIC"},
            {"reason_code": []},
            {"reason_code": {"unsafe": "object"}},
            {"growth_pct": "6.43"}, {"current_usd": "1"},
            {"sec_filing_index": "https://sec.example/claimed"},
            {"source_kind": "CALLER_SUPPLIED_SEC_FORMAT_NOT_AUTHENTICATED"},
            {"http_request_attempted": False},
            {"authenticated_external_source": True},
        ):
            with self.subTest(invalid=invalid):
                verdict = review_sec_verdict(base | invalid)
                self.assertEqual(verdict["reason_code"], "UNTRUSTED_VERDICT_CONTRACT")
                self.assertFalse(verdict["ai_agent_executed"])

    def test_http_gate_failure_never_retries(self):
        r = review_sec_verdict({
            "schema": "proofinvest.sec-concept-http-gate.v1",
            "status": "unavailable", "reason_code": "SEC_NETWORK_OR_HTTP_ERROR",
            "source_kind": "SEC_API_NETWORK_ATTEMPT_NOT_FACT_CERTIFICATION",
            "live_api_called": True, "http_request_attempted": True,
            "authenticated_external_source": False,
            "source_rights_verified": False, "ai_agent_executed": False,
            "official_contest_submission": False, "growth_pct": None,
        })
        self.assertEqual(r["reason_code"], "SEC_EVIDENCE_UNAVAILABLE")
        self.assertTrue(r["upstream_http_request_attempted"])
        self.assertEqual(r["external_tool_calls"], 0)

    def test_no_opt_in_failure_has_zero_upstream_http(self):
        v = {
            "schema": "proofinvest.sec-concept-http-gate.v1",
            "status": "unavailable", "reason_code": "NETWORK_OPT_IN_REQUIRED",
            "source_kind": "SEC_API_NETWORK_ATTEMPT_NOT_FACT_CERTIFICATION",
            "live_api_called": False, "http_request_attempted": False,
            "authenticated_external_source": False,
            "source_rights_verified": False, "ai_agent_executed": False,
            "official_contest_submission": False, "growth_pct": None,
        }
        r = review_sec_verdict(v)
        self.assertEqual(r["reason_code"], "SEC_EVIDENCE_UNAVAILABLE")
        self.assertFalse(r["upstream_http_request_attempted"])

    def test_forged_attestation_flags_fail_closed(self):
        for change in (
            {"authenticated_external_source": True},
            {"ai_agent_executed": True}, {"source_rights_verified": True},
            {"official_contest_submission": True},
            {"live_api_called": False}, {"http_request_attempted": False},
        ):
            with self.subTest(change=change):
                r = review_sec_verdict(_BASE | change)
                self.assertEqual(r["reason_code"], "UNTRUSTED_VERDICT_CONTRACT")

    def test_bad_or_untrusted_payload_cannot_elevate(self):
        for payload in (
            None, {}, [], _BASE | {"schema": "untrusted"},
            _BASE | {"source_kind": "CALLER_ASSERTED_AUTHENTICATED"},
            _BASE | {"growth_pct": "NaN"}, _BASE | {"current_usd": "-5"},
            _BASE | {"risk_calculated": True},
        ):
            with self.subTest(payload=payload):
                r = review_sec_verdict(payload)
                self.assertEqual(r["status"], "blocked")

    def test_http_gate_rejects_spoofed_reason_and_residual_amounts(self):
        gate = _BASE | {
            "schema": "proofinvest.sec-concept-http-gate.v1",
            "source_kind": "SEC_API_NETWORK_ATTEMPT_NOT_FACT_CERTIFICATION",
            "status": "unavailable", "reason_code": "SEC_NETWORK_OR_HTTP_ERROR",
            "growth_pct": None, "current_usd": None, "prior_usd": None,
        }
        self.assertEqual(review_sec_verdict(gate)["reason_code"],
                         "SEC_EVIDENCE_UNAVAILABLE")
        for change in (
            {"reason_code": "FAKE_OFFICIAL_SUCCESS"},
            {"reason_code": []},
            {"reason_code": {"unsafe": "object"}},
            {"reason_code": "NETWORK_OPT_IN_REQUIRED"},
            {"current_usd": "123"},
            {"prior_usd": "456"},
            {"sec_filing_index": "https://sec.gov/forged"},
            {"http_request_attempted": False, "live_api_called": False},
        ):
            with self.subTest(change=change):
                self.assertEqual(
                    review_sec_verdict(gate | change)["reason_code"],
                    "UNTRUSTED_VERDICT_CONTRACT",
                )
        locally_blocked = gate | {
            "reason_code": "NETWORK_OPT_IN_REQUIRED",
            "http_request_attempted": False, "live_api_called": False,
        }
        self.assertEqual(review_sec_verdict(locally_blocked)["reason_code"],
                         "SEC_EVIDENCE_UNAVAILABLE")

    def test_calculated_and_conflict_reason_must_match_status(self):
        for payload in (
            _BASE | {"reason_code": "GROWTH_CLAIM_CONFLICT"},
            _BASE | {"reason_code": "MADE_UP_VERIFICATION"},
            _BASE | {"status": "conflict"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(
                    review_sec_verdict(payload)["reason_code"],
                    "UNTRUSTED_VERDICT_CONTRACT",
                )
        coherent = _BASE | {
            "status": "conflict", "reason_code": "GROWTH_CLAIM_CONFLICT",
        }
        self.assertEqual(review_sec_verdict(coherent)["reason_code"],
                         "SEC_GROWTH_CLAIM_CONFLICT")

    def test_deterministic_does_not_modify_inputs(self):
        obj = copy.deepcopy(_BASE)
        original = copy.deepcopy(obj)
        self.assertEqual(review_sec_verdict(obj), review_sec_verdict(obj))
        self.assertEqual(obj, original)

    def test_wrong_filing_shape_must_not_be_authenticated(self):
        obj = _BASE | {"status": "verified"}
        r = review_sec_verdict(obj)
        self.assertEqual(r["reason_code"], "UNTRUSTED_VERDICT_CONTRACT")
        self.assertFalse(r["authenticated_external_source"])


if __name__ == "__main__":
    unittest.main()
