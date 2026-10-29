"""Contract tests for reproducible KIC router judge matrix."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.kic_router_judge_matrix import CASES, run_matrix


class KICRouterJudgeMatrixTests(unittest.TestCase):
    def test_all_cases_and_safety_contract_pass(self):
        result = run_matrix()
        self.assertEqual(result["status"], "PASS", result["failed_case_ids"])
        self.assertEqual(result["cases"], 15)
        self.assertEqual(result["passed"], 15)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["results"]), len(CASES))
        self.assertTrue(all(x["safety_invariants_pass"] for x in result["results"]))
        self.assertTrue(all(x["result"] == "PASS" for x in result["results"]))
        self.assertEqual(result["real_sec_requests"], 0)
        self.assertEqual(result["llm_requests"], 0)
        self.assertEqual(result["trades"], 0)
        self.assertFalse(result["source_authenticated"])

    def test_replay_is_deterministic(self):
        a, b = run_matrix(), run_matrix()
        self.assertEqual(a, b)
        self.assertEqual(len(a["case_results_sha256"]), 64)

    def test_cli_writes_receipt_without_overwriting(self):
        with tempfile.TemporaryDirectory(prefix="kic-router-matrix-") as folder:
            path = Path(folder) / "receipt.json"
            command = [
                sys.executable, "-B", "-m", "scripts.kic_router_judge_matrix", str(path)
            ]
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            parsed = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["status"], "PASS")
            self.assertEqual(parsed["passed"], 15)
            original = path.read_bytes()
            second = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
