"""P231: a genuinely replayed A/B/C source packet→real Guard HOLD→SQLite."""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.real_issuer_local_market import review_real_issuer_local_market_pair
from proofinvest.real_issuer_abc_local_review import build_partial_source_bound_abc
from proofinvest.real_issuer_abc_guard_audit import run_source_bound_abc_hold_audit

_MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


def daily(symbol: str, base: int) -> bytes:
    day=date(2026,8,18)
    rows={}
    i=0
    while day<=date(2026,11,4):
        if day.weekday()<5:
            rows[day.isoformat()]={"4. close":str(base+i*2+(i%5)*3)}
            i+=1
        day+=timedelta(days=1)
    return json.dumps({
        "Meta Data":{"2. Symbol":symbol}, "Time Series (Daily)":rows,
    }).encode()


def joined(stock_base:int=120):
    ab=review_real_issuer_local_market_pair(
        ticker="NVDA",stock_json=daily("NVDA",stock_base),
        ndx_json=daily("NDX",10000))
    return build_partial_source_bound_abc(ab_review=ab)


class ABCGuardHoldSQLiteTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix="kuodra-p231-")
        self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/"partial-abc-audit.sqlite3"

    def test_denied_preconsent_never_creates_database(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("FORBID_EXTERNAL_HTTP")) as network:
            result=run_source_bound_abc_hold_audit(
                abc_review=joined(),audit_db_path=self.path)
            network.assert_not_called()
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason_code"],
                         "EXPLICIT_LOCAL_SQLITE_PERSISTENCE_CONSENT_REQUIRED")
        self.assertFalse(self.path.exists())

    def test_true_publisher_source_bound_untrusted_market_and_peers_to_hold(self):
        packet=joined()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_OUTBOUND_HTTP")) as net:
            result=run_source_bound_abc_hold_audit(
                abc_review=packet,audit_db_path=self.path,
                acknowledge_local_persistence=True)
            net.assert_not_called()
        self.assertEqual(result["status"],
                         "PARTIAL_SOURCE_BOUND_ABC_GUARD_HOLD_AUDIT_RECORDED",result)
        self.assertTrue(result["audit_written"])
        self.assertTrue(result["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.path).verify_chain())
        report=result["report"]
        self.assertEqual(report["guard"]["decision"],"HOLD")
        self.assertEqual(report["guard"]["reason_codes"],
                         ["CLAIM_UNAVAILABLE","RISK_UNAVAILABLE"])
        self.assertEqual(report["source_bound_abc_digest"],packet["derived_sha256"])
        self.assertEqual(report["issuer_source_sha256"],
                         packet["source_linked_issuer_sha256"])
        self.assertTrue(report["run_id"].startswith("p231_"))
        for key in ("market_rights_verified","peer_rights_verified",
                    "full_abc_complete","external_sharing_allowed","trade_executed"):
            self.assertFalse(report[key],key)
        self.assertFalse(result["trade_executed"])
        self.assertEqual(result["network_requests"],0)
        with closing(sqlite3.connect(self.path)) as db, db:
            stored=db.execute("SELECT payload_json FROM guard_audit_events").fetchone()[0]
        self.assertNotIn("Time Series (Daily)",stored)
        self.assertNotIn("4. close",stored)
        self.assertNotIn("api_key",stored.lower())
        self.assertNotIn("raw_html",stored.lower())

    def test_exact_same_abc_idempotent_changed_market_creates_second_event(self):
        one=joined()
        first=run_source_bound_abc_hold_audit(
            abc_review=one,audit_db_path=self.path,
            acknowledge_local_persistence=True)
        second=run_source_bound_abc_hold_audit(
            abc_review=deepcopy(one),audit_db_path=self.path,
            acknowledge_local_persistence=True)
        other=joined(140)
        self.assertNotEqual(one["derived_sha256"],other["derived_sha256"])
        third=run_source_bound_abc_hold_audit(
            abc_review=other,audit_db_path=self.path,
            acknowledge_local_persistence=True)
        self.assertEqual([x["status"] for x in (first,second,third)],
                         ["PARTIAL_SOURCE_BOUND_ABC_GUARD_HOLD_AUDIT_RECORDED"]*3)
        self.assertFalse(first["report"]["audit"]["replayed"])
        self.assertTrue(second["report"]["audit"]["replayed"])
        self.assertFalse(third["report"]["audit"]["replayed"])
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM guard_audit_events").fetchone()[0],2)
        self.assertTrue(GuardAuditStore(self.path).verify_chain())

    def test_forged_source_rights_and_derived_amount_block_no_write(self):
        packet=joined()
        for key,value in (
            ("ticker","AAPL"),
            ("market_rights_verified",True),
            ("peer_rights_verified",True),
            ("source_linked_issuer_sha256","f"*64),
            ("derived_sha256","0"*64),
        ):
            with self.subTest(key=key):
                fake=deepcopy(packet);fake[key]=value
                result=run_source_bound_abc_hold_audit(
                    abc_review=fake,audit_db_path=self.path,
                    acknowledge_local_persistence=True)
                self.assertEqual(result["status"],"BLOCKED")
                self.assertFalse(self.path.exists())

    def test_corrupt_ledger_blocks_further_records(self):
        first=run_source_bound_abc_hold_audit(
            abc_review=joined(),audit_db_path=self.path,
            acknowledge_local_persistence=True)
        self.assertTrue(first["audit_chain_valid"])
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE guard_audit_events SET payload_json='{}'")
        self.assertFalse(GuardAuditStore(self.path).verify_chain())
        denied=run_source_bound_abc_hold_audit(
            abc_review=joined(140),audit_db_path=self.path,
            acknowledge_local_persistence=True)
        self.assertEqual(denied["status"],"BLOCKED")
        self.assertIsNone(denied["audit_written"])

    def test_invalid_audit_path_no_artifact_created(self):
        packet=joined()
        denied=run_source_bound_abc_hold_audit(
            abc_review=packet,audit_db_path=self.path.parent/"no-such"/"x.sqlite",
            acknowledge_local_persistence=True)
        self.assertEqual(denied["status"],"BLOCKED")
        self.assertFalse(self.path.exists())

    def test_native_streamlit_has_separate_explicit_persistence_consent(self):
        from streamlit.testing.v1 import AppTest
        app=Path(__file__).resolve().parents[1]/"streamlit_app.py"
        with patch("proofinvest.kuodra_local_workspace_ui.local_workspace_enabled",
                   return_value=True):
            at=AppTest.from_file(str(app)).run(timeout=30)
            at.selectbox[0].set_value(_MODE).run(timeout=30)
            next(x for x in at.text_input
                 if x.key=="p218_real_issuer_input").set_value("NVDA").run(timeout=30)
            self.assertFalse(at.exception,[str(x.message) for x in at.exception])
            box=next(x for x in at.checkbox if x.key=="p231_local_audit_ack")
            self.assertFalse(box.value)
            self.assertTrue(any(x.key=="p231_local_audit_run" for x in at.button))
            self.assertFalse(any("A/B/C 출처결합 Guard HOLD SQLite 감사 기록 완료"
                                 in x.value for x in at.success))
