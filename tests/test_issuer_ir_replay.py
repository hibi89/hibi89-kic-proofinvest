"""Deterministic regression against historical transcribed issuer-IR facts."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from proofinvest import issuer_ir_replay as ir


class IssuerIrReplayTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(ir.EVIDENCE_PATH.read_text(encoding="utf-8"))

    def _run_modified(self, record, claim="114.20"):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "issuer.json"
            p.write_text(json.dumps(record), encoding="utf-8")
            return ir.replay(claim, p)

    def test_actual_issuer_release_arithmetic_and_hold(self):
        result = ir.replay()
        self.assertEqual(result["arithmetic_state"], "verified")
        self.assertEqual(result["metrics"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(result["metrics"]["fy2025_cash_conversion_pct"], "87.94")
        self.assertEqual(result["guard_decision"], "HOLD")
        self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_wrong_claim_detected(self):
        self.assertEqual(ir.replay("140")["arithmetic_state"], "conflict")

    def test_invalid_nonfinite_claim_unavailable(self):
        for c in ("abc", "NaN", "Infinity", "1e9999"):
            with self.subTest(c=c):
                self.assertEqual(ir.replay(c)["arithmetic_state"], "unavailable")

    def test_source_metadata_tamper_fails_closed(self):
        for key, value in (("ticker", "AMD"), ("source_url", "https://example.com"),
                           ("publication_date", "2026-01-01"), ("basis", "NON_GAAP")):
            with self.subTest(key=key):
                x = copy.deepcopy(self.record)
                x[key] = value
                self.assertEqual(self._run_modified(x)["arithmetic_state"], "unavailable")

    def test_period_or_unit_corruption_fails_closed(self):
        for key, value in (("fiscal_end", "2025-12-31"), ("revenue", "NaN"),
                           ("net_income", "0"), ("operating_cash_flow", "-1")):
            with self.subTest(key=key):
                x = copy.deepcopy(self.record)
                x["periods"]["FY2025"][key] = value
                self.assertEqual(self._run_modified(x)["arithmetic_state"], "unavailable")

    def test_modified_financial_amount_never_self_verifies(self):
        x = copy.deepcopy(self.record)
        x["periods"]["FY2025"]["revenue"] = "140000"
        self.assertEqual(self._run_modified(x, "129.80")["arithmetic_state"], "unavailable")

    def test_source_claim_never_authenticates(self):
        r = ir.replay()
        for key in ("sec_accessed", "source_authenticated", "rights_to_redistribute_verified",
                    "original_filing_verified", "full_engine_abc_executed", "ai_agent_executed",
                    "trade_executed", "risk_of_misconduct_concluded"):
            self.assertIs(r[key], False)
        self.assertEqual(r["external_network_requests"], 0)

    def test_cli_no_network_run(self):
        p = subprocess.run([sys.executable, "-B", "-m", "proofinvest.issuer_ir_replay"],
                           text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(p.stdout)["arithmetic_state"], "verified")

    def test_missing_evidence_unavailable(self):
        self.assertEqual(ir.replay(evidence_path=Path("/does-not-exist"))["arithmetic_state"], "unavailable")


if __name__ == "__main__":
    unittest.main()
