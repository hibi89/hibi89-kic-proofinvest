"""Synthetic-only full backend judge demo, no outside provider calls."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from proofinvest.kic_full_backend_demo import main, run_synthetic_full_backend


class SyntheticFullBackendTests(unittest.TestCase):
    def test_complete_offline_two_decisions_and_verified_audit(self):
        result = run_synthetic_full_backend()
        self.assertEqual(result["schema"], "proofinvest.synthetic-full-backend-e2e.v1")
        self.assertEqual(result["status"], "synthetic_offline_backend_e2e_pass")
        self.assertEqual(result["audited_run_count"], 2)
        self.assertEqual([x["guard_decision"] for x in result["scenarios"]],
                         ["HOLD", "REJECT"])
        self.assertEqual([x["verification_status"] for x in result["scenarios"]],
                         ["calculated_unverified", "conflict"])
        self.assertTrue(result["audit_chain_verified"])
        self.assertTrue(result["human_review_integrity_verified"])
        self.assertTrue(result["temporary_databases_discarded"])
        self.assertTrue(result["synthetic_only"])
        self.assertEqual(result["real_sec_http_requests"], 0)
        self.assertEqual(result["models_trained"], 0)
        self.assertFalse(result["trade_executed"])
        self.assertFalse(result["official_contest_submission"])
        self.assertFalse(result["external_source_authenticated"])

    def test_non_network_and_no_secret_source_text_leakage(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO NETWORK")) as opener:
            result = run_synthetic_full_backend()
        opener.assert_not_called()
        text = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("<script>", text)
        self.assertNotIn("TEST_LITERAL_SOURCE_SPAN", text)
        self.assertNotIn("PRIVATE", text)
        self.assertFalse(any(s["source_authenticated"] for s in result["scenarios"]))
        self.assertFalse(any(s["trade_executed"] for s in result["scenarios"]))

    def test_json_cli_contains_machine_checkable_full_path(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = main(["--format", "json"])
        self.assertEqual(status, 0)
        self.assertEqual(err.getvalue(), "")
        obj = json.loads(out.getvalue())
        self.assertEqual([x["guard_decision"] for x in obj["scenarios"]],
                         ["HOLD", "REJECT"])
        self.assertEqual(obj["real_sec_http_requests"], 0)

    def test_markdown_cli_redacts_untrusted_filing_and_reports_both(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(["--format", "markdown"])
        self.assertEqual(status, 0)
        self.assertIn("SYNTHETIC ONLY", out.getvalue())
        self.assertIn("**HOLD**", out.getvalue())
        self.assertIn("**REJECT**", out.getvalue())
        self.assertNotIn("<script>", out.getvalue())
        self.assertNotIn("TEST_LITERAL_SOURCE_SPAN", out.getvalue())


if __name__ == "__main__":
    unittest.main()
