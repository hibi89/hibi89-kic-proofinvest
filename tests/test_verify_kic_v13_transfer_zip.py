"""P134 synthetic offline transport tests, stdlib only, no private PDF bytes."""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from scripts import verify_kic_v13_transfer_zip as gate


class P134TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / gate.ARCHIVE_NAME
        self.pdf = b"%PDF-1.7\nP134_SYNTHETIC_BYTES_ONLY\n%%EOF\n"
        self.patches = [
            patch.object(gate, "PDF_BYTES", len(self.pdf)),
            patch.object(gate, "PDF_SHA256", sha256(self.pdf).hexdigest()),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.build()

    def build(self, *, pdf=None, manifest=None, add=None, compression=ZIP_STORED):
        pdf = self.pdf if pdf is None else pdf
        expected = (gate.PDF_SHA256 + "  " + gate.PDF_NAME + "\n").encode("utf-8")
        manifest = expected if manifest is None else manifest
        stream = BytesIO()
        with ZipFile(stream, "w", compression=compression) as z:
            z.writestr(gate.PDF_NAME, pdf)
            z.writestr(gate.SUM_NAME, manifest)
            if add:
                z.writestr(add, b"other")
        self.data = stream.getvalue()
        self.path.write_bytes(self.data)
        self.patch_zip = [
            patch.object(gate, "ARCHIVE_BYTES", len(self.data)),
            patch.object(gate, "ARCHIVE_SHA256", sha256(self.data).hexdigest()),
        ]

    def cli(self, path=None, *, pin_current=True):
        with (self.patch_zip[0] if pin_current else patch.object(gate, "ARCHIVE_BYTES", gate.ARCHIVE_BYTES)):
            with (self.patch_zip[1] if pin_current else patch.object(gate, "ARCHIVE_SHA256", gate.ARCHIVE_SHA256)):
                output = StringIO()
                with redirect_stdout(output):
                    code = gate.main(["--zip", str(self.path if path is None else path)])
        return code, json.loads(output.getvalue())

    def test_clean_synthetic_archive_passes_without_false_claims(self):
        code, r = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(r["pdf_bytes"], len(self.pdf))
        self.assertFalse(r["owner_approved"])
        self.assertFalse(r["daker_submission_confirmed"])
        self.assertEqual(r["network_requests"], 0)
        self.assertEqual(r["disk_writes"], 0)

    def test_p172_exact_transfer_is_accepted_without_owner_approval(self):
        # Simulate a previously privately frozen archive using synthetic
        # bytes. The public real P172 SHA remains pinned in the source.
        latest = self.path.with_name(gate.LATEST_ARCHIVE_NAME)
        latest.write_bytes(self.data)
        before = latest.read_bytes()
        with (patch.object(gate, "LATEST_ARCHIVE_BYTES", len(self.data)),
              patch.object(gate, "LATEST_ARCHIVE_SHA256",
                           sha256(self.data).hexdigest())):
            code, result = self.cli(latest, pin_current=False)
        self.assertEqual(code, 0)
        self.assertEqual(result["transfer_version"], "P172")
        self.assertEqual(
            result["status"],
            "EXACT_P172_V13_ZIP_AND_PDF_BYTES_PASS_OWNER_APPROVAL_PENDING",
        )
        self.assertEqual(result["archive_sha256"], sha256(before).hexdigest())
        self.assertFalse(result["owner_approved"])
        self.assertFalse(result["daker_submission_confirmed"])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["disk_writes"], 0)
        self.assertEqual(latest.read_bytes(), before)

    def test_p172_name_does_not_accept_old_p133_bytes(self):
        latest = self.path.with_name(gate.LATEST_ARCHIVE_NAME)
        latest.write_bytes(self.data)
        with patch.object(gate, "LATEST_ARCHIVE_BYTES", len(self.data)):
            code, result = self.cli(latest, pin_current=False)
        self.assertEqual((code, result["reason_code"]),
                         (2, "ZIP_SHA256_MISMATCH"))

    def test_p133_legacy_transfer_still_accepted(self):
        code, result = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(result["transfer_version"], "P133")
        self.assertEqual(result["archive_sha256"],
                         sha256(self.data).hexdigest())

    def test_filename_mismatch(self):
        code, r = self.cli(self.path.with_name("wrong.zip"))
        self.assertEqual((code, r["reason_code"]), (2, "WRONG_ZIP_NAME_OR_SYMLINK"))

    def test_symlink_blocked(self):
        original = self.path.with_name("source.zip")
        self.path.replace(original)
        self.path.symlink_to(original)
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "WRONG_ZIP_NAME_OR_SYMLINK"))

    def test_missing_archive_path_sanitized(self):
        self.path.unlink()
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_READ_FAILED"))
        self.assertNotIn(self.temp.name, json.dumps(r))

    def test_archive_size_changed(self):
        self.path.write_bytes(self.data + b"x")
        code, r = self.cli(pin_current=False)
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_SIZE_OR_TYPE_CHANGED"))

    def test_archive_same_size_tamper(self):
        other = bytearray(self.data)
        other[-11] ^= 1
        self.path.write_bytes(other)
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_SHA256_MISMATCH"))

    def test_extra_entry_rejected(self):
        self.build(add="EXTRA")
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_MEMBERS_UNEXPECTED"))

    def test_traversal_entry_rejected(self):
        self.build(add="../outside.pdf")
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_MEMBERS_UNEXPECTED"))

    def test_wrong_pdf_bytes_even_if_archive_hash_is_accepted(self):
        self.build(pdf=b"%PDF-1.7\nNOT_APPROVED\n%%EOF\n")
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_INNER_SIZE_CHANGED"))

    def test_same_size_pdf_tamper_detected(self):
        other = bytearray(self.pdf)
        other[12] ^= 1
        self.build(pdf=bytes(other))
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_INNER_PDF_HASH_MISMATCH"))

    def test_manifest_mismatch(self):
        good = (gate.PDF_SHA256 + "  " + gate.PDF_NAME + "\n").encode("utf-8")
        self.build(manifest=b"0" + good[1:])
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_CHECKSUM_MANIFEST_MISMATCH"))

    def test_deflate_blocked_for_exact_transfer(self):
        self.build(compression=ZIP_DEFLATED)
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_MEMBERS_UNEXPECTED"))

    def test_corrupt_archive_rejected_without_traceback(self):
        self.data = b"R" * 40
        self.path.write_bytes(self.data)
        self.patch_zip = [patch.object(gate, "ARCHIVE_BYTES", len(self.data)),
                          patch.object(gate, "ARCHIVE_SHA256", sha256(self.data).hexdigest())]
        code, r = self.cli()
        self.assertEqual((code, r["reason_code"]), (2, "ZIP_UNREADABLE"))


if __name__ == "__main__":
    unittest.main()
