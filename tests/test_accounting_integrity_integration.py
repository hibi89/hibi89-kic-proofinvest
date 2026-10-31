"""P43 SEC-shaped 3-file -> Engine B -> Guard -> SQLite -> escaped HTML regression."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from test_accounting_integrity import fixture


class AccountingIntegrityIntegrationTests(unittest.TestCase):
    def _run(self, companyfacts, db):
        raw = json.dumps(companyfacts, sort_keys=True).encode()
        pins = {
            "submissions": hashlib.sha256(synthetic_submissions()).hexdigest(),
            "companyfacts": hashlib.sha256(raw).hexdigest(),
            "original_filing": hashlib.sha256(SYNTHETIC_HTML).hexdigest(),
        }
        return review_local_sec_with_guard(
            submissions_json=synthetic_submissions(),
            companyfacts_json=raw, original_filing=SYNTHETIC_HTML,
            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE, audit_db_path=db, run_id="p43-integrity-case",
            expected_source_sha256=pins,
        )

    def test_guard_unchanged_integrity_card_and_html_escaped(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p43-") as home:
            db = Path(home) / "audit.sqlite"
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_PROVIDER_CALL")) as network:
                report = self._run(fixture(), db)
            network.assert_not_called()
            self.assertTrue(GuardAuditStore(db).verify_chain())
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertEqual(report["accounting_integrity"]["status"], "reviewed_unverified")
            self.assertEqual(report["accounting_integrity"]["earnings_less_cash_usd"], "40")
            self.assertFalse(report["accounting_integrity"]["guard_policy_modified"])
            self.assertFalse(report["limits"]["trade_executed"])
            html = render_local_sec_html(report).decode("utf-8")
            self.assertIn("Engine B", html)
            self.assertIn("순이익 - 영업현금흐름", html)
            self.assertIn("매출채권 성장률", html)
            self.assertIn("회계 부정의 증거가 아닙니다", html)

    def test_missing_net_income_does_not_change_valid_guard(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p43-") as home:
            report = self._run(fixture(ni=None), Path(home) / "audit.sqlite")
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertEqual(report["accounting_integrity"]["status"], "unavailable")
            self.assertIn("NOT_AVAILABLE", render_local_sec_html(report).decode("utf-8"))

    def test_html_refuses_maliciously_swapped_companyfacts_pin(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p43-") as home:
            report = self._run(fixture(), Path(home) / "audit.sqlite")
            report["accounting_integrity"]["companyfacts_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "HTML_ACCOUNTING_TRUST_CONTRACT"):
                render_local_sec_html(report)

    def test_untrusted_card_cannot_claim_proven_fraud(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p43-") as home:
            report = self._run(fixture(), Path(home) / "audit.sqlite")
            report["accounting_integrity"]["accounting_fraud_proven"] = True
            with self.assertRaisesRegex(ValueError, "HTML_ACCOUNTING_TRUST_CONTRACT"):
                render_local_sec_html(report)


if __name__ == "__main__":
    unittest.main()
