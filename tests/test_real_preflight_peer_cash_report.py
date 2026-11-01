"""P95 offline ZIP -> A/B/C -> peer cash evidence -> CLI/JSON/HTML.

Source fixtures are generated SEC-shaped files, NOT actual SEC requests,
external provenance, accounting equivalence, trade safety, or a live model.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.operator_sec_zip import make_operator_sec_zip_bytes
from tests.test_real_data_preflight_auto_industry import build_args
from tests.test_sec_bundle_replay import fixture as source_fixture
from tests.test_peer_cash_trend import extend_with_prior
from tests.test_peer_cash_conversion import NI, CFO
from proofinvest.kic_dl_original_demo import PHRASE


def assembled(root: Path, mode: str = "complete"):
    opts, _old_capture, _market, _sector, peer_path = build_args(root)
    receipt, raws = source_fixture()
    if mode == "missing_current":
        tgt, peer = None, None
    else:
        _, tgt, peers = extend_with_prior(with_peer=(mode != "no_prior_peer"))
        peer = json.loads(peers[0][2])
        if mode == "current_window_mismatch":
            for tag in (NI, CFO):
                for row in peer["facts"]["us-gaap"][tag]["units"]["USD"]:
                    if row["end"] == "2025-09-30":
                        row["start"] = "2024-10-02"
        raws["companyfacts"] = tgt[2]
        peer_path.write_bytes(json.dumps(peer, sort_keys=True).encode())
    operator_path = root / "operator-sec-shaped.zip"
    operator_path.write_bytes(make_operator_sec_zip_bytes(
        submissions=raws["submissions"],
        companyfacts=raws["companyfacts"],
        original_filing=raws["original_filing"],
        issuer_cik=receipt["issuer_cik"], accession=receipt["accession"],
        as_of=receipt["observed_utc_day"],
        collected_at=receipt["submissions_observed_at_utc"],
    ))
    opts["sec_bundle"] = None
    opts["operator_sec_zip"] = operator_path
    return opts, operator_path, peer_path


def safe_run(options):
    with patch("urllib.request.urlopen",
               side_effect=AssertionError("EXTERNAL_HTTP_DENIED")) as http:
        receipt = inspect_offline_data_files(**options)
    http.assert_not_called()
    return receipt


class P95PeerAccountingOfflineE2E(unittest.TestCase):
    def test_full_two_year_company_and_peer_report_zip(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, src, peer = assembled(root)
            initial = {p.name: sha256(p.read_bytes()).hexdigest()
                       for p in root.iterdir() if p.is_file()}
            dest = root / "reviewer-report.zip"
            opts["output_report_zip"] = dest
            receipt = safe_run(opts)
            self.assertEqual(receipt["status"],
                             "local_structure_pass_origin_unverified", receipt)
            self.assertEqual(receipt["sec_input_mode"],
                             "OPERATOR_LOCAL_ZIP_NO_HTTP_UNAUTHENTICATED")
            self.assertTrue(receipt["operator_sec_zip_integrity_matched"])
            self.assertFalse(receipt["sec_capture_digest_matched"])
            self.assertEqual(receipt["peer_cash_conversion_status"],
                             "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
            self.assertEqual(receipt["peer_cash_trend_status"],
                             "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
            self.assertEqual(receipt["peer_period_comparability_current_status"],
                             "MATCHED_CURRENT_ANNUAL_WINDOW_LOCAL_ONLY")
            self.assertEqual(receipt["peer_period_comparability_two_year_status"],
                             "MATCHED_TWO_YEAR_ANNUAL_WINDOWS_LOCAL_ONLY")
            self.assertEqual(receipt["peer_current_target_pct"], "33.33")
            self.assertEqual(receipt["peer_current_median_pct"], "50.00")
            self.assertEqual(receipt["peer_current_gap_pp"], "-16.67")
            self.assertEqual(receipt["peer_two_year_target_change_pp"], "-66.67")
            self.assertEqual(receipt["peer_two_year_median_change_pp"], "25.00")
            self.assertEqual(receipt["peer_two_year_gap_pp"], "-91.67")
            self.assertTrue(receipt["all_three_inputs_present"])
            self.assertTrue(receipt["report_bundle_created"])
            self.assertEqual(receipt["report_bundle_sha256"],
                             sha256(dest.read_bytes()).hexdigest())
            with ZipFile(dest) as bundle:
                self.assertEqual(set(bundle.namelist()),
                                 {"report.json", "report.html", "manifest.json"})
                report = json.loads(bundle.read("report.json"))
                html = bundle.read("report.html").decode("utf-8")
                manifest = json.loads(bundle.read("manifest.json"))
            self.assertEqual(report["guard"]["decision"],
                             receipt["guard_decision_unchanged"])
            self.assertEqual(report["peer_cash_conversion"]["cash_conversion_target_pct"],
                             "33.33")
            self.assertEqual(report["peer_cash_conversion"]["target_minus_peer_median_pp"],
                             "-16.67")
            self.assertEqual(report["peer_cash_conversion"]["two_year_target_minus_peer_change_pp"],
                             "-91.67")
            self.assertEqual(report["peer_cash_conversion"]["rows"][0][
                "companyfacts_sha256"], receipt["sec_source_sha256"]["companyfacts"])
            self.assertEqual(report["peer_cash_conversion"]["rows"][1][
                "companyfacts_sha256"], sha256(peer.read_bytes()).hexdigest())
            self.assertIn("02F-3 / Engine B × C 경쟁사 현금전환 비교 (로컬)", html)
            self.assertIn("33.33", html)
            self.assertIn("-91.67", html)
            self.assertIn("0000000007", html)
            self.assertNotIn("<script", html.lower())
            self.assertFalse(manifest["source_authenticated"])
            self.assertFalse(manifest["real_data_verified"])
            self.assertFalse(report["peer_cash_conversion"]["trade_executed"])
            self.assertFalse(receipt["data_rights_verified"])
            self.assertFalse(receipt["external_http_called"])
            self.assertFalse(receipt["audit_retained"])
            self.assertEqual(
                initial,
                {name: sha256((root / name).read_bytes()).hexdigest()
                 for name in initial},
            )

    def test_no_owner_export_means_zero_new_files_and_same_peer_metrics(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _src, _peer = assembled(root)
            before = {p.name: sha256(p.read_bytes()).hexdigest()
                      for p in root.iterdir() if p.is_file()}
            result = safe_run(opts)
            self.assertEqual(result["peer_cash_conversion_status"],
                             "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
            self.assertIsNone(result["report_bundle_sha256"])
            self.assertFalse(result["report_bundle_created"])
            self.assertEqual(before, {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in root.iterdir() if p.is_file()
            })

    def test_missing_accounting_keeps_a_b_c_guard_and_withholds_peer_median(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _zip, _peer = assembled(root, "missing_current")
            opts["output_report_zip"] = root / "partial.zip"
            out = safe_run(opts)
            self.assertEqual(out["status"], "local_structure_pass_origin_unverified", out)
            self.assertTrue(out["all_three_inputs_present"])
            self.assertEqual(out["peer_cash_conversion_status"],
                             "INCOMPLETE_ACCOUNTING_METRICS_COMPARISON_WITHHELD")
            self.assertEqual(out["peer_cash_trend_status"],
                             "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD")
            self.assertEqual(out["peer_period_comparability_current_status"],
                             "INCOMPLETE_CURRENT_ACCOUNTING_EVIDENCE")
            self.assertIsNone(out["peer_current_target_pct"])
            self.assertIsNone(out["peer_current_median_pct"])
            self.assertIsNone(out["peer_current_gap_pp"])
            self.assertIsNone(out["peer_two_year_gap_pp"])
            with ZipFile(opts["output_report_zip"]) as bundle:
                report = json.loads(bundle.read("report.json"))
                rendered = bundle.read("report.html").decode("utf-8")
            self.assertEqual(report["peer_cash_conversion"]["period_comparability"][
                "missing_current_count"], 2)
            self.assertIn("WITHHELD", rendered)
            self.assertIn("INCOMPLETE_CURRENT_ACCOUNTING_EVIDENCE", rendered)
            self.assertFalse(report["peer_cash_conversion"]["accounting_fraud_proven"])
            self.assertEqual(report["guard"]["decision"], out["guard_decision_unchanged"])

    def test_missing_prior_peer_only_blocks_two_year_median(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _zip, _peer = assembled(root, "no_prior_peer")
            opts["output_report_zip"] = root / "partial-trend.zip"
            out = safe_run(opts)
            self.assertEqual(out["status"], "local_structure_pass_origin_unverified", out)
            self.assertEqual(out["peer_cash_conversion_status"],
                             "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
            self.assertEqual(out["peer_current_median_pct"], "50.00")
            self.assertEqual(out["peer_cash_trend_status"],
                             "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD")
            self.assertIsNone(out["peer_two_year_target_change_pp"])
            with ZipFile(opts["output_report_zip"]) as bundle:
                report = json.loads(bundle.read("report.json"))
                rendered = bundle.read("report.html").decode("utf-8")
            self.assertIn("50.00", rendered)
            self.assertIn("WITHHELD", rendered)
            self.assertEqual(report["peer_cash_conversion"]["period_comparability"][
                "missing_two_year_count"], 1)

    def test_mismatched_company_annual_windows_withhold_both_group_comparisons(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _zip, _peer = assembled(root, "current_window_mismatch")
            out = safe_run(opts)
            self.assertEqual(out["status"], "local_structure_pass_origin_unverified", out)
            self.assertEqual(out["peer_cash_conversion_status"],
                             "PERIOD_WINDOW_COMPARISON_WITHHELD")
            self.assertEqual(out["peer_cash_trend_status"],
                             "PERIOD_WINDOW_TWO_YEAR_COMPARISON_WITHHELD")
            self.assertEqual(out["peer_period_comparability_current_status"],
                             "CASH_REVENUE_CURRENT_WINDOW_MISMATCH")
            self.assertIsNone(out["peer_current_median_pct"])
            self.assertIsNone(out["peer_two_year_median_change_pp"])

    def test_wrong_source_or_issuer_is_blocked_without_export(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _zip, peer = assembled(root)
            original = peer.read_bytes()
            doc = json.loads(original)
            doc["cik"] = 400
            peer.write_bytes(json.dumps(doc).encode())
            opts["output_report_zip"] = root / "blocked-output.zip"
            out = safe_run(opts)
            self.assertEqual(out["status"], "blocked", out)
            self.assertEqual(out["reason_code"], "DERIVED_INDUSTRY_SOURCE_BLOCKED")
            self.assertFalse(opts["output_report_zip"].exists())
            self.assertFalse(out["audit_retained"])

    def test_html_rejects_detached_sha_and_fake_aggregate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, _zip, _peer = assembled(root)
            opts["output_report_zip"] = root / "original.zip"
            out = safe_run(opts)
            self.assertEqual(out["status"], "local_structure_pass_origin_unverified", out)
            with ZipFile(opts["output_report_zip"]) as bundle:
                doc = json.loads(bundle.read("report.json"))
            changed = deepcopy(doc)
            changed["peer_cash_conversion"]["rows"][1][
                "companyfacts_sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                render_local_sec_html(changed)
            changed = deepcopy(doc)
            changed["peer_cash_conversion"]["cash_conversion_peer_median_pct"] = None
            with self.assertRaises(ValueError):
                render_local_sec_html(changed)
            changed = deepcopy(doc)
            changed["peer_cash_conversion"]["guard_policy_modified"] = True
            with self.assertRaises(ValueError):
                render_local_sec_html(changed)

    def test_cli_operator_zip_and_industry_source_results_are_consistent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            opts, zipped, peer = assembled(root)
            cmd = [
                sys.executable, "-m", "proofinvest.real_data_preflight",
                "--operator-sec-zip", str(zipped),
                "--prior-end", "2024-09-30", "--current-end", "2025-09-30",
                "--needle", PHRASE,
                "--market-csv", str(opts["market_csv"]),
                "--symbol", "SYNTH", "--benchmark", "NASDAQ_100",
                "--return-basis", "PRICE_ONLY_CLOSE",
                "--market-source-url", "https://example.org/legal-operator-csv",
                "--market-published-at", "2025-10-15",
                "--industry-sector-csv", str(opts["industry_sector_csv"]),
                "--industry-sector-url", opts["industry_sector_url"],
                "--industry-sector-published-at",
                opts["industry_sector_published_at"],
                "--industry-name", opts["industry_name"],
                "--industry-series-name", opts["industry_series_name"],
                "--industry-series-kind", opts["industry_series_kind"],
                "--industry-sector-unit", opts["industry_sector_unit"],
                "--industry-target-name", opts["industry_target_name"],
                "--industry-peer-name", opts["industry_peer_names"][0],
                "--peer-companyfacts", str(peer),
                "--peer-cik", opts["peer_ciks"][0],
                "--peer-accession", opts["peer_accessions"][0],
            ]
            exe = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            self.assertEqual(exe.returncode, 0, exe.stdout + exe.stderr)
            parsed = json.loads(exe.stdout)
            self.assertEqual(parsed["peer_cash_conversion_status"],
                             "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
            self.assertEqual(parsed["peer_two_year_gap_pp"], "-91.67")
            self.assertNotIn(str(root), exe.stdout)
            self.assertNotIn(PHRASE, exe.stdout)
            self.assertFalse(parsed["external_http_called"])


if __name__ == "__main__":
    unittest.main()
