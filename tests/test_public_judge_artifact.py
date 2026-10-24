"""Public-only artifact allowlist and byte-integrity protection."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import public_judge_artifact as artifact


class PublicJudgeArtifactTests(unittest.TestCase):
    def test_three_cases_and_all_authenticity_flags_are_false(self):
        output = artifact.make_receipt()
        self.assertEqual(output["schema"], artifact.SCHEMA)
        self.assertEqual([x["manual_arithmetic"] for x in output["scenarios"]],
                         ["verified", "conflict", "unavailable"])
        self.assertEqual([x["risk"] for x in output["scenarios"]], ["withheld"] * 3)
        for flag in ("source_reauthenticated", "dart_accessed", "ai_agent_executed",
                     "risk_calculated", "official_contest_submission",
                     "private_proposal_included"):
            self.assertIs(output[flag], False)

    def test_only_allowlisted_public_fields_in_bounded_json(self):
        report = artifact.make_receipt()
        self.assertEqual(set(report), {
            "schema", "reviewed_public_json_git_blob_sha1", "scope",
            "source_reauthenticated", "dart_accessed", "ai_agent_executed",
            "risk_calculated", "official_contest_submission",
            "private_proposal_included", "scenarios",
        })
        raw = artifact.encode(report)
        self.assertLess(len(raw), 2048)
        for sensitive in (b"KIC_ProofInvest_FROZEN_CANDIDATE", b"PRIVATE_PATH",
                          b"password", b"authorization", b"cookie"):
            self.assertNotIn(sensitive, raw.lower())

    def test_rejects_corrupted_or_augmented_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "receipt.json"
            file.write_bytes(artifact.encode(artifact.make_receipt()))
            artifact.verify_file(file)
            for change in (lambda x: x["scenarios"][0].update(risk="safe"),
                           lambda x: x.update(extra_private_payload="INJECTED")):
                edited = copy.deepcopy(artifact.make_receipt())
                change(edited)
                file.write_text(json.dumps(edited), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    artifact.verify_file(file)

    def test_modified_upstream_replay_cannot_be_exported(self):
        good = artifact.make_receipt()
        for alteration in ("authentication", "unexpected_case", "risk_calculated"):
            from proofinvest import judge_replay
            injected = judge_replay.replay()
            if alteration == "authentication":
                injected["independent_dart_authentication"] = True
            elif alteration == "unexpected_case":
                injected["scenarios"][0]["verification_state"] = "verified_real_source"
            else:
                injected["scenarios"][2]["risk_calculated"] = True
            with patch.object(artifact, "replay", return_value=injected):
                with self.subTest(alteration=alteration):
                    with self.assertRaises(ValueError):
                        artifact.make_receipt()
        self.assertEqual(artifact.make_receipt(), good)

    def test_cli_write_verify_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "public-receipt.json"
            base = [sys.executable, "-m", "scripts.public_judge_artifact"]
            first = subprocess.run(base + [str(path)], capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            checked = subprocess.run(base + ["--verify", str(path)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            attempted = subprocess.run(base + [str(path)], capture_output=True, text=True)
            self.assertNotEqual(attempted.returncode, 0)
            self.assertEqual(path.read_bytes(), artifact.encode(artifact.make_receipt()))

    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                artifact.verify_file(Path(temp) / "absent.json")


if __name__ == "__main__":
    unittest.main()
