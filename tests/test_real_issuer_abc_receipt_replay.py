"""P232: independently replay downloaded partial A/B/C Guard receipts read-only."""
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from proofinvest.real_issuer_abc_guard_audit import run_source_bound_abc_hold_audit
from proofinvest.real_issuer_abc_local_review import build_partial_source_bound_abc
from proofinvest.real_issuer_abc_receipt_replay import verify_p231_local_receipt
from proofinvest.real_issuer_local_market import review_real_issuer_local_market_pair


def _daily(symbol, base):
    day = date(2026, 8, 18)
    rows = {}
    i = 0
    while day <= date(2026, 11, 4):
        if day.weekday() < 5:
            rows[day.isoformat()] = {"4. close": str(base + i * 2 + (i % 5) * 3)}
            i += 1
        day += timedelta(days=1)
    return json.dumps({
        "Meta Data": {"2. Symbol": symbol}, "Time Series (Daily)": rows,
    }).encode()


def _packet(stock_base=120):
    return build_partial_source_bound_abc(ab_review=review_real_issuer_local_market_pair(
        ticker="NVDA", stock_json=_daily("NVDA", stock_base),
        ndx_json=_daily("NDX", 10000),
    ))


class LocalP231ReceiptReplayTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(prefix="kuodra-p232-")
        self.addCleanup(d.cleanup)
        self.db = Path(d.name) / "audited.sqlite"
        self.packet = _packet()
        produced = run_source_bound_abc_hold_audit(
            abc_review=self.packet, audit_db_path=self.db,
            acknowledge_local_persistence=True,
        )
        self.assertEqual(produced["status"],
                         "PARTIAL_SOURCE_BOUND_ABC_GUARD_HOLD_AUDIT_RECORDED",
                         produced)
        self.receipt = produced["report"]

    def replay(self, packet=None, receipt=None, path=None):
        return verify_p231_local_receipt(
            abc_review=self.packet if packet is None else packet,
            receipt=self.receipt if receipt is None else receipt,
            audit_db_path=self.db if path is None else path,
        )

    def test_real_sqlite_event_and_source_match_readonly(self):
        before = sha256(self.db.read_bytes()).hexdigest()
        x = self.replay()
        self.assertEqual(x["status"], "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY", x)
        self.assertTrue(x["local_chain_valid"])
        self.assertTrue(x["receipt_matches_local_source"])
        self.assertFalse(x["market_rights_verified"])
        self.assertFalse(x["source_authenticated_by_sec"])
        self.assertFalse(x["trade_executed"])
        self.assertFalse(x["historical_replayed_flag_attested"])
        self.assertEqual(x["network_requests"], 0)
        self.assertEqual(sha256(self.db.read_bytes()).hexdigest(), before)

    def test_replayed_original_event_still_matches(self):
        again = run_source_bound_abc_hold_audit(
            abc_review=self.packet, audit_db_path=self.db,
            acknowledge_local_persistence=True,
        )
        self.assertTrue(again["report"]["audit"]["replayed"])
        self.assertEqual(self.replay(receipt=again["report"])["status"],
                         "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY")

    def test_changed_source_or_misleading_rights_block(self):
        swapped = self.replay(packet=_packet(140))
        self.assertEqual(swapped["status"], "BLOCKED")
        for key, val in (
            ("redacted_evidence_digest", "f" * 64),
            ("source_bound_abc_digest", "0" * 64),
            ("market_rights_verified", True),
            ("trade_executed", True),
            ("external_sharing_allowed", True),
        ):
            with self.subTest(key=key):
                forgery = deepcopy(self.receipt)
                forgery[key] = val
                self.assertEqual(self.replay(receipt=forgery)["status"], "BLOCKED")

    def test_invalid_event_and_malformed_receipt_block(self):
        for malformed in ([], {}, {"status": "PASS"}, "OK"):
            self.assertEqual(self.replay(receipt=malformed)["status"], "BLOCKED")
        fake = deepcopy(self.receipt)
        fake["audit"]["event_hash"] = "f" * 64
        self.assertEqual(self.replay(receipt=fake)["status"], "BLOCKED")
        fake = deepcopy(self.receipt)
        fake["audit"]["event_id"] = True
        self.assertEqual(self.replay(receipt=fake)["status"], "BLOCKED")

    def test_missing_db_does_not_get_created_and_corruption_rejected(self):
        absent = self.db.with_name("never-create.sqlite")
        self.assertEqual(self.replay(path=absent)["status"], "BLOCKED")
        self.assertFalse(absent.exists())
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE guard_audit_events SET payload_json='{}'")
        invalid = self.replay()
        self.assertEqual(invalid["status"], "BLOCKED")
        self.assertFalse(invalid["local_chain_valid"])

    def test_user_cli_replay_and_fail_closed(self):
        import io
        from contextlib import redirect_stdout
        from scripts.verify_p231_receipt import main
        a = self.db.with_name("abc-review.json")
        b = self.db.with_name("hold-receipt.json")
        a.write_text(json.dumps(self.packet), encoding="utf-8")
        b.write_text(json.dumps(self.receipt), encoding="utf-8")
        args = ["--abc-review", str(a), "--receipt", str(b),
                "--audit-db", str(self.db)]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(args)
        self.assertEqual(exit_code, 0, stdout.getvalue())
        x = json.loads(stdout.getvalue())
        self.assertEqual(x["status"], "VERIFIED_LOCAL_RECEIPT_MATCH_ONLY")
        self.assertNotIn("Time Series (Daily)", stdout.getvalue())
        b.write_text('{"status":"forged"}', encoding="utf-8")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            denied = main(args)
        self.assertEqual(denied, 2)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "BLOCKED")
