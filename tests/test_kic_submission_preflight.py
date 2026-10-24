"""Only synthetic bytes are exercised; private PDF stays out of GitHub."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import kic_submission_preflight as guard


class SubmissionGuardTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.good = b"%PDF-1.7\nsynthetic unit-test bytes only\n"
        self.digest = hashlib.sha256(self.good).hexdigest()
        self.path = self.root / "private_preflight.pdf"
        self.path.write_bytes(self.good)

    def verify(self, path=None, **changes):
        return guard.verify_candidate(
            self.path if path is None else path,
            expected_sha256=changes.get("sha", self.digest),
            expected_bytes=changes.get("size", len(self.good)),
        )

    def test_synthetic_matching_bytes_only_ready_for_user_review(self):
        verdict = self.verify()
        self.assertEqual(verdict["decision"], "READY_FOR_USER_REVIEW_NOT_SUBMITTED")
        self.assertTrue(verdict["matched_pinned_byte_identity"])
        self.assertFalse(verdict["officially_submitted"])
        self.assertFalse(verdict["page_count_rechecked_in_this_run"])
        self.assertEqual(verdict["prior_private_audit_page_count"], 10)
        self.assertFalse(verdict["daker_upload_authority_verified"])

    def test_wrong_checksum_blocks_even_if_pdf_header_is_valid(self):
        self.assertEqual(self.verify(sha="0" * 64)["reason"], "CHECKSUM_MISMATCH")

    def test_wrong_size_blocks(self):
        self.assertEqual(self.verify(size=len(self.good) + 1)["reason"], "BYTE_SIZE_MISMATCH")

    def test_corrupt_nonpdf_header_blocks(self):
        self.path.write_bytes(b"HELLO" + self.good[5:])
        self.assertEqual(self.verify()["reason"], "INVALID_PDF_HEADER")

    def test_invalid_expectation_blocks(self):
        with self.assertRaisesRegex(ValueError, "Invalid expected digest"):
            self.verify(sha="not-a-hash")
        with self.assertRaisesRegex(ValueError, "Invalid expected byte count"):
            self.verify(size=0)

    def test_missing_and_directory_are_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.verify(self.root / "missing.pdf")
        with self.assertRaisesRegex(ValueError, "ordinary file"):
            self.verify(self.root)

    def test_symlink_is_rejected(self):
        link = self.root / "link.pdf"
        try:
            link.symlink_to(self.path)
        except (NotImplementedError, OSError):
            self.skipTest("Symlink creation unsupported")
        with self.assertRaisesRegex(ValueError, "Symlinked"):
            self.verify(link)

    def test_cli_rejects_fake_pdf_without_private_path_in_output(self):
        proc = subprocess.run(
            [sys.executable, str(Path(guard.__file__)), str(self.path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        report = json.loads(proc.stdout)
        self.assertEqual(report["decision"], "DO_NOT_UPLOAD")
        self.assertNotIn(str(self.root), proc.stdout + proc.stderr)
        self.assertFalse(report["officially_submitted"])


if __name__ == "__main__":
    unittest.main()
