"""P191 true issuer/SEC public facts, strict model classification guard."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from proofinvest import apple_public_model_claim as p


def envelope(claim=p._GREATER, cite=p._CITE, decision="HUMAN_REVIEW_ONLY",
             model=p._MODEL, count=10, extra=False):
    proposal = {"claim": claim, "source_ref": cite, "decision": decision}
    if extra:
        proposal["unexpected"] = "BUY"
    return json.dumps({
        "done": True, "model": model, "eval_count": count,
        "response": json.dumps(proposal),
    }).encode()


class ApplePublicLocalModelTests(unittest.TestCase):
    def test_public_actual_fact_independently_recalculated(self):
        result = p.verify_public_issuer_model_reply(envelope())
        self.assertEqual(result["status"],
                         "REAL_MODEL_PUBLIC_ISSUER_FACT_INDEPENDENTLY_MATCHED")
        self.assertEqual(result["cash_minus_net_income_usd_millions"], "12922")
        self.assertEqual(result["evidence_id"], p._CITE)
        self.assertTrue(result["actual_model_factual_claim_verified"])
        self.assertTrue(result["actual_model_token_count_verified"])
        for flag in ("publisher_original_bytes_authenticated",
                     "full_market_ndx_peer_rights_verified",
                     "full_agent_factual_quality_verified", "private_input_sent",
                     "investment_recommendation", "trade_executed",
                     "model_free_text_displayed"):
            self.assertFalse(result[flag], flag)

    def test_wrong_model_fact_citation_extra_advice_or_zero_tokens_blocked(self):
        for raw in (envelope(claim=p._NOT_GREATER),
                    envelope(cite="OTHER"), envelope(decision="BUY"),
                    envelope(extra=True), envelope(model="untrusted"),
                    envelope(count=0), b"{}", b"\xff",
                    b'{"done":true,"done":false}', b"x"*8193):
            with self.subTest(raw=raw[:65]):
                r = p.verify_public_issuer_model_reply(raw)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertEqual(r["guard_policy_preview"], "HOLD")

    def test_no_consent_invalid_port_no_http(self):
        with patch.object(p, "_call_loopback",
                          side_effect=AssertionError("HTTP SHOULD BE BLOCKED")) as mock:
            for args in ({}, {"consent": True, "port": 7999}):
                self.assertEqual(p.run_public_issuer_model(**args)["status"], "BLOCKED")
        mock.assert_not_called()

    def test_real_public_numbers_to_loopback_without_presolved_answer(self):
        requests = []
        def mock_call(body, *, port):
            requests.append((json.loads(body), port))
            return envelope()
        with patch.object(p, "_call_loopback", side_effect=mock_call) as call:
            r = p.run_public_issuer_model(consent=True)
        call.assert_called_once()
        self.assertTrue(r["actual_model_factual_claim_verified"])
        req, port = requests[0]
        self.assertEqual(port, 11435)
        self.assertEqual(req["model"], p._MODEL)
        self.assertIn("145097", req["prompt"])
        self.assertIn("132175", req["prompt"])
        self.assertNotIn("12922", req["prompt"])
        self.assertNotIn("sec.gov", req["prompt"].lower())
        self.assertNotIn("secret", req["prompt"].lower())
        self.assertEqual(r["external_network_requests"], 0)

    def test_local_model_failure_preserves_hold(self):
        with patch.object(p, "_call_loopback", side_effect=ValueError("blocked")):
            r = p.run_public_issuer_model(consent=True)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse(r["actual_model_factual_claim_verified"])
        self.assertEqual(r["loopback_http_attempts"], 1)
        self.assertFalse(r["trade_executed"])


if __name__ == "__main__":
    unittest.main()
