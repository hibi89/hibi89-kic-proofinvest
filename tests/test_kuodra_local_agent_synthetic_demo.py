"""CLI proof: owner question -> actual existing SEC/ML tools, fictional only."""
from __future__ import annotations
import json
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

from proofinvest.kuodra_local_agent_synthetic_demo import run_fictional_question_agent_demo


class SyntheticQuestionAgentDemoTests(unittest.TestCase):
    def test_actual_offline_guard_and_ml_route(self):
        result = run_fictional_question_agent_demo()
        self.assertEqual(result["status"], "PASS_OFFLINE_LOCAL_TOOL_WORKFLOW")
        self.assertEqual([c["decision"] for c in result["cases"]],
                         ["HOLD", "REJECT"])
        self.assertTrue(all(c["audit_valid"] and c["source_pins_checked"]
                            for c in result["cases"]))
        self.assertEqual(result["external_network_requests"], 0)
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["host_no_egress_verified"])
        self.assertFalse(result["finance_accuracy_proven"])
        self.assertFalse(result["production_ready"])
        self.assertNotIn("fictionalLocalML", json.dumps(result))
        self.assertNotIn("fictionalOwner", json.dumps(result))

    def test_cli_stdout_is_restricted_json(self):
        p = subprocess.run(
            [sys.executable, "-B", "-m",
             "proofinvest.kuodra_local_agent_synthetic_demo"],
            check=True, timeout=90, text=True, capture_output=True)
        report = json.loads(p.stdout)
        self.assertEqual(report["status"], "PASS_OFFLINE_LOCAL_TOOL_WORKFLOW")
        self.assertEqual(len(report["cases"]), 2)
        self.assertNotIn("fictitiousIssuer0", p.stdout)
        self.assertNotIn("fictionalPrivateSource", p.stdout)

    def test_network_socket_never_called(self):
        with patch.object(socket.socket, "connect",
                          side_effect=AssertionError("NO_NETWORK")) as connect:
            outcome = run_fictional_question_agent_demo()
            connect.assert_not_called()
        self.assertEqual(outcome["cases"][1]["decision"], "REJECT")


if __name__ == "__main__":
    unittest.main()
