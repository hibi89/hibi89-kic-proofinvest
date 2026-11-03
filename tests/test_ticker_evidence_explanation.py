"""P158 offline replay-to-deterministic-explanation integration tests."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import unittest

from proofinvest.ticker_evidence_explanation import (
    explain_linked_market_receipt, explanation_json_bytes,
)
from tests.test_ticker_market_pair_evidence import _build, _prepared


class TickerEvidenceExplanationTests(unittest.TestCase):
    def test_real_offline_a_b_c_receipt_produces_source_bound_notes(self):
        source = _build(_prepared())
        self.assertEqual(source["status"], "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED")
        result = explain_linked_market_receipt(source)
        self.assertEqual(result["status"],
                         "DETERMINISTIC_LOCAL_INTERPRETATION_UNVERIFIED")
        self.assertEqual(result["linked_evidence_sha256"], source["evidence_sha256"])
        self.assertEqual(result["source_hashes"]["companyfacts_sha256"],
                         source["engine_b"]["companyfacts_sha256"])
        self.assertEqual(result["source_hashes"]["index_response_sha256"],
                         source["premium_engine_a"]["index_response_sha256"])
        self.assertEqual([x["engine"] for x in result["findings"]], ["A", "B", "C"])
        market = source["premium_engine_a"]
        expected_gap = str((Decimal(market["security_return_pct"]) -
                            Decimal(market["benchmark_return_pct"]))
                           .quantize(Decimal("0.0001")))
        self.assertEqual(result["findings"][0]["simple_return_gap_pp"], expected_gap)
        self.assertEqual(result["findings"][0]["period_end"],
                         market["matched_period_end"])
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        for key in ("source_authenticated", "source_rights_verified",
                    "ai_agent_executed", "investment_recommendation",
                    "trade_executed", "external_sharing_allowed"):
            self.assertIs(result[key], False)
        data = explanation_json_bytes(result)
        self.assertEqual(json.loads(data)["explanation_sha256"],
                         result["explanation_sha256"])
        self.assertNotIn(b"close_observations", data)
        self.assertNotIn(b"apikey", data.lower())

    def test_reject_tampered_receipt_or_forged_source_rights(self):
        baseline = _build(_prepared())
        altered = deepcopy(baseline)
        altered["source_rights_verified"] = True
        with self.assertRaises(ValueError):
            explain_linked_market_receipt(altered)
        altered = deepcopy(baseline)
        altered["premium_engine_a"]["security_return_pct"] = "999999"
        with self.assertRaises(ValueError):
            explain_linked_market_receipt(altered)
        altered = deepcopy(baseline)
        altered["raw_secret"] = "SHOULD_NOT_BE_EXPORTED"
        with self.assertRaises(ValueError):
            explain_linked_market_receipt(altered)

    def test_explanation_export_refuses_checksum_tampering_and_extra_field(self):
        result = explain_linked_market_receipt(_build(_prepared()))
        changed = deepcopy(result)
        changed["findings"][0]["simple_return_gap_pp"] = "999"
        with self.assertRaisesRegex(ValueError, "CHECKSUM"):
            explanation_json_bytes(changed)
        changed = deepcopy(result)
        changed["external_secret"] = "SHOULD_NOT_BE_EXPORTED"
        unsigned = {k: v for k, v in changed.items() if k != "explanation_sha256"}
        changed["explanation_sha256"] = sha256(
            (json.dumps(unsigned, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), allow_nan=False) + "\n").encode()
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "CONTRACT"):
            explanation_json_bytes(changed)

    def test_no_available_market_comparison_is_not_labelled_investment_advice(self):
        original = _build(_prepared())
        result = explain_linked_market_receipt(original)
        self.assertNotIn("검증된 투자 추천", json.dumps(result, ensure_ascii=False))
        self.assertFalse(result["ai_agent_executed"])
        self.assertEqual(result["guard_policy_preview"], "HOLD")


if __name__ == "__main__":
    unittest.main()
