"""Streamlit AppTest for local saved SEC ZIP -> finance -> Risk -> Guard audit.

Only self-authored synthetic SEC-shaped originals. This exercises the actual
archive replay and SQLite backend, without provider HTTP or credentials.
"""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from proofinvest.archived_sec_guard_ui import _safe_archived_report
from proofinvest.archived_sec_guard_report import run_archived_sec_guard_report
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from tests.test_sec_bundle_replay import fixture

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "저장된 SEC 3원문 ZIP → 검산·Risk·Guard 감사 — 오프라인"


class ArchivedGuardUITests(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory(prefix="kic-sec-guard-ui-")
        self.addCleanup(home.cleanup)
        self.folder = Path(home.name)
        self.archive = self.folder / "three-source.zip"
        self.audit = self.folder / "guard-review.sqlite"
        variables = patch.dict(os.environ, {"HOME": str(self.folder)})
        variables.start()
        self.addCleanup(variables.stop)
        receipt, raw = fixture()
        save_local_capture_bundle(self.archive, receipt=receipt, **raw)

    def screen(self):
        app = AppTest.from_file(str(APP)).run(timeout=20)
        self.assertIn(MODE, app.selectbox[0].options)
        app.selectbox[0].set_value(MODE).run(timeout=20)
        self.assertFalse(app.exception, [str(x.message) for x in app.exception])
        return app

    def fill(self, app, *, claim="", run_id="offline-one"):
        entries = {
            "archived_sec_guard_bundle": str(self.archive),
            "archived_sec_guard_db": str(self.audit),
            "archived_sec_guard_current": "2025-09-30",
            "archived_sec_guard_prior": "2024-09-30",
            "archived_sec_guard_needle": PHRASE,
            "archived_sec_guard_claim": claim,
            "archived_sec_guard_run_id": run_id,
        }
        for name, value in entries.items():
            app.text_input(key=name).set_value(value)
        return app

    def submit(self, app):
        app.button(key="archived_sec_guard_submit").click().run(timeout=30)
        self.assertFalse(app.exception, [str(x.message) for x in app.exception])
        return app

    def test_does_not_read_or_write_until_submit(self):
        app = self.screen()
        self.assertFalse(self.audit.exists())
        self.assertFalse(any(m.label == "Guard 판정" for m in app.metric))
        self.fill(app)
        self.assertFalse(self.audit.exists())

    def test_actual_archive_hold_to_guard_audit_and_report(self):
        app = self.screen()
        original = self.archive.read_bytes()
        self.fill(app)
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO NETWORK")) as opener:
            self.submit(app)
        opener.assert_not_called()
        self.assertTrue(self.audit.is_file())
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        self.assertTrue(GuardReviewStore(self.audit).verify_reviews())
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "HOLD"
                            for m in app.metric))
        self.assertTrue(any(m.label == "SQLite 감사 무결성" and m.value == "PASS"
                            for m in app.metric))
        self.assertTrue(any("로컬 ZIP 검산" in s.value for s in app.success))
        self.assertFalse(any("검증 실패" in e.value for e in app.error))
        with closing(sqlite3.connect(self.audit)) as db:
            row = db.execute("SELECT payload_json FROM guard_audit_events").fetchone()[0]
        self.assertNotIn(PHRASE, row)
        self.assertNotIn(str(self.archive), row)
        self.assertNotIn("SYNTHETIC SCRIPT", row)

    def test_financial_claim_conflict_is_reject_not_approval(self):
        app = self.screen()
        self.fill(app, claim="1.00")
        self.submit(app)
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "REJECT"
                            for m in app.metric))
        self.assertTrue(any(m.label == "검산" and m.value == "conflict"
                            for m in app.metric))
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        self.assertFalse(any("APPROVE" == m.value for m in app.metric))

    def test_explicit_acknowledgement_is_separate_from_hold(self):
        app = self.screen()
        self.fill(app)
        app.selectbox(key="archived_sec_guard_action").set_value("ACKNOWLEDGE")
        app.text_input(key="archived_sec_guard_reviewer").set_value("human")
        app.text_area(key="archived_sec_guard_reason").set_value(
            "Acknowledge unverified local evidence"
        )
        self.submit(app)
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "HOLD"
                            for m in app.metric))
        with closing(sqlite3.connect(self.audit)) as db:
            action, = db.execute("SELECT action FROM guard_human_reviews").fetchone()
        self.assertEqual(action, "ACKNOWLEDGE")
        self.assertTrue(GuardReviewStore(self.audit).verify_reviews())

    def test_corrupt_archive_blocks_write_and_result(self):
        raw = bytearray(self.archive.read_bytes())
        position = raw.find(SYNTHETIC_HTML)
        self.assertGreater(position, 0)
        raw[position+3] ^= 1
        self.archive.write_bytes(raw)
        app = self.screen()
        self.fill(app)
        self.submit(app)
        self.assertFalse(self.audit.exists())
        self.assertTrue(any("검증 실패" in e.value for e in app.error))
        self.assertFalse(any(m.label == "Guard 판정" for m in app.metric))

    def test_reused_run_with_changed_claim_fails_and_hides_stale_result(self):
        app = self.screen()
        self.fill(app, claim="100.00")
        self.submit(app)
        self.assertTrue(self.audit.exists())
        self.assertTrue(any(m.label == "Guard 판정" for m in app.metric))
        app.text_input(key="archived_sec_guard_claim").set_value("1.00")
        self.submit(app)
        self.assertTrue(any("검증 실패" in e.value for e in app.error))
        self.assertFalse(any(m.label == "Guard 판정" for m in app.metric))
        self.assertTrue(GuardAuditStore(self.audit).verify_chain())
        with closing(sqlite3.connect(self.audit)) as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM guard_audit_events").fetchone()[0], 1
            )

    def test_forged_report_cannot_render(self):
        app = self.screen()
        self.fill(app)
        original = run_archived_sec_guard_report(
            bundle_path=self.archive, audit_db_path=self.audit,
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE, run_id="preverify",
        )
        for forged in (
            {**original, "source_authenticated": True},
            {**original, "guard": {**original["guard"], "decision": "APPROVE"}},
            {**original, "audit": {**original["audit"], "chain_valid": False}},
        ):
            self.assertFalse(_safe_archived_report(forged))
        with patch("proofinvest.archived_sec_guard_ui.run_archived_sec_guard_report",
                   return_value={**original, "source_authenticated": True}):
            self.submit(app)
        self.assertFalse(any(m.label == "Guard 판정" for m in app.metric))
        self.assertTrue(any("검증 실패" in e.value for e in app.error))

    def test_missing_inputs_do_not_create_database(self):
        app = self.screen()
        self.submit(app)
        self.assertFalse(self.audit.exists())
        self.assertTrue(any("검증 실패" in e.value for e in app.error))


if __name__ == "__main__":
    unittest.main()
