"""P211 original-backed NVIDIA -> strictly consented no-network Guard SQLite review."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofinvest import nvidia_real_guard_audit as p
from proofinvest import nvidia_real_issuer_review as source
from proofinvest.guard_audit import GuardAuditStore

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"


class P211NvidiaAuditTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "nvda-local.sqlite"

    def run_case(self, **kwargs):
        return p.run_nvidia_guard_audit(
            run_id="P211-review-1", audit_db_path=self.path,
            source_receipt=source.actual_nvidia_issuer_receipt(), **kwargs,
        )

    def test_opt_in_before_disk_and_never_trades(self):
        result = self.run_case()
        self.assertEqual(result["reason_code"], "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
        self.assertFalse(self.path.exists())
        self.assertFalse(result["trade_executed"])
        self.assertEqual(result["network_requests"], 0)

    def test_actual_nvda_financials_flow_to_human_guard_and_hash_chain(self):
        result = self.run_case(acknowledge_local_persistence=True)
        self.assertEqual(result["status"], "REAL_NVDA_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED")
        self.assertTrue(result["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.path).verify_chain())
        report = result["report"]
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertEqual(report["guard"]["reason_codes"],
                         ["CLAIM_UNAVAILABLE", "RISK_UNAVAILABLE"])
        self.assertEqual(report["source_sha256"],
                         source.actual_nvidia_issuer_receipt()["source_sha256"])
        self.assertEqual(len(report["financial_evidence_sha256"]), 64)
        self.assertTrue(report["issuer_publisher_original_seen"])
        self.assertFalse(report["sec_original_authenticated"])
        self.assertFalse(report["source_rights_verified"])
        self.assertFalse(report["trade_executed"])
        self.assertFalse(result["full_abc_ready"])

    def test_replay_source_forgery_and_sqlite_tamper_refusal(self):
        first = self.run_case(acknowledge_local_persistence=True)
        second = self.run_case(acknowledge_local_persistence=True)
        self.assertEqual(first["report"]["audit"]["event_hash"],
                         second["report"]["audit"]["event_hash"])
        self.assertFalse(first["report"]["audit"]["replayed"])
        self.assertTrue(second["report"]["audit"]["replayed"])
        fake = source.actual_nvidia_issuer_receipt()
        fake["gaap_income_quarterly_and_annual"]["revenue"] = (
            "0", "1", "999999", "1"
        )
        bad = p.run_nvidia_guard_audit(
            run_id="P211-fake", audit_db_path=self.path,
            acknowledge_local_persistence=True, source_receipt=fake,
        )
        self.assertEqual(bad["status"], "BLOCKED")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM guard_run_registry").fetchone()[0], 1)
            db.execute("UPDATE guard_audit_events SET payload_json='{}'")
        self.assertFalse(GuardAuditStore(self.path).verify_chain())
        denied = p.run_nvidia_guard_audit(
            run_id="P211-more", audit_db_path=self.path,
            acknowledge_local_persistence=True,
            source_receipt=source.actual_nvidia_issuer_receipt(),
        )
        self.assertEqual(denied["status"], "BLOCKED")
        self.assertIsNone(denied["audit_written"])

    def test_invalid_id_and_fake_source_never_make_database(self):
        bad = p.run_nvidia_guard_audit(
            run_id="../../bad", audit_db_path=self.path,
            acknowledge_local_persistence=True,
            source_receipt=source.actual_nvidia_issuer_receipt(),
        )
        self.assertEqual(bad["reason_code"], "INVALID_AUDIT_RUN_ID")
        bad = p.run_nvidia_guard_audit(
            run_id="P211-fake", audit_db_path=self.path,
            acknowledge_local_persistence=True,
            source_receipt={"status": "FAKE"},
        )
        self.assertEqual(bad["status"], "BLOCKED")
        self.assertFalse(self.path.exists())

    def test_cli_flag_is_required_and_local_only(self):
        command = [sys.executable, "-B", "-m", "proofinvest.nvidia_real_guard_audit",
                   "--run-id", "P211-cli", "--audit-db", str(self.path)]
        denied = subprocess.run(command, cwd=_APP.parent,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(denied.returncode, 2, denied.stderr)
        self.assertFalse(self.path.exists())
        allowed = subprocess.run(
            command + ["--acknowledge-local-audit-persistence"],
            cwd=_APP.parent, capture_output=True, text=True, timeout=20)
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertEqual(json.loads(allowed.stdout)["report"]["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.path).verify_chain())

    def test_real_streamlit_nvda_mode_checkbox_button_and_human_hold(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        consent = next(x for x in at.checkbox if x.key == "p211_nvda_local_audit_ack")
        button = next(x for x in at.button if x.key == "p211_nvda_run_once")
        self.assertFalse(consent.value)
        self.assertTrue(button.disabled)
        consent.set_value(True).run(timeout=25)
        button = next(x for x in at.button if x.key == "p211_nvda_run_once")
        self.assertFalse(button.disabled)
        button.click().run(timeout=25)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("NVIDIA 실자료 Guard HOLD 감사 체인 검증 완료" in x.value
                            for x in at.success))

    def test_tampered_nvidia_receipt_blocks_ui_audit_success(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(source, "review_nvidia_actual_release",
                          return_value={"status": "BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception)
        self.assertFalse(any("NVIDIA 실자료 Guard HOLD 감사 체인 검증 완료" in x.value
                             for x in at.success))


if __name__ == "__main__":
    unittest.main()
