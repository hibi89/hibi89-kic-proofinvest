"""P21: Windows local SEC 3-file intake without copying/transporting raw data."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML


SCRIPT = Path(__file__).resolve().parents[1] / "verify_sec_local.ps1"


class WindowsSecLocalAcceptanceTests(unittest.TestCase):
    def test_launcher_is_present_and_never_fetches_or_writes(self):
        self.assertTrue(SCRIPT.is_file())
        contents = SCRIPT.read_text(encoding="utf-8")
        for token in (
            "kuodra_loose_sec_compatibility",
            "--submissions",
            "--companyfacts",
            "--original",
            "--collected-at",
            "P21_LOCAL_PREFLIGHT_BLOCKED",
            "P21_LOCAL_INSPECTION_FAILED",
        ):
            self.assertIn(token, contents)
        for forbidden in (
            "Invoke-WebRequest", "Invoke-RestMethod",
            "Start-BitsTransfer", "Out-File", "Set-Content",
            "New-Item", "Add-Content", "Start-Transcript",
        ):
            self.assertNotIn(forbidden, contents)

    def _make_inputs(self, root: Path):
        p = [root / "submissions.json", root / "companyfacts.json",
             root / "original.html"]
        p[0].write_bytes(synthetic_submissions())
        p[1].write_text(json.dumps(synthetic_companyfacts()), encoding="utf-8")
        p[2].write_bytes(SYNTHETIC_HTML)
        return p

    def _cmd(self, folder: Path):
        return [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
            "-SourceDirectory", str(folder),
            "-Cik", SYNTHETIC_CIK, "-Accession", SYNTHETIC_ACCESSION,
            "-AsOf", AS_OF, "-CollectedAt", COLLECTED_AT,
        ]

    def test_windows_offline_invocation_utf8_and_space_in_folder(self):
        if os.name != "nt":
            self.assertIn("SourceDirectory", SCRIPT.read_text(encoding="utf-8"))
            return
        with tempfile.TemporaryDirectory(prefix="kuodra P21 spaced sources ") as root:
            folder = Path(root)
            paths = self._make_inputs(folder)
            initial = [x.read_bytes() for x in paths]
            result = subprocess.run(self._cmd(folder), capture_output=True,
                                    text=True, encoding="utf-8", timeout=50)
            self.assertEqual(result.returncode, 0, result.stderr[:500])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "operator_review_required")
            self.assertFalse(report["source_authenticated"])
            self.assertFalse(report["original_filing_belongs_to_accession_verified"])
            self.assertEqual(report["network_calls"], 0)
            self.assertFalse(report["audit_written"])
            self.assertNotIn(PHRASE, result.stdout)
            self.assertEqual([x.read_bytes() for x in paths], initial)
            self.assertEqual(sorted(folder.iterdir()), sorted(paths))

    def test_windows_missing_original_returns_safe_blocked_json(self):
        if os.name != "nt":
            self.assertIn("exit $code", SCRIPT.read_text(encoding="utf-8"))
            return
        with tempfile.TemporaryDirectory(prefix="kuodra P21 blocked ") as root:
            folder = Path(root)
            paths = self._make_inputs(folder)
            paths[2].unlink()
            result = subprocess.run(self._cmd(folder), capture_output=True,
                                    text=True, encoding="utf-8", timeout=50)
            self.assertEqual(result.returncode, 2, result.stderr[:500])
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "blocked")
            self.assertNotIn(str(folder), result.stdout)
            self.assertEqual(sorted(folder.iterdir()), sorted(paths[:2]))

    def test_windows_rejects_leaf_path_traversal_before_python(self):
        if os.name != "nt":
            self.assertIn("SOURCE_FILENAME_MUST_BE_A_LEAF",
                          SCRIPT.read_text(encoding="utf-8"))
            return
        with tempfile.TemporaryDirectory(prefix="kuodra P21 traversal ") as root:
            folder = Path(root)
            paths = self._make_inputs(folder)
            cmd = self._cmd(folder) + ["-OriginalFile", "..\\original.html"]
            result = subprocess.run(cmd, capture_output=True,
                                    text=True, encoding="utf-8", timeout=50)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(PHRASE, result.stdout)
            self.assertEqual(sorted(folder.iterdir()), sorted(paths))


if __name__ == "__main__":
    unittest.main()
