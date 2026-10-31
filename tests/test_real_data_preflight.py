"""P49: real-file-shaped offline SEC+market+industry preflight (synthetic tests).

Never calls SEC, authenticates origin, writes outside temp, or grants trades.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from tests.test_industry_vision import fixture as industry_fixture
from tests.test_market_price_csv import csv_from_fixture
from tests.test_sec_bundle_replay import fixture as sec_fixture


def create_files(root: Path):
    receipt, raws = sec_fixture()
    archive = root / "sec.zip"
    save_local_capture_bundle(archive, receipt=receipt, **raws)
    market = root / "market.csv"
    market.write_bytes(csv_from_fixture())
    industry = industry_fixture()
    industry.update(
        issuer_cik=receipt["issuer_cik"],
        as_of="2025-10-16", prior_period_end="2024-09-30",
        current_period_end="2025-09-30",
    )
    industry["target"].update(
        cik=receipt["issuer_cik"],
        prior_revenue_usd="100", current_revenue_usd="200",
    )
    for source in industry["sources"]:
        source["published_at"] = "2025-10-15"
        if source["id"] in ("target-old", "target-now"):
            source["sha256"] = sha256(raws["companyfacts"]).hexdigest()
    datafile = root / "industry.json"
    datafile.write_bytes(json.dumps(industry, sort_keys=True).encode())
    return archive, market, datafile, industry


def args(zipfile, market=None, industry=None):
    out = {
        "sec_bundle": zipfile,
        "prior_end": "2024-09-30", "current_end": "2025-09-30",
        "needle": PHRASE,
    }
    if market is not None:
        out.update({
            "market_csv": market,
            "symbol": "SYNTH", "benchmark": "NASDAQ_100",
            "return_basis": "PRICE_ONLY_CLOSE",
            "market_source_url": "https://example.org/legal-operator-csv",
            "market_published_at": "2025-10-15",
        })
    if industry is not None:
        out["industry_json"] = industry
    return out


class RealDataPreflightTests(unittest.TestCase):
    def test_all_sources_valid_local_shape_and_guard_temp_deleted(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p49-") as directory:
            root = Path(directory)
            archive, market, industry, _ = create_files(root)
            prior_hashes = {p.name: sha256(p.read_bytes()).hexdigest()
                            for p in (archive, market, industry)}
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("NO_HTTP")) as network:
                res = inspect_offline_data_files(**args(archive, market, industry))
            network.assert_not_called()
            self.assertEqual(res["status"], "local_structure_pass_origin_unverified")
            self.assertTrue(res["sec_capture_digest_matched"])
            self.assertTrue(res["all_three_inputs_present"])
            self.assertEqual(res["market_status"], "REPORTED_UNVERIFIED")
            self.assertEqual(res["industry_status"], "OBSERVED_COMPARISON_UNVERIFIED")
            self.assertEqual(res["market_sec_context_temporal_status"],
                             "WITHHELD_FILING_NOT_PRIOR_TO_PRICE_WINDOW")
            self.assertEqual(res["market_csv_original_sha256"],
                             sha256(market.read_bytes()).hexdigest())
            self.assertEqual(res["industry_original_sha256"],
                             sha256(industry.read_bytes()).hexdigest())
            for key in ("source_authenticated", "data_rights_verified",
                        "historical_market_vintage_authenticated",
                        "corporate_actions_verified", "point_in_time_backtest_verified",
                        "three_engine_real_world_validated", "ai_generated",
                        "trade_executed", "audit_retained", "external_http_called"):
                self.assertIs(res[key], False, key)
            self.assertEqual(prior_hashes, {p.name: sha256(p.read_bytes()).hexdigest()
                                            for p in (archive, market, industry)})
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             ["industry.json", "market.csv", "sec.zip"])
            self.assertNotIn("synthetic10k.htm", json.dumps(res))

    def test_sec_only_is_allowed_but_does_not_claim_three_engines(self):
        with tempfile.TemporaryDirectory() as home:
            zipfile, _, _, _ = create_files(Path(home))
            res = inspect_offline_data_files(**args(zipfile))
            self.assertEqual(res["status"], "local_structure_pass_origin_unverified")
            self.assertEqual(res["market_status"], "NO_INPUT")
            self.assertEqual(res["industry_status"], "NO_INPUT")
            self.assertFalse(res["all_three_inputs_present"])
            self.assertFalse(res["audit_retained"])

    def test_wrong_issuer_sector_and_wrong_fiscal_period_block(self):
        with tempfile.TemporaryDirectory() as home:
            root = Path(home)
            zipfile, market, sector, original = create_files(root)
            for change in ("issuer", "period", "revenue", "source_digest"):
                info = json.loads(sector.read_bytes())
                if change == "issuer":
                    info["issuer_cik"] = "0000000002"
                    info["target"]["cik"] = "0000000002"
                if change == "period":
                    info["prior_period_end"] = "2024-09-29"
                if change == "revenue":
                    info["target"]["current_revenue_usd"] = "999"
                if change == "source_digest":
                    info["sources"][1]["sha256"] = "f" * 64
                sector.write_bytes(json.dumps(info).encode())
                with self.subTest(change=change):
                    result = inspect_offline_data_files(**args(zipfile, market, sector))
                    self.assertEqual(result["status"], "blocked")
                    self.assertFalse(result["three_engine_real_world_validated"])
            sector.write_bytes(json.dumps(original).encode())

    def test_corrupted_capture_blocked_without_persisting_audit(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            zipfile, market, sector, _ = create_files(root)
            binary = bytearray(zipfile.read_bytes())
            pos = binary.index(b"synthetic10k")
            binary[pos] ^= 1
            zipfile.write_bytes(binary)
            res = inspect_offline_data_files(**args(zipfile, market, sector))
            self.assertEqual(res["status"], "blocked")
            self.assertEqual(res["reason_code"], "SEC_ZIP_INTEGRITY_OR_MANIFEST_INVALID")

    def test_csv_missing_metadata_and_future_vendor_release_block(self):
        with tempfile.TemporaryDirectory() as home:
            zipfile, market, sector, _ = create_files(Path(home))
            invalid = args(zipfile, market, sector)
            invalid.pop("market_published_at")
            self.assertEqual(inspect_offline_data_files(**invalid)["reason_code"],
                             "MARKET_METADATA_REQUIRED")
            invalid = args(zipfile, market, sector)
            invalid["market_published_at"] = "2025-10-17"
            self.assertEqual(inspect_offline_data_files(**invalid)["status"], "blocked")

    def test_symlink_price_file_rejected_when_platform_supports(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            zipfile, market, sector, _ = create_files(root)
            symlink = root / "alias.csv"
            try:
                symlink.symlink_to(market)
            except (OSError, NotImplementedError):
                return
            res = inspect_offline_data_files(**args(zipfile, symlink, sector))
            self.assertEqual(res["status"], "blocked")
            self.assertFalse(res["source_authenticated"])

    def test_cli_prints_sanitized_receipt_only_without_new_files(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            zipfile, market, _, _ = create_files(root)
            proc = subprocess.run([
                sys.executable, "-m", "proofinvest.real_data_preflight",
                "--sec-bundle", str(zipfile),
                "--prior-end", "2024-09-30", "--current-end", "2025-09-30",
                "--needle", PHRASE,
                "--market-csv", str(market), "--symbol", "SYNTH",
                "--benchmark", "NASDAQ_100",
                "--return-basis", "PRICE_ONLY_CLOSE",
                "--market-source-url", "https://example.org/legal-operator-csv",
                "--market-published-at", "2025-10-15",
            ], capture_output=True, text=True, check=False, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            output=json.loads(proc.stdout)
            self.assertEqual(output["market_status"], "REPORTED_UNVERIFIED")
            self.assertFalse(output["three_engine_real_world_validated"])
            self.assertFalse(output["data_rights_verified"])


if __name__ == "__main__":
    unittest.main()
