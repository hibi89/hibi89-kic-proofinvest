"""Actual Streamlit offline DL/Guard audit and report click-through tests.

Tests use disposable HOME and local SQLite fixtures; never contact SEC.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from integrations.dl_vendor import core, originals
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.dl_guard_ui import SYNTHETIC, LOCAL, _safe_report
from proofinvest.kic_dl_guard_demo import run_synthetic_demo

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "DL → Guard → SQLite 감사 보고서 — 오프라인"
CIK = "0000320193"
ACCESSION = "0000320193-25-000079"
DAY = "2025-11-01"
FIXTURE = (Path(__file__).resolve().parents[1] /
           "integrations/dl_vendor/fixtures/kic_apple_handoff_synthetic.json")


class DlGuardAppClickthroughTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="kic-dl-guard-ui-")
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        environment = patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        self.audit_db = self.home / "guard-audit.sqlite"
        self.dl_db = self.home / "dl-ledger.sqlite"

    def screen(self):
        at = AppTest.from_file(str(APP)).run(timeout=20)
        self.assertIn(MODE, at.selectbox[0].options)
        at.selectbox[0].set_value(MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        return at

    def make_dl(self):
        raw = FIXTURE.read_bytes()
        index = core.index_submissions(
            raw, cik=CIK, as_of=DAY, forms=core.parse_forms("10-K"),
            provenance="OFFLINE_UNVERIFIED",
            collected_at="2025-11-01T10:30:00Z",
        )
        core.save_index(self.dl_db, raw, index)
        locator = originals.locate_original(self.dl_db, cik=CIK, accession=ACCESSION)
        with patch("integrations.dl_vendor.originals._timestamp",
                   return_value="2025-11-01T10:32:00Z"):
            receipt = originals.persist_original(
                db_path=self.dl_db, receipt=locator,
                raw=b"<html><p>Revenue 100</p><script>DO NOT RENDER</script></html>",
                kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
            )
        return receipt["filing_sha256"]

    def enter_local(self, at, sha):
        values = {
            "dl_guard_dl_db": str(self.dl_db),
            "dl_guard_audit_db": str(self.audit_db),
            "dl_guard_cik": CIK,
            "dl_guard_accession": ACCESSION,
            "dl_guard_sha": sha,
            "dl_guard_as_of": DAY,
            "dl_guard_term": "Revenue",
            "dl_guard_run_id": "ui-verified",
        }
        for key, value in values.items():
            at.text_input(key=key).set_value(value)

    def test_opening_ui_has_no_audit_or_eager_demo(self):
        at = self.screen()
        self.assertEqual(at.radio(key="dl_guard_run_mode").value, SYNTHETIC)
        self.assertFalse(self.audit_db.exists())
        self.assertFalse(self.dl_db.exists())
        self.assertFalse(any(m.label == "Guard 판정" for m in at.metric))

    def test_synthetic_click_runs_real_local_path_and_safe_report(self):
        at = self.screen()
        at.button(key="dl_guard_demo_run").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "HOLD"
                            for m in at.metric))
        self.assertTrue(any(m.label == "SQLite 감사 무결성" and m.value == "PASS"
                            for m in at.metric))
        self.assertTrue(any("합성 자료 E2E 실행" in x.value for x in at.success))
        self.assertFalse(self.audit_db.exists(), "Synthetic demo must not write user HOME")
        self.assertFalse(self.dl_db.exists())
        self.assertFalse(any("DO NOT RENDER" in str(x.value) for x in at.markdown))

    def test_local_form_is_write_free_until_submit_and_then_audits(self):
        sha = self.make_dl()
        at = self.screen()
        at.radio(key="dl_guard_run_mode").set_value(LOCAL).run(timeout=20)
        self.assertFalse(at.exception)
        self.assertFalse(self.audit_db.exists())
        self.enter_local(at, sha)
        at.button(key="dl_guard_local_run").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(self.audit_db.is_file())
        self.assertTrue(GuardAuditStore(self.audit_db).verify_chain())
        self.assertTrue(GuardReviewStore(self.audit_db).verify_reviews())
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "HOLD"
                            for m in at.metric))
        with sqlite3.connect(self.audit_db) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM guard_audit_events").fetchone()[0], 1)
            audit = conn.execute(
                "SELECT payload_json FROM guard_audit_events").fetchone()[0]
        self.assertNotIn("Revenue 100", audit)

    def test_bad_local_sha_fails_closed_without_creating_audit(self):
        self.make_dl()
        at = self.screen()
        at.radio(key="dl_guard_run_mode").set_value(LOCAL).run(timeout=20)
        self.enter_local(at, "e" * 64)
        at.button(key="dl_guard_local_run").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertFalse(self.audit_db.exists())
        self.assertTrue(any("검증 실패" in x.value for x in at.error))
        self.assertFalse(any(m.label == "Guard 판정" for m in at.metric))

    def test_forged_trust_flags_not_displayed(self):
        good = run_synthetic_demo()["report"]
        self.assertTrue(_safe_report(good))
        for field, value in (
            ("trade_executed", True),
            ("live_api_called", True),
            ("official_contest_submission", True),
        ):
            with self.subTest(field=field):
                self.assertFalse(_safe_report({**good, field: value}))
        mutated = {**good, "guard": {**good["guard"], "decision": "APPROVE"}}
        self.assertFalse(_safe_report(mutated))


if __name__ == "__main__":
    unittest.main()
