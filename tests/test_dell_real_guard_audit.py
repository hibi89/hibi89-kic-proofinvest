"""P208 real Dell financial observation -> no-approval Guard -> SQLite audit."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest import dell_real_guard_audit as p
from proofinvest import dell_working_capital_review as source
from proofinvest.guard_audit import GuardAuditStore

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class P208ActualGuardAuditTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"actual-review.sqlite"

    def run_case(self, **kwargs):
        return p.run_real_issuer_guard_audit(
            run_id="P208-review-1",audit_db_path=self.path,
            source_receipt=source.actual_working_capital_receipt(), **kwargs,
        )

    def test_explicit_consent_required_no_sqlite_side_effect(self):
        out=self.run_case()
        self.assertEqual(out["status"],"BLOCKED")
        self.assertEqual(out["reason_code"],"EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
        self.assertFalse(self.path.exists())
        self.assertFalse(out["trade_executed"])

    def test_real_derived_signal_guard_hold_sqlite_hashed_chain(self):
        out=self.run_case(acknowledge_local_persistence=True)
        self.assertEqual(out["status"],"REAL_SOURCE_ENGINE_B_GUARD_HOLD_AUDIT_RECORDED")
        self.assertTrue(out["audit_written"])
        self.assertTrue(self.path.exists())
        self.assertTrue(out["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.path).verify_chain())
        report=out["report"]
        self.assertEqual(report["guard"]["decision"],"HOLD")
        self.assertEqual(report["guard"]["reason_codes"],["CLAIM_UNAVAILABLE","RISK_UNAVAILABLE"])
        self.assertEqual(len(report["financial_evidence_sha256"]),64)
        self.assertEqual(report["source_sha256"],source.actual_working_capital_receipt()["source_sha256"])
        self.assertFalse(report["source_rights_verified"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["trade_executed"])
        self.assertEqual(out["network_requests"],0)

    def test_idempotent_replay_rejects_source_mutation_and_detects_tamper(self):
        first=self.run_case(acknowledge_local_persistence=True)
        second=self.run_case(acknowledge_local_persistence=True)
        self.assertEqual(first["report"]["audit"]["event_hash"],second["report"]["audit"]["event_hash"])
        self.assertFalse(first["report"]["audit"]["replayed"])
        self.assertTrue(second["report"]["audit"]["replayed"])
        tampered=source.actual_working_capital_receipt()
        tampered["receivables_usd_millions"]=("999999","1")
        bad=p.run_real_issuer_guard_audit(
            run_id="P208-other",audit_db_path=self.path,
            source_receipt=tampered,acknowledge_local_persistence=True,
        )
        self.assertEqual(bad["status"],"BLOCKED")
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM guard_run_registry").fetchone()[0],1)
            con.execute("UPDATE guard_audit_events SET payload_json='{}'")
        self.assertFalse(GuardAuditStore(self.path).verify_chain())
        denied=p.run_real_issuer_guard_audit(
            run_id="P208-new",audit_db_path=self.path,
            source_receipt=source.actual_working_capital_receipt(),
            acknowledge_local_persistence=True,
        )
        self.assertEqual(denied["status"],"BLOCKED")
        self.assertIsNone(denied["audit_written"])

    def test_unsafe_path_and_missing_source_never_created(self):
        bad=p.run_real_issuer_guard_audit(
            run_id="../unsafe",audit_db_path=self.path,
            source_receipt=source.actual_working_capital_receipt(),
            acknowledge_local_persistence=True,
        )
        self.assertEqual(bad["reason_code"],"INVALID_AUDIT_RUN_ID")
        bad=p.run_real_issuer_guard_audit(
            run_id="P208-missing",audit_db_path=self.path,
            source_receipt={"status":"FAKE"},
            acknowledge_local_persistence=True,
        )
        self.assertEqual(bad["status"],"BLOCKED")
        self.assertFalse(self.path.exists())

    def test_cli_explicit_flag_without_any_external_request(self):
        base=[sys.executable,"-B","-m","proofinvest.dell_real_guard_audit",
              "--run-id","P208-cli","--audit-db",str(self.path)]
        no=subprocess.run(base,cwd=_APP.parent,capture_output=True,text=True,timeout=20)
        self.assertEqual(no.returncode,2,no.stderr)
        self.assertFalse(self.path.exists())
        ok=subprocess.run(base+["--acknowledge-local-audit-persistence"],
                          cwd=_APP.parent,capture_output=True,text=True,timeout=20)
        self.assertEqual(ok.returncode,0,ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["report"]["guard"]["decision"],"HOLD")
        self.assertTrue(GuardAuditStore(self.path).verify_chain())

    def test_actual_ui_requires_click_and_no_background_disk_writes(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception,[str(x.message) for x in at.exception])
        consent=next(x for x in at.checkbox if x.key=="p208_local_audit_ack")
        button=next(x for x in at.button if x.key=="p208_run_once")
        self.assertFalse(consent.value)
        self.assertTrue(button.disabled)
        consent.set_value(True).run(timeout=25)
        button=next(x for x in at.button if x.key=="p208_run_once")
        self.assertFalse(button.disabled)
        button.click().run(timeout=25)
        self.assertFalse(at.exception,[str(x.message) for x in at.exception])
        self.assertTrue(any("실자료 감사 체인 검증 완료" in x.value for x in at.success))
        self.assertTrue(any("HOLD" in x.value for x in at.success))

    def test_untrusted_p207_source_never_allows_audit_ui_success(self):
        from streamlit.testing.v1 import AppTest
        at=AppTest.from_file(str(_APP)).run(timeout=25)
        with patch.object(source,"review_real_working_capital",
                          return_value={"status":"BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=25)
            consent=next(x for x in at.checkbox if x.key=="p208_local_audit_ack")
            consent.set_value(True).run(timeout=25)
            self.assertTrue(next(x for x in at.button if x.key=="p208_run_once").disabled)
            next(x for x in at.button if x.key=="p208_run_once").click().run(timeout=25)
        self.assertFalse(at.exception)
        self.assertFalse(any("실자료 감사 체인 검증 완료" in x.value for x in at.success))


if __name__=="__main__":
    unittest.main()
