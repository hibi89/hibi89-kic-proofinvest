"""Boundaries for offline risk screening; no network or external data."""
import unittest

from proofinvest.local_risk_screen import screen_local_evidence


def evidence():
    return {"status": "calculated_unverified"}, {
        "original_sha256": "a" * 64,
        "start_byte": 0,
        "end_byte_exclusive": 5,
    }


class LocalRiskScreenTests(unittest.TestCase):
    def test_reviewable_is_not_authenticated_or_tradable(self):
        financial, source = evidence()
        result = screen_local_evidence(financial, source)
        self.assertEqual(result["status"], "reviewed_unverified")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["trade_authorized"])

    def test_financial_conflict_is_unavailable(self):
        financial, source = evidence()
        financial["status"] = "conflict"
        result = screen_local_evidence(financial, source)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("CLAIMED_GROWTH_CONFLICT", result["reason_codes"])

    def test_structural_corrobation_signals_are_not_authentication(self):
        financial, source = evidence()
        source["ixbrl_context"] = {"status": "local_ixbrl_revenue_context_match_unverified"}
        source["numeric_literals"] = {"status": "untrusted_numeric_literals_located"}
        result = screen_local_evidence(financial, source)
        self.assertIn("LOCAL_IXBRL_CONTEXT_MATCH_UNVERIFIED", result["reason_codes"])
        self.assertIn("LOCAL_NUMERIC_TEXT_MATCH_UNVERIFIED", result["reason_codes"])
        self.assertFalse(result["source_authenticated"])

    def test_bad_digests_fail_closed(self):
        for digest in ("x" * 64, "A" * 64, "a" * 63, None, 1):
            with self.subTest(digest=digest):
                financial, source = evidence()
                source["original_sha256"] = digest
                self.assertIn("SOURCE_DIGEST_MISSING",
                              screen_local_evidence(financial, source)["reason_codes"])

    def test_boolean_or_reversed_offsets_fail_closed(self):
        for start, end in ((True, 5), (0, True), (-1, 5), (5, 5), (6, 5)):
            with self.subTest(start=start, end=end):
                financial, source = evidence()
                source["start_byte"], source["end_byte_exclusive"] = start, end
                self.assertIn("SOURCE_SPAN_INVALID",
                              screen_local_evidence(financial, source)["reason_codes"])


if __name__ == "__main__":
    unittest.main()
