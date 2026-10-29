"""Standalone synthetic DL/Guard report demo tests; no provider network."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

from proofinvest.kic_dl_guard_demo import main, run_synthetic_demo


class KicDlGuardDemoTests(unittest.TestCase):
    def test_demo_real_code_paths_and_audit(self):
        result = run_synthetic_demo()
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["database_persisted_after_demo"])
        self.assertFalse(result["real_sec_source_authenticated"])
        report = result["report"]
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertEqual(report["evidence"]["candidate_count"], 1)
        self.assertTrue(report["audit"]["chain_valid"])
        self.assertTrue(report["audit"]["human_review_integrity_valid"])
        self.assertEqual(report["human_review"]["action"], "ACKNOWLEDGE")
        self.assertFalse(report["trade_executed"])
        self.assertFalse(report["live_api_called"])

    def test_cli_json_is_explicitly_synthetic(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = main(["--format", "json"])
        self.assertEqual(status, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["synthetic_only"])
        self.assertFalse(payload["database_persisted_after_demo"])

    def test_cli_markdown_excludes_untrusted_html(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = main(["--format", "markdown"])
        self.assertEqual(status, 0)
        content = stdout.getvalue()
        self.assertIn("SYNTHETIC DEMONSTRATION", content)
        self.assertIn("**HOLD**", content)
        self.assertNotIn("INVISIBLE SYNTHETIC SCRIPT", content)
        self.assertNotIn("Revenue 100 synthetic units", content)


if __name__ == "__main__":
    unittest.main()
