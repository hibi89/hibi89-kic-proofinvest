"""Independent actual CLI subprocess test with disposable synthetic originals.

Never uses live SEC/market providers. This tests path-based executable input
and actual filesystem output/verification on GitHub Windows and Linux.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from tests.test_ticker_offline_review_builder import payload
from proofinvest.ticker_review_source_replay import replay_review_packet_from_original_bytes
from proofinvest.ticker_source_clearance_packet import inspect_source_clearance_packet


def main() -> int:
    fixture = payload()
    with tempfile.TemporaryDirectory(prefix="kuodra-originals-smoke-") as tmp:
        directory = Path(tmp)
        flags = ["--ticker", fixture["ticker"], "--as-of", fixture["as_of"]]
        for key, content in fixture["sources"].items():
            file = directory / (key + ".json")
            file.write_bytes(content)
            flags += ["--" + key.replace("_", "-"), str(file)]
        for opt, name, value in (
            ("stock-daily", "stock.json", fixture["stock_raw"]),
            ("ndx-daily", "ndx.json", fixture["index_raw"]),
            ("market-json", "market.json", fixture["market_json"]),
            ("industry-json", "industry.json", fixture["industry_json"]),
        ):
            file = directory / name
            file.write_bytes(value)
            flags += ["--" + opt, str(file)]
        out = directory / "reports"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.local_originals_review_cli",
             *flags, "--output-dir", str(out)],
            check=True, text=True, capture_output=True, timeout=30,
        )
        receipt = json.loads(result.stdout)
        assert receipt["status"] == "LOCAL_ORIGINALS_REPLAYED_UNVERIFIED"
        assert receipt["source_rights_verified"] is False
        assert receipt["external_sharing_allowed"] is False
        assert receipt["network_requests"] == 0
        review = (out / receipt["review_filename"]).read_bytes()
        rights = (out / receipt["rights_filename"]).read_bytes()
        assert inspect_source_clearance_packet(
            rights, review_packet=review)["status"] == (
                "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING")
        assert replay_review_packet_from_original_bytes(
            review, sources=fixture["sources"],
            stock_raw=fixture["stock_raw"],
            index_raw=fixture["index_raw"],
            market_json=fixture["market_json"],
            industry_json=fixture["industry_json"])["status"] == (
                "PASS_UNVERIFIED_ORIGIN")
        duplicate = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.local_originals_review_cli",
             *flags, "--output-dir", str(out)],
            text=True, capture_output=True, timeout=30,
        )
        assert duplicate.returncode == 2
        assert json.loads(duplicate.stdout)["status"] == "BLOCKED"
    print("KUODRA_P178_ORIGINAL_FILES_TO_REPLAYED_REDACTED_PACKET_WINDOWS_LINUX_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
