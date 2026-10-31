"""End-to-end operator-local Engine C packet generation, all fixture bytes synthetic."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.industry_packet_builder import build_industry_packet
from proofinvest.industry_vision import analyze_industry_vision
from proofinvest.industry_peer_companyfacts import bind_peer_companyfacts_to_industry
from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.three_engine_research import bind_industry_to_sec
from tests.test_real_data_preflight_peer_companyfacts import setup_peer, CIK, ACC
from tests.test_real_data_preflight import args
from proofinvest.kic_dl_demo import (
    SYNTHETIC_CIK, SYNTHETIC_ACCESSION, synthetic_companyfacts,
)

CSV = b"period_end,value\n2024-09-30,200\n2025-09-30,240\n"


def build(raw_target: bytes, raw_peer: bytes, sector: bytes = CSV, **overrides):
    options = {
        "target": (SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
                   "CONSTRUCTED_TARGET", raw_target),
        "peers": [(CIK, ACC, "CONSTRUCTED_PEER", raw_peer)],
        "sector_csv": sector,
        "sector_url": "https://www.bea.gov/data/industry/synthetic-manual-normalization",
        "sector_published_at": "2025-10-15",
        "as_of": "2025-10-16",
        "prior_end": "2024-09-30",
        "current_end": "2025-09-30",
        "industry_name": "SYNTHETIC_INDUSTRY",
        "series_name": "SYNTHETIC_PRODUCTION_INDEX",
        "series_kind": "PRODUCTION_INDEX",
        "sector_unit": "index_points",
    }
    return build_industry_packet(**(options | overrides))


class IndustryPacketBuilderTests(unittest.TestCase):
    def setup(self, root: Path):
        archive, market, _, peer = setup_peer(root)
        target = json.dumps(synthetic_companyfacts()).encode()
        return archive, market, target, peer.read_bytes()

    def test_raw_companyfacts_and_two_row_sector_csv_to_full_preflight(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive, market, target, peer = self.setup(root)
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("NO_HTTP")) as req:
                packet = build(target, peer)
                record = json.loads(packet)
                growth = analyze_industry_vision(record)
                proof = bind_peer_companyfacts_to_industry(
                    packet, peer_sources=[(CIK, ACC, peer)],
                )
                industry = root / "industry-generated.json"
                industry.write_bytes(packet)
                response = inspect_offline_data_files(
                    **args(archive, market, industry),
                    peer_companyfacts_files=[root / "peer-companyfacts.json"],
                    peer_ciks=[CIK], peer_accessions=[ACC],
                )
            req.assert_not_called()
            self.assertEqual(growth["target"]["growth_pct_reported_input"], "100.00")
            self.assertEqual(growth["peers"][0]["growth_pct_reported_input"], "30.00")
            self.assertEqual(growth["industry_series"]["growth_pct_reported_input"], "20.00")
            self.assertEqual(proof["peer_records"][0]["companyfacts_sha256"],
                             sha256(peer).hexdigest())
            self.assertEqual(record["sources"][0]["sha256"], sha256(target).hexdigest())
            self.assertEqual(response["status"], "local_structure_pass_origin_unverified", response)
            self.assertTrue(response["all_three_inputs_present"])
            self.assertEqual(response["peer_sec_companyfacts_check"]["peer_count"], 1)
            self.assertFalse(response["three_engine_real_world_validated"])
            self.assertFalse(response["source_authenticated"])

    def test_companyfacts_mutation_and_wrong_sector_value_block(self):
        with TemporaryDirectory() as folder:
            _, _, target, peer = self.setup(Path(folder))
            invalid = json.loads(peer)
            row = invalid["facts"]["us-gaap"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"][0]
            row["val"] = "not-a-number"
            with self.assertRaisesRegex(ValueError, "COMPANYFACTS_ANNUAL_REVENUE_UNAVAILABLE"):
                build(target, json.dumps(invalid).encode())
            with self.assertRaises(ValueError):
                build(target, peer, b"period_end,value\n2024-09-30,200\n2025-09-30,not-a-number\n")
            with self.assertRaises(ValueError):
                build(target, peer, CSV.replace(b"2025-09-30,240", b"2024-09-30,240"))

    def test_sector_release_after_asof_refused_not_rewritten(self):
        with TemporaryDirectory() as folder:
            _, _, target, peer = self.setup(Path(folder))
            with self.assertRaisesRegex(ValueError, "SOURCE_AFTER_RESEARCH_AS_OF"):
                build(target, peer, sector_published_at="2025-10-17")
            with self.assertRaisesRegex(ValueError, "SOURCE_PRECEDES_ITS_OBSERVATION_PERIOD_END"):
                build(target, peer, sector_published_at="2025-09-29")

    def test_missing_peer_and_duplicate_target_refused(self):
        with TemporaryDirectory() as folder:
            _, _, target, peer = self.setup(Path(folder))
            with self.assertRaises(ValueError):
                build(target, peer, peers=[])
            with self.assertRaisesRegex(ValueError, "INDUSTRY_BUILDER_DUPLICATE_OR_BAD_SOURCE"):
                build(target, peer, peers=[(
                    SYNTHETIC_CIK, ACC, "SELF_COMPETITOR", peer,
                )])

    def test_cli_reads_local_sources_and_exclusive_output_preserves_originals(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive, market, target, peer = self.setup(root)
            target_file = root / "target-companyfacts.json"
            target_file.write_bytes(target)
            sector_file = root / "sector-normalized.csv"
            sector_file.write_bytes(CSV)
            out = root / "engine-c.json"
            before = {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in (target_file, root / "peer-companyfacts.json", sector_file)
            }
            cmd = [
                sys.executable, "-m", "proofinvest.industry_packet_builder",
                "--target-companyfacts", str(target_file),
                "--target-cik", SYNTHETIC_CIK,
                "--target-accession", SYNTHETIC_ACCESSION,
                "--target-name", "CONSTRUCTED_TARGET",
                "--peer-companyfacts", str(root / "peer-companyfacts.json"),
                "--peer-cik", CIK, "--peer-accession", ACC,
                "--peer-name", "CONSTRUCTED_PEER",
                "--industry-csv", str(sector_file),
                "--sector-source-url", "https://www.bea.gov/data/industry/normalized",
                "--sector-published-at", "2025-10-15",
                "--industry-name", "SYNTHETIC_INDUSTRY",
                "--series-name", "SYNTHETIC_INDEX",
                "--series-kind", "PRODUCTION_INDEX",
                "--sector-unit", "index_points",
                "--as-of", "2025-10-16",
                "--prior-end", "2024-09-30",
                "--current-end", "2025-09-30",
                "--output-json", str(out),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            receipt = json.loads(proc.stdout)
            self.assertEqual(receipt["status"],
                             "local_industry_packet_written_origin_unverified")
            self.assertEqual(receipt["output_sha256"], sha256(out.read_bytes()).hexdigest())
            self.assertNotIn(str(target_file), proc.stdout)
            self.assertEqual(before, {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in (target_file, root / "peer-companyfacts.json", sector_file)
            })
            rerun = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(rerun.returncode, 2)
            self.assertEqual(json.loads(rerun.stdout)["status"], "blocked")
            self.assertEqual(receipt["output_sha256"], sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
