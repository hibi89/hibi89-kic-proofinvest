"""No-HTTP tests for compact offline evidence summaries."""
import unittest

from proofinvest.offline_review_summary import build_offline_review_summary


def receipt():
    return {
        "status": "offline_capture_replayed_unverified",
        "source_authenticated": False,
        "financial_values_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
        "external_http_called": False,
        "offline_financial_review": {"status": "calculated_unverified"},
        "risk": {"status": "reviewed_unverified"},
        "human_review_triage": {
            "status": "offline_evidence_ready_for_human_review",
            "priority": "normal",
            "reason_codes": ["EXTERNAL_SOURCE_AUTHENTICITY_UNVERIFIED"],
            "source_authenticated": False,
            "financial_values_authenticated": False,
            "investment_recommendation": False,
            "trade_authorized": False,
            "external_http_called": False,
        },
    }


class ReviewSummaryTests(unittest.TestCase):
    def test_normal_remains_human_review(self):
        result = build_offline_review_summary(receipt())
        self.assertEqual(result["status"], "human_review_required")
        self.assertEqual(result["review_priority"], "normal")
        self.assertFalse(result["investment_recommendation"])
        self.assertIn("VERIFY_PROVIDER_ORIGIN_AND_RIGHTS", result["review_actions"])
        self.assertIn("INSPECT_IXBRL_CONTEXT_AND_UNITS", result["review_actions"])

    def test_conflicting_financial_claim_requests_reconciliation(self):
        data = receipt()
        data["offline_financial_review"]["status"] = "conflict"
        data["risk"]["status"] = "unavailable"
        data["human_review_triage"]["status"] = "manual_review_required"
        data["human_review_triage"]["priority"] = "high"
        result = build_offline_review_summary(data)
        self.assertIn("RECONCILE_FINANCIAL_CLAIM", result["review_actions"])
        self.assertIn("REVIEW_LOCAL_RISK_FLAGS", result["review_actions"])

    def test_forged_attestation_is_blocked(self):
        for section, key in (("human_review_triage", "financial_values_authenticated"),
                             ("human_review_triage", "investment_recommendation"),
                             (None, "official_contest_submission")):
            with self.subTest(section=section, key=key):
                data = receipt()
                target = data if section is None else data[section]
                target[key] = True
                self.assertEqual(build_offline_review_summary(data)["status"], "blocked")

    def test_malformed_status_does_not_raise(self):
        for section in ("offline_financial_review", "risk"):
            with self.subTest(section=section):
                data = receipt()
                data[section]["status"] = []
                self.assertEqual(build_offline_review_summary(data)["status"], "blocked")

    def test_priority_cannot_be_downgraded_with_conflict(self):
        data = receipt()
        data["offline_financial_review"]["status"] = "conflict"
        result = build_offline_review_summary(data)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("INCONSISTENT_REVIEW_PRIORITY", result["reason_codes"])

    def test_failure_reason_allowlist(self):
        result = build_offline_review_summary({"status": "unavailable", "reason_code": "REPLAY_DIGEST_CONFLICT"})
        self.assertEqual(result["reason_codes"], ["REPLAY_DIGEST_CONFLICT"])
        result = build_offline_review_summary({"status": "unavailable", "reason_code": "OTHER"})
        self.assertEqual(result["reason_codes"], ["REPLAY_UNAVAILABLE"])

    def test_unknown_reason_text_never_leaks(self):
        data = receipt()
        data["human_review_triage"]["reason_codes"] = ["secret private text"]
        self.assertEqual(build_offline_review_summary(data)["reason_codes"], [])


if __name__ == "__main__":
    unittest.main()
