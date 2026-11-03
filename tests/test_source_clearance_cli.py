"""P168 user-facing offline matching report verifier; never grants usage rights."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.source_clearance_cli import main
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload


class DownloadPairCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = build_offline_initial_review(**payload())
        assert result["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
        cls.packet = result["review_packet"]
        cls.gaps = result["source_clearance_report"]

    def run_cli(self, packet=None, gaps=None):
        if packet is None:
            packet = self.packet
        if gaps is None:
            gaps = self.gaps
        with tempfile.TemporaryDirectory(prefix="kuodra-clearance-cli-") as folder:
            a, b = Path(folder) / "packet.json", Path(folder) / "rights.json"
            a.write_bytes(packet)
            b.write_bytes(gaps)
            out = StringIO()
            with (
                redirect_stdout(out),
                patch("urllib.request.urlopen",
                      side_effect=AssertionError("CLI_NETWORK_FORBIDDEN")) as net,
            ):
                code = main([str(a), str(b)])
            net.assert_not_called()
            return code, json.loads(out.getvalue())

    def test_valid_local_pair_does_not_claim_legal_clearance(self):
        code, result = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(result["status"],
                         "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING")
        self.assertEqual(result["release_gate"], "HOLD")
        self.assertIs(result["rights_verified"], False)
        self.assertIs(result["public_submission_allowed"], False)
        self.assertIs(result["publisher_origin_authenticated"], False)
        self.assertEqual(result["network_requests"], 0)
        self.assertNotIn("close_observations", repr(result))

    def test_changed_receipt_and_missing_data_fail_closed(self):
        for packet, gaps in (
            (self.packet, self.gaps + b" "),
            (self.packet + b" ", self.gaps),
            (self.packet, b"{}"),
            (self.packet * 4, self.gaps),
        ):
            with self.subTest(packet_bytes=len(packet),gap_bytes=len(gaps)):
                code, result = self.run_cli(packet, gaps)
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["release_gate"], "HOLD")
                self.assertIs(result["rights_verified"], False)


if __name__ == "__main__":
    unittest.main()
