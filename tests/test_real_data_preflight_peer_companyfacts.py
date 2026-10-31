"""Integrated offline A/B/C peer raw CompanyFacts binding (synthetic inputs)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.sec_companyfacts import TAG
from tests.test_real_data_preflight import create_files, args


CIK = "0000000007"
ACC = "0000000007-25-000001"
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000007.json"


def setup_peer(root: Path):
    archive, market, industry_path, industry = create_files(root)
    peer_facts = {
        "cik": 7, "entityName": "SYNTHETIC_PEER",
        "facts": {"us-gaap": {TAG: {"units": {"USD": [
            {"accn": ACC, "form": "10-K", "start": "2024-10-01",
             "end": "2025-09-30", "filed": "2025-10-15", "val": 130},
            {"accn": ACC, "form": "10-K", "start": "2023-10-01",
             "end": "2024-09-30", "filed": "2025-10-15", "val": 100},
        ]}}}},
    }
    path = root / "peer-companyfacts.json"
    raw = json.dumps(peer_facts, sort_keys=True).encode()
    path.write_bytes(raw)
    for source in industry["sources"]:
        if source["id"] in ("peer-old", "peer-now"):
            source.update(
                url=URL, published_at="2025-10-15",
                sha256=sha256(raw).hexdigest(),
            )
    industry_path.write_bytes(json.dumps(industry, sort_keys=True).encode())
    return archive, market, industry_path, path


def kwargs(archive, market, industry, path):
    return {
        **args(archive, market, industry),
        "peer_companyfacts_files": [path],
        "peer_ciks": [CIK],
        "peer_accessions": [ACC],
    }


class PeerSecPreflightTests(unittest.TestCase):
    def test_complete_three_engine_offline_peer_companyfacts_e2e(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive, market, industry, peer = setup_peer(root)
            originals = {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in (archive, market, industry, peer)
            }
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("NO_NETWORK")) as network:
                result = inspect_offline_data_files(
                    **kwargs(archive, market, industry, peer))
            network.assert_not_called()
            self.assertEqual(result["status"],
                             "local_structure_pass_origin_unverified", result)
            self.assertTrue(result["all_three_inputs_present"])
            proof = result["peer_sec_companyfacts_check"]
            self.assertEqual(proof["peer_count"], 1)
            self.assertEqual(proof["peer_records"][0]["growth_pct"], "30.00")
            self.assertEqual(proof["peer_records"][0]["companyfacts_sha256"],
                             originals[peer.name])
            self.assertFalse(proof["source_authenticated"])
            self.assertFalse(result["source_authenticated"])
            self.assertFalse(result["three_engine_real_world_validated"])
            self.assertFalse(result["audit_retained"])
            self.assertEqual(
                originals, {p.name: sha256(p.read_bytes()).hexdigest()
                            for p in (archive, market, industry, peer)},
            )
            self.assertEqual(len(list(root.iterdir())), 4)

    def test_declared_peer_revenue_conflict_blocks_whole_preflight(self):
        with TemporaryDirectory() as folder:
            archive, market, industry, peer = setup_peer(Path(folder))
            data = json.loads(industry.read_bytes())
            data["peers"][0]["current_revenue_usd"] = "131"
            industry.write_bytes(json.dumps(data).encode())
            result = inspect_offline_data_files(
                **kwargs(archive, market, industry, peer))
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_code"], "PEER_COMPANYFACTS_CHECK_BLOCKED")
            self.assertFalse(result["audit_retained"])

    def test_missing_peer_inputs_or_industry_block_before_guard(self):
        with TemporaryDirectory() as folder:
            archive, market, industry, peer = setup_peer(Path(folder))
            invalid = kwargs(archive, market, industry, peer)
            invalid.pop("peer_accessions")
            self.assertEqual(
                inspect_offline_data_files(**invalid)["reason_code"],
                "PEER_SOURCE_INPUTS_REQUIRED",
            )
            invalid = kwargs(archive, market, industry, peer)
            invalid.pop("industry_json")
            self.assertEqual(
                inspect_offline_data_files(**invalid)["reason_code"],
                "PEER_SOURCE_INPUTS_REQUIRED",
            )

    def test_symlink_peer_original_blocks_on_supported_platforms(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            archive, market, industry, peer = setup_peer(root)
            link = root / "not-actual-source.json"
            try:
                link.symlink_to(peer)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable on platform")
            result = inspect_offline_data_files(
                **kwargs(archive, market, industry, link))
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_code"], "PEER_COMPANYFACTS_CHECK_BLOCKED")


if __name__ == "__main__":
    unittest.main()
