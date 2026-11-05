"""P233 independent read-only public Apple numbers and real model safety gate."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from proofinvest import apple_qwen_public_claim as p


def answer(label="CASH_GREATER", source=None, model=None, tokens=20,
           decision="HUMAN_REVIEW_ONLY", extra=False):
    claim = {
        "comparison": label,
        "source_ref": p._CITE if source is None else source,
        "decision": decision,
    }
    if extra:
        claim["recommendation"] = "BUY"
    return json.dumps({
        "model": p._MODEL if model is None else model,
        "done": True, "eval_count": tokens, "response": json.dumps(claim),
    }).encode()


class ActualLocalQwenFactTests(unittest.TestCase):
    def test_replay_public_facts_independently(self):
        result = p.verify_local_qwen_public_facts(answer())
        self.assertEqual(result["status"],
                         "ACTUAL_LOCAL_MODEL_PUBLIC_NUMERIC_COMPARISON_MATCHED")
        self.assertEqual(result["cash_minus_net_income_usd_millions"], "12922")
        self.assertTrue(result["actual_model_tokens_verified"])
        self.assertTrue(result["independent_public_fact_validated"])
        for k in ("issuer_raw_sec_bytes_authenticated",
                  "copyright_or_model_data_rights_attested",
                  "true_ndx_stock_or_peer_rights_verified", "trade_executed",
                  "external_model_requests", "secrets_or_originals_sent",
                  "model_free_text_displayed", "investment_advice"):
            self.assertFalse(result[k])

    def test_wrong_facts_and_hallucinated_citations_denied(self):
        for val in (answer(label="CASH_NOT_GREATER"),
                    answer(source="FAKE"),
                    answer(model="qwen2.5:7b"),
                    answer(tokens=0),
                    answer(decision="INVEST"),
                    answer(extra=True), b"{}", b"\xff",
                    b'{"done":true,"done":false}', b"x" * 8193):
            with self.subTest(value=val[:90]):
                bad = p.verify_local_qwen_public_facts(val)
                self.assertEqual(bad["status"], "BLOCKED")
                self.assertEqual(bad["guard_policy_preview"], "HOLD")
                self.assertFalse(bad["actual_model_tokens_verified"])

    def test_consent_and_fixed_loopback_avoid_network(self):
        with patch.object(p, "_call_loopback",
                          side_effect=AssertionError("NO_NETWORK")) as net:
            for kw in ({}, {"explicit_public_local_consent": True,
                            "port": 11434}):
                out = p.run_actual_local_qwen_public_facts(**kw)
                self.assertEqual(out["status"], "BLOCKED")
        net.assert_not_called()

    def test_exact_one_redacted_loopback_request(self):
        called = []
        def call(data, *, port):
            called.append((json.loads(data), port))
            return answer()
        with patch.object(p, "_call_loopback", side_effect=call):
            result = p.run_actual_local_qwen_public_facts(
                explicit_public_local_consent=True)
        self.assertTrue(result["independent_public_fact_validated"])
        self.assertEqual(len(called), 1)
        payload, port = called[0]
        self.assertEqual(port, 11435)
        self.assertEqual(payload["model"], "qwen2.5:0.5b-instruct")
        self.assertIn("145097", payload["prompt"])
        self.assertIn("132175", payload["prompt"])
        for no in ("12922", "private", "api_key", "https://",
                   "source_sha256", "NDX", "SECRET"):
            self.assertNotIn(no, payload["prompt"])
        self.assertLessEqual(len(json.dumps(payload).encode()), 2048)

    def test_actual_mismatched_real_output_fails_closed(self):
        with patch.object(p, "_call_loopback",
                          return_value=answer(label="CASH_NOT_GREATER")):
            bad = p.run_actual_local_qwen_public_facts(
                explicit_public_local_consent=True)
        self.assertEqual(bad["status"], "BLOCKED")
        self.assertFalse(bad["trade_executed"])
