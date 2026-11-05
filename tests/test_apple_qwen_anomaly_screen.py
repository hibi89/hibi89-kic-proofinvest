"""P234 independent positive/negative anomaly signal classification gates."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from proofinvest import apple_qwen_anomaly_screen as p


def response(*, inventory=p._OVER, receivables=p._NOT_OVER,
             source=p._CITE, decision="HUMAN_REVIEW_ONLY",
             model=p._MODEL, tokens=21, extra=False):
    output = {
        "inventory_signal": inventory, "receivables_signal": receivables,
        "source_ref": source, "decision": decision,
    }
    if extra:
        output["free_text"] = "Buy now"
    return json.dumps({
        "model": model, "done": True, "eval_count": tokens,
        "response": json.dumps(output),
    }).encode()


class QwenTwoFinancialSignalsTests(unittest.TestCase):
    def test_derived_public_source_positive_and_negative_signals(self):
        r = p.verify_local_qwen_anomaly_response(response())
        self.assertEqual(r["status"],
                         "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED", r)
        self.assertEqual(r["verified_signals"],
                         {"inventory_signal": p._OVER,
                          "receivables_signal": p._NOT_OVER})
        self.assertTrue(r["actual_model_tokens_verified"])
        self.assertTrue(r["two_opposing_independent_signals_verified"])
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

    def test_wrong_positive_negative_citation_or_advice_fails_closed(self):
        for raw in (
            response(inventory=p._NOT_OVER),
            response(receivables=p._OVER),
            response(source="FABRICATED"),
            response(decision="APPROVE"),
            response(model="qwen2.5:7b"),
            response(tokens=0),
            response(extra=True),
            b"{}", b"\xff",
            b'{"done":true,"done":false}',
            response().replace(b'"eval_count": 21',
                               b'"eval_count": true'),
            b"x" * 8193,
        ):
            with self.subTest(raw=raw[:70]):
                r = p.verify_local_qwen_anomaly_response(raw)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertFalse(r["two_opposing_independent_signals_verified"])
                self.assertEqual(r["guard_decision"], "HOLD")
                self.assertFalse(r["trade_executed"])

    def test_default_no_model_outbound_without_two_consents(self):
        with patch.object(p, "_call_loopback",
                          side_effect=AssertionError("NO_REQUEST")) as net:
            for opts in (
                {},
                {"explicit_local_model_consent": True},
                {"explicit_public_derived_consent": True},
                {"explicit_local_model_consent": True,
                 "explicit_public_derived_consent": True, "port": 11434},
            ):
                self.assertEqual(p.run_local_qwen_anomaly_screen(**opts)["status"],
                                 "BLOCKED")
        net.assert_not_called()

    def test_model_prompt_only_public_derived_percentages_and_single_call(self):
        calls = []
        def fake(data, *, port):
            calls.append((json.loads(data), port))
            return response()
        with patch.object(p, "_call_loopback", side_effect=fake):
            r = p.run_local_qwen_anomaly_screen(
                explicit_local_model_consent=True,
                explicit_public_derived_consent=True,
            )
        self.assertEqual(r["status"],
                         "REAL_QWEN_TWO_PUBLIC_FINANCIAL_SIGNALS_MATCHED", r)
        self.assertEqual(len(calls), 1)
        body, port = calls[0]
        self.assertEqual(port, 11435)
        self.assertEqual(body["model"], p._MODEL)
        for metric in ("15.06", "154.30", "10.16"):
            self.assertIn(metric, body["prompt"])
        for forbidden in (
            "478834", "416161", "14541", "5718", "43817", "39777",
            "NVDA", "ticker", "api_key", "https://", "source_sha256",
            "SEC original", "BUY", "FAKE",
        ):
            self.assertNotIn(forbidden, body["prompt"])
        self.assertLessEqual(len(json.dumps(body).encode()), 2048)

    def test_wrong_real_model_claim_is_not_displayable(self):
        with patch.object(p, "_call_loopback",
                          return_value=response(receivables=p._OVER)):
            result = p.run_local_qwen_anomaly_screen(
                explicit_local_model_consent=True,
                explicit_public_derived_consent=True,
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["two_opposing_independent_signals_verified"])
