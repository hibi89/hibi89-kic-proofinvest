"""Fail-closed manual primary-source arithmetic at extreme Decimal magnitudes."""
import copy
import json
import unittest

from proofinvest.evidence_scenarios import EVIDENCE_PATH, three_scenarios, verify_growth_claim
from proofinvest.evidence_chain import evaluate_offline_chain


def extreme_evidence():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence["current"]["amount"] = "9" * 80
    # Existing stored delta and percent deliberately remain pinned to the
    # true issuer report: this must never be treated as verified evidence.
    return evidence


class ManualEvidenceExtremeDecimalTests(unittest.TestCase):
    def test_extreme_amount_withheld_without_uncaught_decimal_exception(self):
        value = verify_growth_claim(extreme_evidence(), "16.20")
        self.assertEqual(value["state"], "unavailable")
        self.assertIsNone(value["source_url"])
        self.assertIsNone(value["computed_pct"])
        self.assertIn("unrepresentable revenue growth", value["reason"])
        self.assertIs(value["dart_viewer_verified"], False)

    def test_three_scenarios_do_not_crash_or_fabricate_verification(self):
        scenarios = three_scenarios(extreme_evidence())["scenarios"]
        self.assertEqual(
            {name: record["state"] for name, record in scenarios.items()},
            {name: "unavailable" for name in scenarios},
        )

    def test_chain_risk_stays_withheld_on_extreme_manual_amount(self):
        research = {
            "target_name": "Synthetic Test", "target_id": "00126380",
            "as_of": "2026-10-24",
            "sources": [{"id": "S1", "title": "Manual review test",
                "url": "https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2025_SEC_Consolidated_Financial_statements.pdf",
                "published_at": "2025-03-11", "collected_at": "2026-10-24",
                "license": "not_verified"}],
            "findings": [{"claim": "A supplied manual statement was reviewed",
                "source_ids": ["S1"], "as_of": "2026-10-24"}],
        }
        saved = copy.deepcopy(research)
        result = evaluate_offline_chain(
            research_request=research,
            financial_evidence=extreme_evidence(),
            claimed_growth_pct="16.20",
        )
        self.assertEqual(research, saved)
        self.assertEqual(result["verification"]["state"], "unavailable")
        self.assertFalse(result["trace_linked"])
        self.assertFalse(result["risk"]["risk_calculated"])
        self.assertIsNone(result["risk"]["ratio_pct"])
        self.assertFalse(result["authenticated_external_source"])


if __name__ == "__main__":
    unittest.main()
