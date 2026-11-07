"""Synthetic-only read-only tests for the no-dependency V13 upload gate."""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import verify_kic_v13_upload_candidate as validator


class UploadGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / validator.EXPECTED_NAME
        self.payload = b"%PDF-1.7\nsynthetic-test\n%%EOF\n"
        self.file.write_bytes(self.payload)
        self.patches = [
            patch.object(validator, "EXPECTED_SIZE", len(self.payload)),
            patch.object(validator, "EXPECTED_SHA256", sha256(self.payload).hexdigest()),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def check(self, path=None):
        out = StringIO()
        with redirect_stdout(out):
            exit_code = validator.main(["--pdf", str(path if path is not None else self.file)])
        return exit_code, json.loads(out.getvalue())

    def test_valid(self):
        before = self.file.read_bytes()
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertFalse(result["daker_submitted"])
        self.assertFalse(result["official_final_submission_confirmed"])
        self.assertFalse(result["owner_document_approval_recorded"])
        self.assertEqual(result["approval_status"], "OWNER_EXPLICIT_APPROVAL_REQUIRED")
        self.assertEqual(result["status"], "EXACT_FROZEN_V13_BYTES_PASS_OWNER_APPROVAL_PENDING")
        self.assertFalse(result["file_changed"])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(self.file.read_bytes(), before)

    def test_byte_identity_is_not_owner_approval_and_not_a_portal_receipt(self):
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertIn("OWNER_APPROVAL_PENDING", result["status"])
        self.assertNotIn("EXACT_APPROVED_V13_BYTES", result["status"])
        self.assertIs(result["owner_document_approval_recorded"], False)
        self.assertIs(result["official_final_submission_confirmed"], False)
        self.assertIs(result["daker_submitted"], False)

    def test_wrong_filename(self):
        code, result = self.check(self.file.with_name("different.pdf"))
        self.assertEqual((code, result["reason_code"]), (2, "WRONG_FILE_NAME"))

    def test_missing(self):
        self.file.unlink()
        code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "FILE_NOT_ACCESSIBLE"))
        self.assertNotIn(self.temp.name, json.dumps(result))

    def test_symlink(self):
        actual = self.file.with_name("actual.pdf")
        self.file.replace(actual)
                try:
            self.file.symlink_to(actual)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable")
            raise
        code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "FILE_LINK_OR_NOT_REGULAR"))

    def test_changed_size(self):
        self.file.write_bytes(self.payload + b"0")
        code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "FILE_SIZE_MISMATCH"))

    def test_same_size_tamper(self):
        modified = bytearray(self.payload)
        modified[10] ^= 1
        self.file.write_bytes(modified)
        code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "FILE_SHA256_MISMATCH"))

    def test_bad_signature_with_new_digest(self):
        modified = b"!" + self.payload[1:]
        self.file.write_bytes(modified)
        with patch.object(validator, "EXPECTED_SHA256", sha256(modified).hexdigest()):
            code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_SIGNATURE_INVALID"))

    def test_directory_instead_of_pdf(self):
        self.file.unlink()
        self.file.mkdir()
        code, result = self.check()
        self.assertEqual((code, result["reason_code"]), (2, "FILE_LINK_OR_NOT_REGULAR"))


if __name__ == "__main__":
    unittest.main()
