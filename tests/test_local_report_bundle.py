"""P70 explicit ZIP export of one-shot local original-byte analysis.

Constructed SEC and sector inputs only: no real-source authentication.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.local_report_bundle import write_new_local_report_bundle
from tests.test_real_data_preflight_auto_industry import build_args
from proofinvest.kic_dl_original_demo import PHRASE


class ReportBundleTests(unittest.TestCase):
    def test_opt_in_output_has_json_html_digest_and_no_source_replacement(self):
        with TemporaryDirectory() as root:
            home = Path(root)
            opts, archive, market, sector, peer = build_args(home)
            before = {f.name: sha256(f.read_bytes()).hexdigest()
                      for f in home.iterdir()}
            dest = home / "owner-requested-report.zip"
            opts["output_report_zip"] = dest
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("NETWORK_FORBIDDEN")) as network:
                result = inspect_offline_data_files(**opts)
            network.assert_not_called()
            self.assertEqual(result["status"],
                             "local_structure_pass_origin_unverified", result)
            self.assertTrue(result["report_bundle_created"])
            self.assertEqual(result["report_bundle_sha256"],
                             sha256(dest.read_bytes()).hexdigest())
            self.assertEqual(result["industry_input_mode"],
                             "LOCAL_ORIGINALS_DERIVED_NO_SAVE")
            self.assertEqual(
                before,
                {name: sha256((home / name).read_bytes()).hexdigest()
                 for name in before},
            )
            self.assertEqual(
                sorted(f.name for f in home.iterdir()),
                sorted([*before, "owner-requested-report.zip"]),
            )
            with ZipFile(dest) as bundle:
                self.assertEqual(sorted(bundle.namelist()),
                                 ["manifest.json", "report.html", "report.json"])
                manifest = json.loads(bundle.read("manifest.json"))
                report = json.loads(bundle.read("report.json"))
                rendered = bundle.read("report.html")
                for name in ("report.json", "report.html"):
                    self.assertEqual(
                        sha256(bundle.read(name)).hexdigest(),
                        manifest["files"][name]["sha256"],
                    )
                self.assertFalse(manifest["source_authenticated"])
                self.assertFalse(manifest["audit_retained"])
                self.assertFalse(manifest["real_data_verified"])
                self.assertIn(report["guard"]["decision"], ("HOLD", "REJECT"))
                self.assertEqual(report["peer_sec_companyfacts_check"]["peer_count"], 1)
                self.assertTrue(report["three_engine_summary"]["all_three_inputs_present"])
                self.assertIn(b"<!DOCTYPE html", rendered)

    def test_no_output_flag_preserves_zero_created_files(self):
        with TemporaryDirectory() as root:
            home = Path(root)
            opts, *_ = build_args(home)
            initial = {p.name: sha256(p.read_bytes()).hexdigest()
                       for p in home.iterdir()}
            result = inspect_offline_data_files(**opts)
            self.assertEqual(result["status"],
                             "local_structure_pass_origin_unverified", result)
            self.assertFalse(result["report_bundle_created"])
            self.assertIsNone(result["report_bundle_sha256"])
            self.assertEqual(initial, {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in home.iterdir()})

    def test_preexisting_bundle_not_overwritten_even_with_good_inputs(self):
        with TemporaryDirectory() as root:
            home = Path(root)
            opts, *_ = build_args(home)
            dest = home / "report.zip"
            dest.write_bytes(b"ORIGINAL_DO_NOT_OVERWRITE")
            opts["output_report_zip"] = dest
            result = inspect_offline_data_files(**opts)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_code"], "REPORT_BUNDLE_EXPORT_BLOCKED")
            self.assertEqual(dest.read_bytes(), b"ORIGINAL_DO_NOT_OVERWRITE")
            self.assertFalse(result["report_bundle_created"])
            self.assertFalse(result["audit_retained"])

    def test_invalid_inputs_never_create_output_or_temp_guard(self):
        with TemporaryDirectory() as root:
            home = Path(root)
            opts, *_ = build_args(home)
            dest = home / "must-not-exist.zip"
            opts["output_report_zip"] = dest
            opts["industry_peer_names"] = []
            result = inspect_offline_data_files(**opts)
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(dest.exists())
            self.assertFalse(result["audit_retained"])

    def test_cli_option_writes_single_zip_no_full_private_paths_in_receipt(self):
        with TemporaryDirectory() as root:
            home = Path(root)
            opts, archive, market, sector, peer = build_args(home)
            dest = home / "result-report.zip"
            cmd = [
                sys.executable, "-m", "proofinvest.real_data_preflight",
                "--sec-bundle", str(archive),
                "--prior-end", "2024-09-30",
                "--current-end", "2025-09-30",
                "--needle", PHRASE,
                "--market-csv", str(market), "--symbol", "SYNTH",
                "--benchmark", "NASDAQ_100", "--return-basis", "PRICE_ONLY_CLOSE",
                "--market-source-url", "https://example.org/legal-operator-csv",
                "--market-published-at", "2025-10-15",
                "--industry-sector-csv", str(sector),
                "--industry-sector-url", "https://www.bea.gov/data/industry/normalized",
                "--industry-sector-published-at", "2025-10-15",
                "--industry-name", "CONSTRUCTED_SECTOR",
                "--industry-series-name", "CONSTRUCTED_PRODUCTION_INDEX",
                "--industry-series-kind", "PRODUCTION_INDEX",
                "--industry-sector-unit", "index_points",
                "--industry-target-name", "CONSTRUCTED_TARGET",
                "--industry-peer-name", "CONSTRUCTED_PEER",
                "--peer-companyfacts", str(peer), "--peer-cik", "0000000007",
                "--peer-accession", "0000000007-25-000001",
                "--output-report-zip", str(dest),
            ]
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            receipt = json.loads(run.stdout)
            self.assertTrue(receipt["report_bundle_created"])
            self.assertNotIn(str(home), run.stdout)
            self.assertEqual(receipt["report_bundle_sha256"],
                             sha256(dest.read_bytes()).hexdigest())
            retry = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(retry.returncode, 2)
            self.assertEqual(json.loads(retry.stdout)["reason_code"],
                             "REPORT_BUNDLE_EXPORT_BLOCKED")
            self.assertEqual(sha256(dest.read_bytes()).hexdigest(),
                             receipt["report_bundle_sha256"])

    def test_helper_refuses_forged_guard_and_existing_symlink(self):
        with TemporaryDirectory() as root:
            folder = Path(root)
            invalid = {"guard": {"decision": "APPROVE", "source_authenticated": False},
                       "three_engine_summary": {"all_three_inputs_present": True}}
            with self.assertRaisesRegex(ValueError, "REPORT_GUARD_OR_HTML_INVALID"):
                write_new_local_report_bundle(
                    folder / "forged.zip", invalid, b"<!DOCTYPE html><html></html>")
            self.assertFalse((folder / "forged.zip").exists())
            target = folder / "target.zip"
            target.write_bytes(b"DO_NOT_TOUCH")
            link = folder / "link.zip"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            valid = {"guard": {"decision": "HOLD", "source_authenticated": False},
                     "three_engine_summary": {"all_three_inputs_present": True}}
            with self.assertRaises(ValueError):
                write_new_local_report_bundle(
                    link, valid, b"<!DOCTYPE html><html></html>")
            self.assertEqual(target.read_bytes(), b"DO_NOT_TOUCH")


if __name__ == "__main__":
    unittest.main()
