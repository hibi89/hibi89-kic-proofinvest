"""P234 separate generated-token responses with opposing financial indicators."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch
from proofinvest import apple_qwen_anomaly_screen as p


def response(signal=p._OVER, *, source=p._CITE,
             decision="HUMAN_REVIEW_ONLY", model=p._MODEL,
             tokens=21, extra=False):
    claim = {"signal": signal, "source_ref": source, "decision": decision}
    if extra:
        claim["recommendation"] = "BUY"
    return json.dumps({
        "model": model, "done": True, "eval_count": tokens,
        "response": json.dumps(claim),
    }).encode()


def pair(first=p._OVER, second=p._NOT_OVER):
    return (response(first), response(second))


class QwenTwoFinancialSignalsTests(unittest.TestCase):
    def test_independent_source_math_two_opposite_model_answers(self):
        r = p.verify_local_qwen_anomaly_response(pair())
        self.assertEqual(r["status"],
                         "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED", r)
        self.assertEqual(r["local_model_requests"], 2)
        self.assertEqual(r["verified_signals"],
                         {"inventory_signal": p._OVER,
                          "receivables_signal": p._NOT_OVER})
        self.assertTrue(r["two_opposing_independent_signals_verified"])
        self.assertTrue(r["actual_model_tokens_verified"])
        for key in (
            "original_sec_bytes_authenticated",
            "market_ndx_peer_rights_verified",
            "model_and_data_processing_rights_attested",
            "source_use_rights_verified", "full_abc_complete",
            "model_free_text_displayed", "fraud_proven",
            "investment_recommendation", "trade_executed",
            "external_model_requests", "raw_source_files_sent",
            "confidential_data_sent",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual(r["guard_decision"], "HOLD")

    def test_wrong_claim_citation_token_and_model_is_fail_closed(self):
        for replies in (
            pair(first=p._NOT_OVER),
            pair(second=p._OVER),
            (response(source="FABRICATED"), response(p._NOT_OVER)),
            (response(), response(p._NOT_OVER, decision="APPROVE")),
            (response(model="other"), response(p._NOT_OVER)),
            (response(tokens=0), response(p._NOT_OVER)),
            (response(extra=True), response(p._NOT_OVER)),
            (response(), b"{}"), (response(), b"\xff"),
            (response(), b'{"done":true,"done":false}'),
            (response(), b"x" * 8193),
            (response(), response(tokens=True)),
            (response(),), [response(), response(p._NOT_OVER)],
        ):
            with self.subTest(kind=str(type(replies)), bad=replies[0][:40]):
                result = p.verify_local_qwen_anomaly_response(replies)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["two_opposing_independent_signals_verified"])
                self.assertEqual(result["guard_decision"], "HOLD")
                self.assertFalse(result["trade_executed"])

    def test_default_no_model_outbound_without_both_consents(self):
        with patch.object(p, "_call_loopback",
                          side_effect=AssertionError("NO_REQUEST")) as net:
            for kw in ({}, {"explicit_local_model_consent": True},
                       {"explicit_public_derived_consent": True},
                       {"explicit_local_model_consent": True,
                        "explicit_public_derived_consent": True,
                        "port": 11434}):
                self.assertEqual(p.run_local_qwen_anomaly_screen(**kw)["status"],
                                 "BLOCKED")
        net.assert_not_called()

    def test_two_independent_bounded_redacted_local_requests(self):
        seen = []
        def call(data, *, port):
            data = json.loads(data)
            seen.append((data, port))
            return response(p._OVER if len(seen) == 1 else p._NOT_OVER)
        with patch.object(p, "_call_loopback", side_effect=call):
            r = p.run_local_qwen_anomaly_screen(
                explicit_local_model_consent=True,
                explicit_public_derived_consent=True)
        self.assertEqual(r["status"],
                         "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED", r)
        self.assertEqual(len(seen), 2)
        for index, (body, port) in enumerate(seen):
            self.assertEqual(port, 11435)
            self.assertEqual(body["model"], p._MODEL)
            self.assertIn("15.06", body["prompt"])
            self.assertIn(("154.30", "10.16")[index], body["prompt"])
            self.assertNotIn(("10.16", "154.30")[index], body["prompt"])
            for forbidden in (
                "478834", "416161", "14541", "5718", "43817", "39777",
                "NVDA", "api_key", "https://", "source_sha256", "BUY",
                "SEC original",
            ):
                self.assertNotIn(forbidden, body["prompt"])
            self.assertLessEqual(len(json.dumps(body).encode()), 2048)

    def test_second_reply_disagreement_blocks_both_signals(self):
        n = 0
        def bad(data, *, port):
            nonlocal n
            n += 1
            return response(p._OVER)
        with patch.object(p, "_call_loopback", side_effect=bad):
            r = p.run_local_qwen_anomaly_screen(
                explicit_local_model_consent=True,
                explicit_public_derived_consent=True)
        self.assertEqual(n, 2)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertFalse(r["two_opposing_independent_signals_verified"])
