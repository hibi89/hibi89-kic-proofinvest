"""P69: user-held SEC 3-file/ZIP + raw sector CSV + raw peers in ONE offline command.

All sample inputs are constructed synthetic sources. No real issuer claim.
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

from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.kic_dl_original_demo import PHRASE
from tests.test_real_data_preflight import args
from tests.test_real_data_preflight_peer_companyfacts import setup_peer, CIK, ACC
from tests.test_sec_bundle_replay import fixture as sec_fixture


CSV = b"period_end,value\n2024-09-30,200\n2025-09-30,240\n"


def build_args(root: Path):
    archive, market, _, peer = setup_peer(root)
    sector = root / "two-period-sector.csv"
    sector.write_bytes(CSV)
    values = {
        **args(archive, market),
        "industry_sector_csv": sector,
        "industry_sector_url": "https://www.bea.gov/data/industry/normalized",
        "industry_sector_published_at": "2025-10-15",
        "industry_name": "CONSTRUCTED_SECTOR",
        "industry_series_name": "CONSTRUCTED_PRODUCTION_INDEX",
        "industry_series_kind": "PRODUCTION_INDEX",
        "industry_sector_unit": "index_points",
        "industry_target_name": "CONSTRUCTED_TARGET",
        "industry_peer_names": ["CONSTRUCTED_PEER"],
        "peer_companyfacts_files": [peer],
        "peer_ciks": [CIK],
        "peer_accessions": [ACC],
    }
    return values, archive, market, sector, peer


class DirectIndustryPreflightTests(unittest.TestCase):
    def test_no_intermediate_industry_file_or_external_calls(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            options, archive, market, sector, peer = build_args(root)
            before = {p.name: sha256(p.read_bytes()).hexdigest()
                      for p in (archive, market, sector, peer)}
            existing_files = sorted(p.name for p in root.iterdir())
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("HTTP_FORBIDDEN")) as external:
                result = inspect_offline_data_files(**options)
            external.assert_not_called()
            self.assertEqual(result["status"],
                             "local_structure_pass_origin_unverified", result)
            self.assertEqual(result["industry_input_mode"],
                             "LOCAL_ORIGINALS_DERIVED_NO_SAVE")
            self.assertIsNone(result["industry_original_sha256"])
            self.assertRegex(result["industry_generated_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(result["all_three_inputs_present"])
            self.assertEqual(result["peer_sec_companyfacts_check"]["peer_count"], 1)
            self.assertEqual(result["peer_sec_companyfacts_check"][
                "peer_records"][0]["companyfacts_sha256"], before[peer.name])
            for key in ("source_authenticated", "data_rights_verified",
                        "three_engine_real_world_validated", "audit_retained",
                        "external_http_called", "trade_executed"):
                self.assertIs(result[key], False, key)
            self.assertEqual(before, {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in (archive, market, sector, peer)})
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             existing_files)

    def test_accept_direct_three_sec_files_same_bytes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, archive, market, sector, peer = build_args(root)
            receipt, raws = sec_fixture()
            # Reuse the fixture bytes, not a new or invented SEC submission.
            paths = {}
            for key in ("submissions", "companyfacts", "original_filing"):
                p = root / (key + ".input")
                p.write_bytes(raws[key])
                paths[key] = p
            opts.pop("sec_bundle")
            opts.update({
                "sec_submissions": paths["submissions"],
                "sec_companyfacts": paths["companyfacts"],
                "sec_filing": paths["original_filing"],
                "issuer_cik": receipt["issuer_cik"],
                "accession": receipt["accession"],
                "as_of": receipt["observed_utc_day"],
                "collected_at": "2025-10-16T12:00:00Z",
            })
            out = inspect_offline_data_files(**opts)
            self.assertEqual(out["status"],
                             "local_structure_pass_origin_unverified", out)
            self.assertEqual(out["sec_input_mode"],
                             "DIRECT_THREE_FILES_UNAUTHENTICATED")
            self.assertEqual(out["industry_input_mode"],
                             "LOCAL_ORIGINALS_DERIVED_NO_SAVE")
            self.assertIsNone(out["industry_original_sha256"])
            self.assertFalse(out["source_authenticated"])

    def test_invalid_raw_peer_blocks_all_engines_without_guard_audit(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, archive, market, sector, peer = build_args(root)
            obj = json.loads(peer.read_bytes())
            row = next(iter(obj["facts"]["us-gaap"].values()))["units"]["USD"][0]
            row["val"] = "not-a-number"
            peer.write_bytes(json.dumps(obj).encode())
            out = inspect_offline_data_files(**opts)
            self.assertEqual(out["status"], "blocked", out)
            self.assertEqual(out["reason_code"], "DERIVED_INDUSTRY_SOURCE_BLOCKED")
            self.assertFalse(out["audit_retained"])
            self.assertFalse(out["three_engine_real_world_validated"])

    def test_mixed_derived_and_existing_json_rejected_before_file_writes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, *_ = build_args(root)
            industry = root / "industry.json"
            industry.write_text('{"not":"valid"}', encoding="utf-8")
            opts["industry_json"] = industry
            out = inspect_offline_data_files(**opts)
            self.assertEqual(out["reason_code"], "DERIVED_INDUSTRY_INPUTS_INVALID")
            self.assertEqual(industry.read_text(), '{"not":"valid"}')

    def test_incomplete_peer_labels_and_bad_sector_block(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, archive, market, sector, peer = build_args(root)
            opts["industry_peer_names"] = []
            self.assertEqual(inspect_offline_data_files(**opts)["reason_code"],
                             "DERIVED_INDUSTRY_INPUTS_INVALID")
            opts["industry_peer_names"] = ["CONSTRUCTED_PEER"]
            sector.write_bytes(b"period_end,value\n2024-09-30,200\n2024-09-30,240\n")
            out = inspect_offline_data_files(**opts)
            self.assertEqual(out["reason_code"], "DERIVED_INDUSTRY_SOURCE_BLOCKED")

    def test_cli_with_direct_sector_flags_reports_only_sanitized_local_receipt(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, archive, market, sector, peer = build_args(root)
            cmd = [
                sys.executable, "-m", "proofinvest.real_data_preflight",
                "--sec-bundle", str(archive),
                "--prior-end", "2024-09-30",
                "--current-end", "2025-09-30",
                "--needle", PHRASE,
                "--market-csv", str(market),
                "--symbol", "SYNTH", "--benchmark", "NASDAQ_100",
                "--return-basis", "PRICE_ONLY_CLOSE",
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
                "--peer-companyfacts", str(peer),
                "--peer-cik", CIK, "--peer-accession", ACC,
            ]
            p = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
            receipt = json.loads(p.stdout)
            self.assertEqual(receipt["industry_input_mode"],
                             "LOCAL_ORIGINALS_DERIVED_NO_SAVE")
            self.assertTrue(receipt["all_three_inputs_present"])
            self.assertNotIn(str(root), p.stdout)
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             ["industry.json", "market.csv", "peer-companyfacts.json",
                              "sec.zip", "two-period-sector.csv"])


if __name__ == "__main__":
    unittest.main()
