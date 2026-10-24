"""Judge replay integrity tests: no external calls or private files."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest import judge_replay, manual_case_demo


class OfflineJudgeReplayTests(unittest.TestCase):
    def test_replays_exact_three_states_without_any_risk_score(self):
        result = judge_replay.replay()
        self.assertEqual(result["schema"], "proofinvest.offline-judge-replay.v1")
        self.assertEqual([x["verification_state"] for x in result["scenarios"]],
                         ["verified", "conflict", "unavailable"])
        self.assertEqual([x["scenario"] for x in result["scenarios"]],
                         ["match", "conflict", "no_claim"])
        self.assertTrue(all(x["risk_state"] == "unavailable" for x in result["scenarios"]))
        self.assertTrue(all(x["risk_calculated"] is False for x in result["scenarios"]))
        self.assertTrue(all(x["manual_computed_pct"] == "16.20" for x in result["scenarios"]))

    def test_no_live_data_or_llm_or_submission_claim(self):
        result = judge_replay.replay()
        for key in ("live_api_called", "independent_dart_authentication",
                    "ai_agent_executed", "investment_recommendation",
                    "actual_official_hackathon_submission"):
            self.assertIs(result[key], False)
        self.assertEqual(result["issuer_ir_publication_date"], "2025-02-18")
        self.assertEqual(result["reviewed_record_git_blob_sha1"],
                         manual_case_demo.REVIEWED_GIT_BLOB_SHA1)

    def test_deterministic_replay_without_source_mutation(self):
        path = manual_case_demo.EVIDENCE_PATH
        before = path.read_bytes()
        self.assertEqual(judge_replay.replay(), judge_replay.replay())
        self.assertEqual(path.read_bytes(), before)

    def test_any_byte_change_to_pinned_record_fails_closed_even_if_new_math_matches(self):
        raw = manual_case_demo.EVIDENCE_PATH.read_bytes()
        changed = raw.replace(b'"300870903"', b'"400870903"')
        self.assertNotEqual(raw, changed)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "imposter.json"
            path.write_bytes(changed)
            with patch.object(manual_case_demo, "EVIDENCE_PATH", path):
                with self.assertRaisesRegex(ValueError, "reviewed evidence bytes changed"):
                    manual_case_demo.run_manual_case()
                with self.assertRaisesRegex(ValueError, "reviewed evidence bytes changed"):
                    judge_replay.replay()

    def test_cannot_replace_source_while_preserving_issuer_metadata(self):
        raw = manual_case_demo.EVIDENCE_PATH.read_bytes()
        altered = raw.replace(b"2025_SEC_Consolidated_Financial_statements.pdf",
                              b"changed_other_company_financial_statement.pdf")
        self.assertNotEqual(raw, altered)
        with tempfile.TemporaryDirectory() as root:
            fake = Path(root) / "evidence.json"
            fake.write_bytes(altered)
            with patch.object(manual_case_demo, "EVIDENCE_PATH", fake):
                with self.assertRaisesRegex(ValueError, "reviewed evidence bytes changed"):
                    manual_case_demo.read_reviewed_evidence()

    def test_cli_json_and_text_outputs_are_separate_and_private_free(self):
        for fmt in ([], ["--json"]):
            with self.subTest(fmt=fmt):
                p = subprocess.run(
                    [sys.executable, "-m", "proofinvest.judge_replay", *fmt],
                    capture_output=True, text=True, check=True,
                )
                self.assertNotIn("KIC_ProofInvest_FROZEN_CANDIDATE", p.stdout)
                self.assertNotIn("secret", p.stdout.lower())
                if fmt:
                    parsed = json.loads(p.stdout)
                    self.assertEqual(len(parsed["scenarios"]), 3)
                    self.assertFalse(parsed["live_api_called"])
                else:
                    self.assertIn("Risk=보류", p.stdout)
                    self.assertIn("AI Agent 아님", p.stdout)

    def test_report_missing_record_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(manual_case_demo, "EVIDENCE_PATH", Path(root) / "missing.json"):
                with self.assertRaises(FileNotFoundError):
                    judge_replay.replay()


if __name__ == "__main__":
    unittest.main()
