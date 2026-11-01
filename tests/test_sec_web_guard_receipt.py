"""P87 deterministic reviewer download of the offline, unauthenticated SEC WEB demo."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.sec_web_claim_guard_demo import review_manual_web_growth_claim
from proofinvest.sec_web_claim_guard_ui import export_manual_web_guard_receipt


class ManualWebGuardReceiptTests(unittest.TestCase):
    def test_custom_conflict_receipt_has_numeric_provenance_limits(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_REMOTE")) as http:
            result = review_manual_web_growth_claim("8.25")
            receipt = export_manual_web_guard_receipt(result, "8.25")
        http.assert_not_called()
        self.assertLessEqual(len(receipt), 4096)
        self.assertEqual(receipt, export_manual_web_guard_receipt(result, "8.25"))
        data = json.loads(receipt)
        self.assertEqual(data["schema"], "kuodra.manual-sec-web-guard-receipt.v1")
        self.assertEqual(data["numeric_check"]["claim_minus_manual_percentage_points"], "1.82")
        self.assertEqual(data["numeric_check"]["numeric_verdict"], "CONFLICT")
        self.assertEqual(data["simulated_guard"]["decision"], "REJECT")
        self.assertEqual(data["source"]["manual_cells_checked"], 28)
        self.assertEqual(data["status"], "OFFLINE_DEMO_ONLY_ORIGINAL_UNVERIFIED")
        self.assertTrue(data["not_investment_advice"])
        self.assertTrue(all(value is False for value in data["limits"].values()))
        self.assertNotIn("original_filing", data)
        self.assertNotIn("audit_db", data)

    def test_matching_and_unavailable_safely_remain_hold(self):
        for claim, expected in (("6.43", "VERIFIED"), (None, "UNAVAILABLE")):
            with self.subTest(claim=claim):
                data = json.loads(export_manual_web_guard_receipt(
                    review_manual_web_growth_claim(claim), claim
                ))
                self.assertEqual(data["numeric_check"]["numeric_verdict"], expected)
                self.assertEqual(data["simulated_guard"]["decision"], "HOLD")
                self.assertIs(data["simulated_guard"]["human_approved"], False)
                self.assertIs(data["source"]["issuer_original_authenticated"], False)

    def test_forged_source_guard_and_numeric_receipts_blocked(self):
        baseline = review_manual_web_growth_claim("8.25")
        for section, field, value in (
            ("top", "source_authenticated", True),
            ("top", "numeric_verdict", "VERIFIED"),
            ("guard", "decision", "APPROVE"),
            ("guard", "human_approved", True),
            ("top", "claim_minus_manual_web_pp", "0.00"),
        ):
            with self.subTest(section=section, field=field):
                forged = deepcopy(baseline)
                target = forged if section == "top" else forged["guard"]
                target[field] = value
                with self.assertRaises(ValueError):
                    export_manual_web_guard_receipt(forged, "8.25")

    def test_invalid_input_cannot_export_and_no_network(self):
        for claim in ("NaN", "1000", "1e2", "8<script>", "8.250"):
            with self.subTest(claim=claim):
                with patch("urllib.request.urlopen", side_effect=AssertionError("NO_REMOTE")) as http:
                    with self.assertRaises(ValueError):
                        export_manual_web_guard_receipt({}, claim)
                http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
