"""No-network, fail-closed tests for a report assembled from canonical KIC/DL."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.evidence_report import (
    build_synthetic_evidence_report, render_report, main,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML
from proofinvest.kic_dl_demo import synthetic_submissions


class OfflineEvidenceReportTests(unittest.TestCase):
    def test_report_is_deterministic_and_preserves_negative_attestations(self):
        a = build_synthetic_evidence_report()
        b = build_synthetic_evidence_report()
        self.assertEqual(a, b)
        self.assertEqual(a["mode"], "SYNTHETIC_FIXTURE_OFFLINE_ONLY")
        self.assertEqual(a["status"], "local_structural_review_only")
        self.assertEqual(a["risk"]["status"], "unavailable")
        self.assertTrue(all(v is False for v in a["authenticity"].values()))

    def test_combines_financial_numbers_and_distinct_provenance_hashes(self):
        report = build_synthetic_evidence_report()
        self.assertEqual(report["financial"]["prior_revenue"], "100")
        self.assertEqual(report["financial"]["current_revenue"], "200")
        self.assertEqual(report["financial"]["growth_pct"], "100.00")
        self.assertEqual(report["financial"]["status"], "calculated_unverified")
        self.assertEqual(report["issuer"]["accession"], "0000000001-25-000001")
        source = report["source"]
        self.assertEqual(source["archived_original_sha256"],
                         hashlib.sha256(SYNTHETIC_HTML).hexdigest())
        self.assertEqual(source["submissions_json_sha256"],
                         hashlib.sha256(synthetic_submissions()).hexdigest())
        self.assertNotEqual(source["archived_original_sha256"],
                            source["submissions_json_sha256"])
        self.assertFalse(source["source_span"]["supports_financial_values"])

    def test_json_and_markdown_exports_warn_of_synthetic_uncertainty(self):
        report = build_synthetic_evidence_report()
        js = render_report(report, "json")
        self.assertEqual(json.loads(js), report)
        md = render_report(report, "markdown")
        self.assertIn("SYNTHETIC / UNVERIFIED", md)
        self.assertIn("USD 200", md)
        self.assertIn("100.00%", md)
        self.assertIn("Risk verdict: unavailable", md)
        self.assertIn("does not authenticate or prove", md)
        self.assertNotIn("<script>", md)
        self.assertNotIn("&lt;script&gt;", md)
        self.assertNotIn("alert(", md)

    def test_no_html_from_original_archive_is_exported(self):
        for fmt in ("json", "markdown"):
            payload = render_report(build_synthetic_evidence_report(), fmt)
            self.assertNotIn("escaped_context", payload)
            self.assertNotIn("alert(", payload)
            self.assertNotIn("<html", payload)
            self.assertNotIn("<script", payload)

    def test_tampered_archive_hash_or_byte_location_is_blocked(self):
        original_path = "proofinvest.evidence_report.replay_original"
        from proofinvest.kic_dl_original_demo import replay_original
        actual = replay_original()
        for mutate in (
            {"original_filing_sha256": "0" * 64},
            {"source_byte_start": 1},
            {"source_byte_end": True},
            {"escaped_context": "<script>attack</script>"},
            {"authenticated_external_source": True},
            {"source_uri": "https://evil.example/filing.htm"},
        ):
            with self.subTest(mutate=mutate):
                with patch(original_path, return_value=dict(actual, **mutate)):
                    with self.assertRaisesRegex(ValueError, "SYNTHETIC_REPORT_BLOCKED"):
                        build_synthetic_evidence_report()

    def test_forged_numeric_status_or_amount_fails_closed(self):
        from proofinvest.sec_companyfacts import verify_sec_annual_revenue
        from proofinvest.kic_dl_demo import (
            AS_OF, SYNTHETIC_CIK, SYNTHETIC_ACCESSION, synthetic_companyfacts,
        )
        real = verify_sec_annual_revenue(
            synthetic_companyfacts(), cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION,
            current_end="2025-09-30", prior_end="2024-09-30",
            as_of=AS_OF, claimed_growth_pct="100.00",
        )
        for altered in ({"current_usd": "999999"}, {"growth_pct": "200.00"},
                        {"status": "verified"}, {"authenticated_external_source": True}):
            with self.subTest(altered=altered):
                with patch("proofinvest.evidence_report.verify_sec_annual_revenue",
                           return_value=dict(real, **altered)):
                    with self.assertRaisesRegex(ValueError, "SYNTHETIC_REPORT_BLOCKED"):
                        build_synthetic_evidence_report()

    def test_spoofed_report_cannot_be_rendered_or_upgrade_trust(self):
        data = build_synthetic_evidence_report()
        bad = copy.deepcopy(data)
        bad["authenticity"]["external_source_authenticated"] = True
        for fmt in ("json", "markdown"):
            with self.assertRaisesRegex(ValueError, "UNTRUSTED_REPORT_CONTENT"):
                render_report(bad, fmt)
        with self.assertRaises(ValueError):
            render_report(None, "json")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_REPORT_FORMAT"):
            render_report(data, "pdf")

    def test_real_cli_json_and_markdown_are_offline_and_reproducible(self):
        for fmt in ("json", "markdown"):
            with self.subTest(fmt=fmt):
                output = subprocess.run(
                    [sys.executable, "-m", "proofinvest.evidence_report", "--format", fmt],
                    capture_output=True, text=True, timeout=20, check=False,
                )
                self.assertEqual(output.returncode, 0, output.stderr)
                self.assertFalse(output.stderr)
                self.assertIn("SYNTHETIC", output.stdout)
                if fmt == "json":
                    self.assertEqual(json.loads(output.stdout)["financial"]["growth_pct"],
                                     "100.00")
                else:
                    self.assertTrue(output.stdout.startswith("# ProofInvest"))

    def test_explicit_file_export_never_overwrites_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "synthetic-report.json"
            self.assertEqual(main(["--format", "json", "--output", str(dest)]), 0)
            original = dest.read_bytes()
            self.assertEqual(json.loads(original)["schema"],
                             "proofinvest.synthetic-evidence-report.v1")
            with self.assertRaises(SystemExit) as caught:
                main(["--format", "json", "--output", str(dest)])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(original, dest.read_bytes())

    def test_network_transport_not_called_by_report(self):
        with patch("disclosure_lightning.core.urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_BLOCK")) as a, patch(
                       "disclosure_lightning.originals.urllib.request.build_opener",
                       side_effect=AssertionError("NETWORK_BLOCK")) as b:
            result = build_synthetic_evidence_report()
        a.assert_not_called()
        b.assert_not_called()
        self.assertFalse(result["authenticity"]["real_sec_network_called"])


if __name__ == "__main__":
    unittest.main()
