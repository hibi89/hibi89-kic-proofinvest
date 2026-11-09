"""Executable local backend vertical slice: synthetic data only, never public."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

from proofinvest.kuodra_synthetic_demo import (
    run_synthetic_demo, write_synthetic_demo, verify_synthetic_demo)


class KUODRASyntheticDemoTest(TestCase):
    def test_all_three_ingesters_and_ml_stats_run(self):
        report, html = run_synthetic_demo()
        self.assertTrue(report["synthetic_only"])
        self.assertFalse(report["institution_data_used"])
        self.assertEqual(report["guard"], "HOLD")
        self.assertEqual(report["group_time_review"]["scope"], "LOCAL_HYBRID")
        self.assertEqual(report["group_time_review"]["analysis"]["status"],
                         "EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED")
        self.assertEqual(report["document_statistical_review"]["status"],
                         "EXPLORATORY_INDEPENDENCE_UNVERIFIED")
        self.assertEqual(report["document_statistical_review"]["pairs_evaluated"], 1)
        self.assertIn("Content-Security-Policy", html)
        for forbidden in ("fictitiousIssuer0", "fictionalPrivate", "fictionalDocPrivate",
                          "sqlite_master", "<script"):
            self.assertNotIn(forbidden, json.dumps(report) + html)

    def test_deterministic_checksum_outputs(self):
        a, ah = run_synthetic_demo()
        b, bh = run_synthetic_demo()
        self.assertEqual(a, b)
        self.assertEqual(ah, bh)

    def test_no_egress_codepath(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("EGRESS")) as conn:
            run_synthetic_demo()
            conn.assert_not_called()

    def test_create_and_verify_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            manifest = write_synthetic_demo(out)
            self.assertEqual(set(manifest["files"]), {"review.json", "review.html"})
            self.assertEqual(verify_synthetic_demo(out)["guard"], "HOLD")
            with self.assertRaises(FileExistsError):
                write_synthetic_demo(out)
            self.assertEqual(verify_synthetic_demo(out)["status"],
                             "SYNTHETIC_ONLY_RECEIPT_VERIFIED")

    def test_tampered_report_or_html_denied(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            write_synthetic_demo(out)
            page = out / "review.html"
            page.write_text(page.read_text("utf-8") + "modified", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DEMO_VERIFY_CHECKSUM_MISMATCH"):
                verify_synthetic_demo(out)

    def test_symlink_target_denied(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            target = out / "secret.txt"
            target.write_text("never overwrite")
            link = out / "review.json"
            try:
                link.symlink_to(target)
            except (NotImplementedError, OSError):
                self.skipTest("symlink not available")
            with self.assertRaisesRegex(ValueError, "DEMO_OUTPUT_TARGET_DENIED"):
                write_synthetic_demo(out)
            self.assertEqual(target.read_text(), "never overwrite")

    def test_cli_subprocess_run_and_verify_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            home = str(Path(__file__).resolve().parents[1])
            env = {**os.environ, "PYTHONPATH": home}
            commands = [[sys.executable, "-m", "proofinvest.kuodra_synthetic_demo",
                         "--output-dir", td],
                        [sys.executable, "-m", "proofinvest.kuodra_synthetic_demo",
                         "--verify-dir", td]]
            for args in commands:
                r = subprocess.run(args, cwd=home, env=env,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["guard"], "HOLD")
            self.assertTrue((Path(td) / "review.html").exists())
