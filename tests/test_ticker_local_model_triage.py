"""P179 real localhost HTTP, negative responses, zero external model calls."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_model_triage import (
    triage_review, _blocked, _expected_missing_evidence_focus,
)
from tests.test_ticker_offline_review_builder import payload
from proofinvest.ticker_offline_review_builder import build_offline_initial_review


class ModelHandler(BaseHTTPRequestHandler):
    observations = []
    response_body = {}
    http_status = 200

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.__class__.observations.append({
            "path": self.path, "host": self.headers.get("Host"),
            "body": self.rfile.read(int(self.headers["Content-Length"])),
        })
        body = json.dumps(self.response_body).encode()
        self.send_response(self.http_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalModelTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = build_offline_initial_review(**payload())
        assert fixture["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
        cls.packet, cls.rights = (
            fixture["review_packet"], fixture["source_clearance_report"],
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        ModelHandler.observations.clear()
        ModelHandler.http_status = 200
        ModelHandler.response_body = {
            "done": True, "model": "test-local-model",
            "response": json.dumps({
                "focus_engine": "B",
                "decision": "HUMAN_REVIEW_ONLY",
            }),
        }

    def call(self, **changes):
        args = {
            "model": "test-local-model", "port": self.port,
            "allow_local_model": True,
            "confirm_local_derivative_processing": True,
        }
        return triage_review(self.packet, self.rights, **(args | changes))

    def test_default_does_not_open_http_or_send_data(self):
        with patch("proofinvest.ticker_local_model_triage._call_loopback",
                   side_effect=AssertionError("UNAPPROVED_LOCAL_HTTP")):
            for changes in ({}, {"allow_local_model": True},
                            {"confirm_local_derivative_processing": True}):
                report = triage_review(self.packet, self.rights, **changes)
                self.assertEqual(report["status"], "BLOCKED")
                self.assertEqual(report["loopback_http_attempts"], 0)

    def test_real_local_http_receives_only_status_codes_not_origins(self):
        out = self.call()
        self.assertEqual(out["status"],
                         "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN")
        self.assertEqual(out["focus_engine"], "B")
        self.assertEqual(
            out["focus_status"],
            json.loads(self.packet)["explanation"]["findings"][1]["status"],
        )
        self.assertTrue(out["model_protocol_http_verified"])
        self.assertTrue(out["human_review_priority_policy_verified"])
        self.assertTrue(out["model_structured_focus_verified"])
        self.assertFalse(out["model_inference_authenticated"])
        self.assertFalse(out["ai_agent_executed"])
        self.assertFalse(out["source_rights_verified"])
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertFalse(out["trade_executed"])
        self.assertEqual(len(ModelHandler.observations), 1)
        request = ModelHandler.observations[0]
        self.assertEqual(request["path"], "/api/generate")
        self.assertEqual(request["host"], "127.0.0.1:" + str(self.port))
        body = json.loads(request["body"])
        self.assertEqual(body["model"], "test-local-model")
        self.assertIs(body["stream"], False)
        self.assertEqual(body["format"], {
            "type": "object",
            "properties": {
                "focus_engine": {"type": "string", "enum": ["A", "B", "C"]},
                "decision": {"type": "string", "enum": ["HUMAN_REVIEW_ONLY"]},
            },
            "required": ["focus_engine", "decision"],
            "additionalProperties": False,
        })
        self.assertLessEqual(len(request["body"]), 2048)
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertEqual(body["options"]["num_predict"], 128)
        self.assertNotIn("NVDA", body["prompt"])
        self.assertNotIn("1045810", body["prompt"])
        self.assertNotIn("http", body["prompt"])
        self.assertNotIn("companyfacts", body["prompt"])
        self.assertNotIn("alpha", body["prompt"].lower())
        self.assertNotIn("10-K", body["prompt"])
        self.assertNotIn("source_hashes", body["prompt"])
        self.assertNotIn("CLOSE", body["prompt"])
        self.assertNotIn("ORIGINAL", body["prompt"])
        self.assertNotIn("llm", out["safe_existing_interpretation"].lower())

    def test_malformed_approved_model_names_and_ports_fail_without_http(self):
        for value in ("", "http://attacker", "../dir", "model bad", 2):
            with self.subTest(model=value):
                result = self.call(model=value)
                self.assertEqual(result["status"], "BLOCKED")
        for value in (0, 80, 65536, "11434", False):
            with self.subTest(port=value):
                self.assertEqual(self.call(port=value)["status"], "BLOCKED")
        self.assertFalse(ModelHandler.observations)

    def test_missing_evidence_review_priority_policy(self):
        statuses = {
            "A": "REPORTED_UNVERIFIED",
            "B": "REVIEWED_UNVERIFIED",
            "C": "OBSERVED_COMPARISON_UNVERIFIED",
        }
        self.assertEqual(_expected_missing_evidence_focus(statuses), "A")
        self.assertEqual(_expected_missing_evidence_focus(
            {**statuses, "B": "UNAVAILABLE"}), "B")
        self.assertEqual(_expected_missing_evidence_focus(
            {**statuses, "C": "INSUFFICIENT_EVIDENCE"}), "C")
        self.assertEqual(_expected_missing_evidence_focus(
            {**statuses, "A": "INSUFFICIENT_MARKET_VARIANCE",
             "B": "UNAVAILABLE"}), "A")

    def test_schema_valid_but_wrong_focus_is_blocked(self):
        ModelHandler.response_body = {
            "done": True, "model": "test-local-model",
            "response": json.dumps({
                "focus_engine": "A", "decision": "HUMAN_REVIEW_ONLY",
            }),
        }
        out = self.call()
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["loopback_http_attempts"], 1)
        self.assertFalse(out["ai_agent_executed"])
        self.assertFalse(out["trade_executed"])
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertEqual(
            out["reason_code"], "MODEL_FOCUS_DISAGREES_WITH_LOCAL_POLICY",
        )
        self.assertIs(out["model_structured_focus_verified"], True)
        self.assertIs(out["human_review_priority_policy_verified"], False)
        self.assertNotIn("focus_engine", out)
        self.assertEqual(len(ModelHandler.observations), 1)

    def test_adversarial_model_output_is_rejected_no_model_text_export(self):
        for text in (
            "Buy NVDA now",
            '{"focus_engine":"A","decision":"BUY"}',
            '{"focus_engine":"Z","decision":"HUMAN_REVIEW_ONLY"}',
            '{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY","trade":true}',
            '{"focus_engine":"A","focus_engine":"B","decision":"HUMAN_REVIEW_ONLY"}',
            '{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY","why":"SEC says buy"}',
        ):
            with self.subTest(reply=text):
                ModelHandler.response_body = {
                    "model": "test-local-model", "done": True,
                    "response": text,
                }
                result = self.call()
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertFalse(result["ai_agent_executed"])
                self.assertFalse(result["trade_executed"])

    def test_model_not_ready_and_wrong_model_cannot_assert_success(self):
        for reply in (
            {"done": False, "model": "test-local-model",
             "response": '{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY"}'},
            {"done": True, "model": "fake-model",
             "response": '{"focus_engine":"A","decision":"HUMAN_REVIEW_ONLY"}'},
        ):
            ModelHandler.response_body = reply
            self.assertEqual(self.call()["status"], "BLOCKED")
        ModelHandler.http_status = 403
        self.assertEqual(self.call()["status"], "BLOCKED")

    def test_corrupted_or_relinked_original_receipts_block_before_socket(self):
        packet = self.packet.replace(b"LOCAL_REPLAYED", b"LOCAL_FAKE__")
        for p, r in ((packet, self.rights), (self.packet, self.rights + b" ")):
            out = triage_review(
                p, r, model="test-local-model", port=self.port,
                allow_local_model=True,
                confirm_local_derivative_processing=True,
            )
            self.assertEqual(out["status"], "BLOCKED")
            self.assertEqual(out["loopback_http_attempts"], 0)
        self.assertEqual(ModelHandler.observations, [])


if __name__ == "__main__":
    unittest.main()
