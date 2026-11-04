"""P185 exact local numeric model proposal validation, no network."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_model_numeric_claim import (
    verify_local_model_numeric_claim, _SCHEMA, _CLAIM,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload


class LocalModelNumericClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receipt = build_offline_initial_review(**payload())
        assert receipt["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
        cls.review = receipt["review_packet"]
        cls.rights = receipt["source_clearance_report"]
        packet = json.loads(cls.review)
        cls.valid = {
            "schema": _SCHEMA,
            "engine": "A",
            "claim_kind": _CLAIM,
            "gap_pp": packet["explanation"]["findings"][0]["simple_return_gap_pp"],
            "decision": "HUMAN_REVIEW_ONLY",
        }

    def check(self, item=None, *, review=None, rights=None):
        draft = json.dumps(self.valid if item is None else item,
                           separators=(",", ":")).encode()
        return verify_local_model_numeric_claim(
            self.review if review is None else review,
            self.rights if rights is None else rights,
            draft,
        )

    def test_exact_decimal_math_verification_is_not_source_auth(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK")):
            result = self.check()
        self.assertEqual(result["status"],
                         "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY")
        self.assertTrue(result["local_numeric_claim_recomputed"])
        self.assertEqual(result["simple_return_gap_pp"], self.valid["gap_pp"])
        self.assertEqual(result["engine"], "A")
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        self.assertEqual(result["external_network_requests"], 0)
        for key in ("publisher_source_authenticated", "source_rights_verified",
                    "model_origin_authenticated", "ai_agent_executed",
                    "external_sharing_allowed", "investment_recommendation",
                    "trade_executed"):
            self.assertIs(result[key], False)
        self.assertNotIn("NVDA", json.dumps(result))

    def test_hallucinated_number_and_unapproved_advice_are_blocked(self):
        for changes in (
            {"gap_pp": "9999.9999"},
            {"gap_pp": "1.0"},
            {"gap_pp": 1.0},
            {"gap_pp": None},
            {"decision": "BUY"},
            {"engine": "B"},
            {"claim_kind": "MARKET_BUBBLE_ESTIMATE"},
            {"schema": "another"},
            {"notes": "BUY NOW"},
        ):
            with self.subTest(changes=changes):
                out = self.check({**self.valid, **changes})
                self.assertEqual(out["status"], "BLOCKED", out)
                self.assertFalse(out["local_numeric_claim_recomputed"])
                self.assertFalse(out["trade_executed"])

    def test_corrupted_or_relinked_canonical_packets_rejected(self):
        for review, rights in (
            (self.review + b" ", self.rights),
            (self.review, self.rights + b" "),
            (self.review.replace(b"LOCAL_REPLAYED", b"INVALID______"),
             self.rights),
        ):
            with self.subTest(length=len(review)):
                result = self.check(review=review, rights=rights)
                self.assertEqual(result["status"], "BLOCKED")

    def test_duplicate_nonfinite_extra_bytes_rejected(self):
        invalid = (
            b'{"schema":"x","schema":"x"}',
            b'{"gap_pp":NaN}',
            b'{"gap_pp":Infinity}',
            b'{"gap_pp":-Infinity}',
            b'not json',
            b'[]',
            b'{}',
            b'x' * 1025,
            b"",
        )
        for bad in invalid:
            with self.subTest(bad=bad[:40]):
                outcome = verify_local_model_numeric_claim(
                    self.review, self.rights, bad,
                )
                self.assertEqual(outcome["status"], "BLOCKED")
                self.assertFalse(outcome["ai_agent_executed"])

    def test_exact_local_numeric_replay_cannot_authenticate_external_rights(self):
        result = self.check()
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["publisher_source_authenticated"])
        self.assertFalse(result["external_sharing_allowed"])


if __name__ == "__main__":
    unittest.main()
