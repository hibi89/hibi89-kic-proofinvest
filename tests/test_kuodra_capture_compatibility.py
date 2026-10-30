"""P19 offline ZIP acceptance diagnostics, no accidental source/audit disclosure."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import synthetic_companyfacts, synthetic_submissions
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_capture_compatibility import (
    inspect_saved_capture_compatibility, main,
)
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods
from proofinvest.sec_companyfacts import TAG
from test_ixbrl_revenue_review import xhtml
from test_kuodra_offline_preflight import make_zip


class SavedCaptureCompatibilityTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(prefix="kuodra-p19-")
        self.addCleanup(holder.cleanup)
        self.dir = Path(holder.name)
        self.zip = self.dir / "source.zip"
        self.db = self.dir / "audit.sqlite"
        make_zip(self.zip)

    def examine(self):
        return inspect_saved_capture_compatibility(self.zip)

    def test_verified_bundle_read_only_no_original_disclosure(self):
        original = self.zip.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as net:
            report = self.examine()
        net.assert_not_called()
        self.assertEqual(report["status"], "operator_review_required")
        self.assertEqual(report["fiscal_pair_count"], 1)
        self.assertEqual(report["period_checks"][0]["revenue_concept"], TAG)
        self.assertTrue(report["original_strict_utf8"])
        self.assertGreaterEqual(report["locally_verified_candidate_count"], 1)
        self.assertFalse(report["text_candidates_disclosed"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["audit_written"])
        self.assertEqual(report["network_calls"], 0)
        self.assertEqual(original, self.zip.read_bytes())
        self.assertFalse(self.db.exists())
        self.assertNotIn(PHRASE, json.dumps(report))
        self.assertEqual(sorted(self.dir.iterdir()), [self.zip])

    def test_inline_xbrl_optional_not_entire_filing_denial(self):
        report = self.examine()
        inline = report["period_checks"][0]
        self.assertEqual(inline["inline_xbrl_structural_status"], "unavailable")
        self.assertTrue(inline["inline_xbrl_not_required_for_operator_selection"])
        self.assertEqual(report["status"], "operator_review_required")

    def test_strict_xhtml_inline_context_review_has_its_own_signal(self):
        self.zip.unlink()
        make_zip(self.zip, original=xhtml())
        report = self.examine()
        self.assertEqual(report["status"], "operator_review_required")
        self.assertEqual(
            report["period_checks"][0]["inline_xbrl_structural_status"],
            "local_ixbrl_revenue_context_match_unverified",
        )
        self.assertFalse(report["financial_facts_authenticated"])

    def test_selected_revenues_alternative_preserved_without_tag_confusion(self):
        facts = synthetic_companyfacts()
        gaap = facts["facts"]["us-gaap"]
        gaap["Revenues"] = gaap.pop(TAG)
        self.zip.unlink()
        make_zip(self.zip, facts=facts, original=xhtml().replace(
            TAG.encode(), b"Revenues"
        ))
        report = self.examine()
        self.assertEqual(report["status"], "operator_review_required")
        self.assertEqual(report["period_checks"][0]["revenue_concept"], "Revenues")
        self.assertEqual(
            report["period_checks"][0]["inline_xbrl_structural_status"],
            "local_ixbrl_revenue_context_match_unverified",
        )

    def test_non_utf8_original_blocks_source_quote_but_keeps_period_signal(self):
        self.zip.unlink()
        make_zip(self.zip, original=b"<html><p>\xff PUBLIC </p></html>")
        report = self.examine()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"],
                         "ORIGINAL_NOT_STRICT_UTF8_FOR_SOURCE_ANCHOR")
        self.assertEqual(report["fiscal_pair_count"], 1)
        self.assertEqual(report["locally_verified_candidate_count"], 0)
        self.assertFalse(report["original_strict_utf8"])
        self.assertFalse(self.db.exists())

    def test_no_suggested_snippet_does_not_auto_accept_or_reject_period(self):
        self.zip.unlink()
        make_zip(self.zip, original=b"<html><body><p>x</p></body></html>")
        report = self.examine()
        self.assertEqual(report["status"], "operator_review_required")
        self.assertEqual(report["locally_verified_candidate_count"], 0)
        self.assertTrue(report["operator_selection_required"])
        self.assertFalse(report["automatic_execution"])

    def test_corrupt_zip_fails_closed_without_source_identifiers(self):
        corrupt = bytearray(self.zip.read_bytes())
        corrupt[0] ^= 1
        self.zip.write_bytes(corrupt)
        report = self.examine()
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "CAPTURE_ZIP_UNVERIFIABLE")
        self.assertIsNone(report["source_sha256"])
        self.assertEqual(report["period_checks"], [])

    def test_missing_fiscal_periods_fail_closed(self):
        data = synthetic_companyfacts()
        rows = data["facts"]["us-gaap"][TAG]["units"]["USD"]
        data["facts"]["us-gaap"][TAG]["units"]["USD"] = rows[:1]
        self.zip.unlink()
        make_zip(self.zip, facts=data)
        report = self.examine()
        self.assertEqual(report["status"], "blocked")
        self.assertIn(report["reason_code"],
                      ("NO_CONSECUTIVE_ANNUAL_PERIODS", "NO_VERIFIABLE_REVENUE_PERIOD_PAIR"))

    def test_zip_swap_between_preflight_and_recheck_is_blocked(self):
        original_inspect = inspect_saved_capture_periods
        def switch(path):
            report = original_inspect(path)
            self.zip.unlink()
            make_zip(self.zip, original=SYNTHETIC_HTML + b"<!-- changed -->")
            return report
        with patch("proofinvest.kuodra_capture_compatibility.inspect_saved_capture_periods",
                   side_effect=switch):
            result = self.examine()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason_code"], "CAPTURE_CHANGED_SINCE_PREFLIGHT")
        self.assertFalse(self.db.exists())

    def test_candidate_needle_never_in_json_stdout(self):
        output = io.StringIO()
        with redirect_stdout(output):
            rc = main(["--capture-zip", str(self.zip)])
        report = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(report["status"], "operator_review_required")
        self.assertNotIn("TEST_LITERAL_SOURCE_SPAN", output.getvalue())
        self.assertFalse(self.db.exists())

    def test_invalid_path_types_are_not_executed(self):
        for value in (None, 42, {}, [], ""):
            with self.subTest(value=value):
                result = inspect_saved_capture_compatibility(value)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason_code"], "INVALID_LOCAL_CAPTURE_PATH")

    def test_missing_file_cli_returns_failure_code(self):
        with redirect_stdout(io.StringIO()) as output:
            rc = main(["--capture-zip", str(self.dir / "missing.zip")])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
