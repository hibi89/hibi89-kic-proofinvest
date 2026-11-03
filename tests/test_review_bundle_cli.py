"""P171 end-user offline reviewer ZIP validation command."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.review_bundle_cli import main
from proofinvest.ticker_review_bundle import build_review_bundle_bytes
from tests.test_ticker_review_bundle import originals


class ReviewerZipCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p, lineage = originals(True)
        cls.bundle = build_review_bundle_bytes(
            review_packet=p["review_packet"],
            rights_gap_report=p["source_clearance_report"],
            csv_lineage=lineage,
        )

    def invoke(self, raw):
        with tempfile.TemporaryDirectory(prefix="kuodra-p171-cli-") as tmp:
            path = Path(tmp) / "review.zip"
            path.write_bytes(raw)
            output = StringIO()
            with (
                redirect_stdout(output),
                patch("urllib.request.urlopen",
                      side_effect=AssertionError("NO_EXTERNAL_HTTP")) as net,
            ):
                code = main([str(path)])
            net.assert_not_called()
            return code, json.loads(output.getvalue())

    def test_downloaded_bundle_verifies_without_extracting_or_approving(self):
        code, result = self.invoke(self.bundle)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"],
                         "INTERNAL_CONTENT_VERIFIED_ORIGIN_RIGHTS_PENDING")
        self.assertEqual(result["files_verified"], 4)
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        self.assertIs(result["source_rights_verified"], False)
        self.assertIs(result["contest_submission_approved"], False)
        self.assertEqual(result["network_requests"], 0)

    def test_bad_or_large_bundle_fails_closed_without_source_echo(self):
        for raw in (b"{}", self.bundle + b"X"*150001):
            with self.subTest(bytes=len(raw)):
                code, result = self.invoke(raw)
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "INVALID_REVIEW_BUNDLE")
                self.assertIs(result["source_rights_verified"], False)


if __name__ == "__main__":
    unittest.main()
