"""Click-through Streamlit Guard persistence tests; offline AppTest, no browser/API.

Exercise the *actual* Streamlit controls with an isolated HOME so tests
never write the user's Guard database. No mock of the Guard pipeline.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SEC_MODE = "Apple SEC 10-K 수동 발췌 — 오프라인 검산 (2025/2024)"


def _sec_app() -> AppTest:
    at = AppTest.from_file(str(APP)).run(timeout=15)
    at.selectbox[0].set_value(SEC_MODE).run(timeout=15)
    assert not at.exception, [str(x.message) for x in at.exception]
    return at


class GuardStreamlitClickthroughTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kic-guard-ui-")
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        env = patch.dict(os.environ, {"HOME": str(home)})
        env.start()
        self.addCleanup(env.stop)
        self.db = home / ".proofinvest-guard" / "audit.sqlite"

    def test_explicit_audit_click_is_idempotent_and_history_is_visible(self):
        at = _sec_app()
        self.assertFalse(self.db.exists(), "Opening view must not persist data")
        self.assertTrue(any(m.label == "정책 판정" and m.value == "HOLD"
                            for m in at.metric))

        at.button(key="guard_sec_record").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(self.db.is_file())
        self.assertTrue(any("로컬 감사 기록 저장 완료" in x.value for x in at.success))
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0], 1)

        at.button(key="guard_sec_record").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("중복 저장 없음" in x.value for x in at.success))
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0], 1)

        at.button(key="guard_audit_history").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("감사 체인 검증 통과" in x.value for x in at.success))
        self.assertTrue(GuardReviewStore(self.db).verify_reviews())

    def test_explicit_review_acknowledgement_persists_separately(self):
        at = _sec_app()
        self.assertFalse(self.db.exists())
        at.text_input(key="guard_reviewer").set_value("test-human").run(timeout=15)
        at.text_area(key="guard_review_reason").set_value("Reviewed local-only SEC excerpt").run(timeout=15)
        at.button(key="guard_review_save").click().run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("모의 검토 기록 저장 완료" in x.value for x in at.success))
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertTrue(GuardReviewStore(self.db).verify_reviews())
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM guard_audit_events").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM guard_human_reviews").fetchone()[0], 1)
            action, reviewer = conn.execute(
                "SELECT action, reviewer FROM guard_human_reviews"
            ).fetchone()
        self.assertEqual((action, reviewer), ("ACKNOWLEDGE", "test-human"))
        self.assertFalse(any("AUTHORIZE_SIMULATION" in str(x.value)
                             for x in at.success))

    def test_invalid_review_and_conflicting_claim_do_not_auto_approve(self):
        at = _sec_app()
        at.selectbox[2].set_value("30% — 불일치 주장").run(timeout=15)
        self.assertTrue(any(m.label == "정책 판정" and m.value == "REJECT"
                            for m in at.metric))
        self.assertFalse(self.db.exists())
        at.text_input(key="guard_reviewer").set_value("test-human").run(timeout=15)
        at.text_area(key="guard_review_reason").set_value("bad").run(timeout=15)
        at.button(key="guard_review_save").click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertTrue(any("검토 기록 저장 실패" in x.value for x in at.error))
        self.assertFalse(self.db.exists(), "Invalid review must not create audit")
        self.assertFalse(any("모의 검토 기록 저장 완료" in x.value for x in at.success))


if __name__ == "__main__":
    unittest.main()
