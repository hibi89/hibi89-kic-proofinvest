"""P178 file-backed end-to-end original->A/B/C/Guard HOLD and no overwrite."""
from __future__ import annotations

import contextlib
from hashlib import sha256
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import local_originals_review_cli as cli
from proofinvest.ticker_review_source_replay import replay_review_packet_from_original_bytes
from proofinvest.ticker_source_clearance_packet import inspect_source_clearance_packet
from tests.test_ticker_offline_review_builder import payload


class NativeOriginalsReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = payload()
        self.originals = {}
        for role, raw in self.fixture["sources"].items():
            path = self.root / (role + ".json")
            path.write_bytes(raw)
            self.originals[role] = str(path)
        self.stock = self.root / "stock.json"
        self.stock.write_bytes(self.fixture["stock_raw"])
        self.index = self.root / "ndx.json"
        self.index.write_bytes(self.fixture["index_raw"])
        self.market = self.root / "market.json"
        self.market.write_bytes(self.fixture["market_json"])
        self.peers = self.root / "industry.json"
        self.peers.write_bytes(self.fixture["industry_json"])
        self.out = self.root / "new-report"

    def kwargs(self):
        return dict(ticker="NVDA", as_of="2026-02-01",
                    originals=self.originals, stock_path=str(self.stock),
                    index_path=str(self.index), output_dir=str(self.out),
                    market_path=str(self.market), industry_path=str(self.peers))

    def cli_argv(self):
        args = ["--ticker", "NVDA", "--as-of", "2026-02-01"]
        for role, path in self.originals.items():
            args += ["--" + role.replace("_", "-"), path]
        return args + [
            "--stock-daily", str(self.stock), "--ndx-daily", str(self.index),
            "--market-json", str(self.market),
            "--industry-json", str(self.peers),
            "--output-dir", str(self.out),
        ]

    def test_real_file_path_full_source_replay_no_network_no_origin_claim(self):
        before = {role: Path(path).read_bytes()
                  for role, path in self.originals.items()}
        with (
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NO SEC GET")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO VENDOR GET")) as vendor,
        ):
            summary = cli.generate(**self.kwargs())
        sec.assert_not_called()
        vendor.assert_not_called()
        self.assertEqual(summary["status"], "LOCAL_ORIGINALS_REPLAYED_UNVERIFIED")
        self.assertEqual(summary["ticker"], "NVDA")
        self.assertEqual(summary["network_requests"], 0)
        self.assertIs(summary["source_rights_verified"], False)
        self.assertFalse(summary["external_sharing_allowed"])
        self.assertEqual(summary["guard_policy_preview"], "HOLD")
        self.assertEqual(len(list(self.out.iterdir())), 2)
        review = (self.out / summary["review_filename"]).read_bytes()
        rights = (self.out / summary["rights_filename"]).read_bytes()
        self.assertEqual(sha256(review).hexdigest(), summary["review_sha256"])
        self.assertEqual(sha256(rights).hexdigest(), summary["rights_sha256"])
        self.assertNotIn(b"<html", review.lower())
        self.assertNotIn(b"Time Series (Daily)", review)
        self.assertEqual(inspect_source_clearance_packet(
            rights, review_packet=review)["status"],
            "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING")
        self.assertEqual(replay_review_packet_from_original_bytes(
            review, sources=self.fixture["sources"],
            stock_raw=self.fixture["stock_raw"],
            index_raw=self.fixture["index_raw"],
            market_json=self.fixture["market_json"],
            industry_json=self.fixture["industry_json"])["status"],
            "PASS_UNVERIFIED_ORIGIN")
        self.assertEqual(before, {role: Path(path).read_bytes()
                                  for role, path in self.originals.items()})

    def test_cli_real_invocation_and_repeated_runs_refuse_overwrite(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(cli.main(self.cli_argv()), 0)
        self.assertIn("LOCAL_ORIGINALS_REPLAYED_UNVERIFIED", stdout.getvalue())
        old = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(self.cli_argv()), 2)
        self.assertEqual(old, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_malformed_ndx_or_sec_original_fails_without_new_directory(self):
        for file in (self.index, Path(self.originals["original_10k"])):
            orig = file.read_bytes()
            try:
                file.write_bytes(b"invalid-format")
                with self.assertRaises(ValueError):
                    cli.generate(**self.kwargs())
                self.assertFalse(self.out.exists())
            finally:
                file.write_bytes(orig)

    def test_oversized_index_is_rejected_before_decode_or_output(self):
        self.index.write_bytes(b"x" * (cli.NDX_MAX + 1))
        with self.assertRaises(ValueError):
            cli.generate(**self.kwargs())
        self.assertFalse(self.out.exists())

    def test_symlink_input_rejected_when_supported(self):
        link = self.root / "stock-symlink.json"
        try:
            link.symlink_to(self.stock)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable without Windows privilege")
        kwargs = dict(self.kwargs(), stock_path=str(link))
        with self.assertRaises(ValueError):
            cli.generate(**kwargs)
        self.assertFalse(self.out.exists())

    def test_output_failure_removes_only_owned_new_files(self):
        original = cli._write_one
        calls = 0
        def fail_second(path, raw):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synth second write failed")
            original(path, raw)
        with patch.object(cli, "_write_one", side_effect=fail_second):
            with self.assertRaises(OSError):
                cli.generate(**self.kwargs())
        self.assertEqual(calls, 2)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.stock.read_bytes(), self.fixture["stock_raw"])

    def test_existing_directory_and_input_parent_symlink_are_fail_closed(self):
        self.out.mkdir()
        marker = self.out / "user_original.txt"
        marker.write_text("KEEP_ME", encoding="utf-8")
        with self.assertRaises(ValueError):
            cli.generate(**self.kwargs())
        self.assertEqual(marker.read_text(encoding="utf-8"), "KEEP_ME")

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_posix_output_not_world_readable(self):
        cli.generate(**self.kwargs())
        self.assertEqual(self.out.stat().st_mode & 0o077, 0)
        for path in self.out.iterdir():
            self.assertEqual(path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
