"""Offline decision gate regression checks (no HTTP)."""
import unittest
from proofinvest.offline_evidence_triage import triage_offline_replay


def valid_replay():
    return {
        "status": "offline_capture_replayed_unverified",
        "source_authenticated": False,
        "financial_values_authenticated": False,
        "source_rights_verified": False,
        "external_http_called": False,
        "official_contest_submission": False,
        "local_integrity": {"status": "bundle_integrity_pass_origin_unverified"},
        "offline_financial_review": {},
        "risk": {},
        "source_span": {},
    }


class OfflineEvidenceTriageTests(unittest.TestCase):
    def test_valid_replay_still_requires_human_review(self):
        result = triage_offline_replay(valid_replay())
        self.assertEqual(result["status"], "offline_evidence_ready_for_human_review")
        self.assertEqual(result["priority"], "normal")
        self.assertFalse(result["investment_recommendation"])
        self.assertFalse(result["trade_authorized"])

    def test_rejects_unavailable_or_non_object(self):
        for receipt in (None, [], {}, {"status": "unavailable"}):
            with self.subTest(receipt=receipt):
                self.assertEqual(triage_offline_replay(receipt)["priority"], "high")

    def test_rejects_trust_escalation_and_missing_attestations(self):
        for key in ("source_authenticated", "financial_values_authenticated",
                    "source_rights_verified", "external_http_called",
                    "official_contest_submission"):
            for value in (True, None):
                with self.subTest(key=key, value=value):
                    receipt = valid_replay()
                    receipt[key] = value
                    self.assertIn("TRUST_BOUNDARY_VIOLATION",
                                  triage_offline_replay(receipt)["reason_codes"])

    def test_rejects_missing_sections(self):
        for key in ("local_integrity", "offline_financial_review", "risk", "source_span"):
            with self.subTest(key=key):
                receipt = valid_replay()
                del receipt[key]
                self.assertEqual(triage_offline_replay(receipt)["priority"], "high")

    def test_rejects_bad_integrity_status(self):
        receipt = valid_replay()
        receipt["local_integrity"]["status"] = "failed"
        self.assertIn("BUNDLE_INTEGRITY_NOT_CONFIRMED",
                      triage_offline_replay(receipt)["reason_codes"])


if __name__ == "__main__":
    unittest.main()
