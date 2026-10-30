"""Offline HTML reporting for genuine local files: no HTML injection or overwrite."""
from __future__ import annotations
import contextlib
from io import StringIO
import json
import tempfile
import unittest
from pathlib import Path

from proofinvest.local_sec_guard_report import main, review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from tests.test_local_sec_guard_report import fixture


class LocalSecHtmlReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kic-html-e2e-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_complete_real_offline_guard_rendered_as_safe_local_html(self):
        report = review_local_sec_with_guard(**fixture(self.root / "audit.sqlite"))
        html = render_local_sec_html(report).decode("utf-8")
        self.assertIn("ProofInvest | OFFLINE UNVERIFIED Review", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("HOLD", html)
        self.assertIn(report["audit"]["event_hash"], html)
        self.assertIn(report["source"]["submissions_sha256"], html)
        self.assertIn("UNVERIFIED LOCAL FILES", html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_escapes_untrusted_reason_text_and_refuses_trust_escalation(self):
        report = review_local_sec_with_guard(**fixture(self.root / "audit.sqlite"))
        injected = '<img src=x onerror="alert(1)">'
        report["risk"]["reason_codes"].append(injected)
        html = render_local_sec_html(report).decode("utf-8")
        self.assertIn("&lt;img", html)
        self.assertNotIn(injected, html)
        report["limits"]["external_source_authenticated"] = True
        with self.assertRaises(ValueError):
            render_local_sec_html(report)

    def test_conflicting_claim_is_reported_as_reject_not_approve(self):
        args = fixture(self.root / "audit.sqlite")
        args["claimed_growth_pct"] = "300.00"
        result = review_local_sec_with_guard(**args)
        self.assertEqual(result["guard"]["decision"], "REJECT")
        page = render_local_sec_html(result).decode("utf-8")
        self.assertIn('class="state reject"', page)
        self.assertIn("GROWTH_CLAIM_CONFLICT", page)

    def test_cli_creates_new_html_and_does_not_overwrite_old_one(self):
        data = fixture(self.root / "audit.sqlite")
        names = {}
        for name in ("submissions_json", "companyfacts_json", "original_filing"):
            target = self.root / (name + ".input")
            target.write_bytes(data[name])
            names[name] = target
        target_html = self.root / "review.html"
        args = [
            "--submissions-json", str(names["submissions_json"]),
            "--companyfacts-json", str(names["companyfacts_json"]),
            "--original-file", str(names["original_filing"]),
            "--cik", data["cik"], "--accession", data["accession"],
            "--as-of", data["as_of"], "--collected-at", data["collected_at"],
            "--current-end", data["current_end"], "--prior-end", data["prior_end"],
            "--needle", data["needle"],
            "--claimed-growth-pct", data["claimed_growth_pct"],
            "--run-id", data["run_id"], "--audit-db", str(data["audit_db_path"]),
            "--acknowledge-local-audit-persistence",
            "--report-html", str(target_html),
        ]
        with contextlib.redirect_stdout(StringIO()) as out:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["guard"]["decision"], "HOLD")
        saved = target_html.read_bytes()
        self.assertTrue(saved.startswith(b"<!doctype html>"))
        with self.assertRaises(SystemExit) as context:
            main(args)
        self.assertEqual(context.exception.code, 2)
        self.assertEqual(target_html.read_bytes(), saved)

    def test_rejects_corrupted_audit_without_html(self):
        report = review_local_sec_with_guard(**fixture(self.root / "audit.sqlite"))
        report["audit_chain_valid"] = False
        with self.assertRaises(ValueError):
            render_local_sec_html(report)


if __name__ == "__main__":
    unittest.main()
