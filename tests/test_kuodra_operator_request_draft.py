"""P15 offline P13 preview -> P14 pinned operator request; never auto execute."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_operator_request_draft import (
    build_operator_request_draft, main,
)
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods
from test_kuodra_operator_replay import capture_fixture


class OperatorDraftTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kuodra-p15-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.zip = self.root / "capture.zip"
        self.db = self.root / "audit.sqlite"
        capture_fixture(self.zip)
        self.options = dict(
            requested_intent="GROWTH_CHECK",
            current_end="2025-09-30",
            prior_end="2024-09-30",
            needle=PHRASE, audit_db=self.db, run_id="p15-first",
        )

    def draft(self, **changes):
        return build_operator_request_draft(self.zip, **(self.options | changes))

    def test_draft_pins_actual_preview_sources_and_never_executes(self):
        before = self.zip.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_NETWORK")) as net:
            output = self.draft()
        net.assert_not_called()
        self.assertEqual(output["status"], "ready_for_operator_review")
        self.assertEqual(output["reason_code"], "DRAFT_ONLY_REQUIRES_SEPARATE_APPROVAL")
        preview = inspect_saved_capture_periods(self.zip)
        self.assertEqual(output["operator_request"]["expected_source_sha256"],
                         preview["source_sha256"])
        self.assertTrue(output["selected_original_text_node_verified"])
        self.assertFalse(output["audit_written"])
        self.assertFalse(output["audit_consent_granted"])
        self.assertFalse(output["source_authenticated"])
        self.assertFalse(self.db.exists())
        self.assertEqual(before, self.zip.read_bytes())

    def test_draft_to_operator_replay_requires_separate_consent(self):
        draft = self.draft()
        request = draft["operator_request"]
        proposal = {"action": "RUN", "intent": "GROWTH_CHECK"}
        no_consent = run_offline_proposal_replay(
            request, proposal, acknowledge_local_audit_persistence=False
        )
        self.assertEqual(no_consent["reason_code"],
                         "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
        self.assertFalse(self.db.exists())
        result = run_offline_proposal_replay(
            request, proposal, acknowledge_local_audit_persistence=True
        )
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["operator_source_digests_verified"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_period_must_be_manually_selected_from_verified_filing(self):
        result = self.draft(current_end="2023-09-30", prior_end="2022-09-30")
        self.assertEqual(result["reason_code"],
                         "OPERATOR_PERIOD_NOT_IN_VERIFIED_PREVIEW")
        self.assertIsNone(result["operator_request"])
        self.assertFalse(self.db.exists())

    def test_invalid_or_script_only_literal_fails_closed(self):
        result = self.draft(needle="NONEXISTENT_PUBLIC_REVENUE")
        self.assertEqual(result["reason_code"],
                         "OPERATOR_NEEDLE_NOT_UNIQUE_TEXT_NODE")
        self.zip.unlink()
        capture_fixture(self.zip, original=(
            b"<html><body><script>PRIVATE_SCRIPT_ONLY_TOKEN</script>"
            b"<p>Readable nonmatching literal evidence.</p></body></html>"
        ))
        result = self.draft(needle="PRIVATE_SCRIPT_ONLY_TOKEN")
        self.assertEqual(result["reason_code"],
                         "OPERATOR_NEEDLE_NOT_UNIQUE_TEXT_NODE")
        self.assertFalse(self.db.exists())

    def test_ambiguous_duplicate_literal_not_cited(self):
        self.zip.unlink()
        capture_fixture(self.zip, original=(
            b"<html><body><p>TEST_LITERAL_SOURCE_SPAN</p>"
            b"<p>TEST_LITERAL_SOURCE_SPAN</p></body></html>"
        ))
        result = self.draft(needle="TEST_LITERAL_SOURCE_SPAN")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(self.db.exists())

    def test_valid_repacked_same_identity_original_blocks_old_draft(self):
        old = self.draft()["operator_request"]
        self.zip.unlink()
        capture_fixture(self.zip, original=SYNTHETIC_HTML + b"<!-- new bytes -->")
        current = self.draft()["operator_request"]
        self.assertNotEqual(old["expected_source_sha256"],
                            current["expected_source_sha256"])
        proposal = {"action": "RUN", "intent": "GROWTH_CHECK"}
        blocked = run_offline_proposal_replay(
            old, proposal, acknowledge_local_audit_persistence=True
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse(self.db.exists())

    def test_invalid_run_id_and_cross_intent_claim_rejected(self):
        for changes in (
            {"run_id": "../../bad"},
            {"requested_intent": "RISK_CHECK", "claimed_growth_pct": "100"},
            {"requested_intent": "UNAUTHORIZED"},
            {"needle": "\x00invalid literal"},
            {"claimed_growth_pct": "1e500"},
        ):
            with self.subTest(changes=changes):
                result = self.draft(**changes)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(self.db.exists())

    def test_source_risk_intents_can_draft_without_auto_execution(self):
        for intent in ("SOURCE_REVIEW", "RISK_CHECK"):
            with self.subTest(intent=intent):
                result = self.draft(requested_intent=intent)
                self.assertEqual(result["status"], "ready_for_operator_review")
                self.assertEqual(result["operator_request"]["requested_intent"], intent)
                self.assertFalse(self.db.exists())

    def test_capture_zip_and_audit_db_cannot_collide(self):
        result = self.draft(audit_db=self.zip)
        self.assertEqual(result["reason_code"], "AUDIT_CAPTURE_INPUT_COLLISION")
        self.assertFalse(self.db.exists())

    def test_corrupt_capture_prevents_request_creation(self):
        broken = bytearray(self.zip.read_bytes())
        broken[0] ^= 1
        self.zip.write_bytes(broken)
        result = self.draft()
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["operator_request"])
        self.assertFalse(self.db.exists())

    def _args(self):
        return [
            "--capture-zip", str(self.zip),
            "--requested-intent", "GROWTH_CHECK",
            "--current-end", "2025-09-30",
            "--prior-end", "2024-09-30",
            "--needle", PHRASE,
            "--audit-db", str(self.db),
            "--run-id", "p15-cli",
        ]

    def test_cli_draft_stdout_never_writes_file_or_db(self):
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = main(self._args())
        data = json.loads(capture.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "ready_for_operator_review")
        self.assertNotIn("request_file_written", data)
        self.assertFalse(self.db.exists())
        self.assertEqual(list(self.root.iterdir()), [self.zip])

    def test_cli_explicit_new_draft_file_no_overwrite(self):
        target = self.root / "operator-request.json"
        capture = io.StringIO()
        with redirect_stdout(capture):
            self.assertEqual(main(self._args() + [
                "--output-request-json", str(target),
            ]), 0)
        report = json.loads(capture.getvalue())
        self.assertTrue(report["request_file_written"])
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                         report["operator_request"])
        first = target.read_bytes()
        with redirect_stdout(io.StringIO()) as fail:
            self.assertEqual(main(self._args() + [
                "--output-request-json", str(target),
            ]), 2)
        self.assertEqual(json.loads(fail.getvalue())["reason_code"],
                         "REQUEST_DRAFT_EXPORT_FAILED_NO_AUDIT")
        self.assertEqual(target.read_bytes(), first)
        self.assertFalse(self.db.exists())

    def test_cli_output_cannot_target_original_or_sqlite(self):
        for target in (self.zip, self.db, self.root / "draft.txt"):
            with self.subTest(target=target):
                with redirect_stdout(io.StringIO()) as stdout:
                    code = main(self._args() + [
                        "--output-request-json", str(target),
                    ])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stdout.getvalue())["status"], "blocked")
                self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
