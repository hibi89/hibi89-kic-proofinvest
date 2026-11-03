"""P133: synthetic-only offline tests; no private V13 PDF distributed."""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import fitz

from scripts import verify_kic_v13_submission as preflight


class V13PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / preflight.EXPECTED_NAME
        self.urls = {f"https://example.org/evidence/{i}" for i in range(5)}
        document = fitz.open()
        for index in range(10):
            page = document.new_page(width=960, height=540)
            page.insert_text((50, 60), f"page{index+1} SECTION{index+1}")
            if index < 5:
                page.insert_link({"kind": fitz.LINK_URI,
                                  "from": fitz.Rect(50, 80, 200, 100),
                                  "uri": f"https://example.org/evidence/{index}"})
        self.original = document.tobytes()
        document.close()
        self.path.write_bytes(self.original)
        self.patches = [
            patch.object(preflight, "EXPECTED_BYTES", len(self.original)),
            patch.object(preflight, "EXPECTED_SHA256", sha256(self.original).hexdigest()),
            patch.object(preflight, "REQUIRED", {i: (f"SECTION{i}",) for i in (2, 3, 4, 5, 7, 8, 9)}),
            patch.object(preflight, "EXPECTED_LINKS", frozenset(self.urls)),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_cli(self, path=None):
        out = StringIO()
        with redirect_stdout(out):
            code = preflight.main(["--pdf", str(path or self.path)])
        return code, json.loads(out.getvalue())

    def test_valid_synthetic_pdf_has_no_false_submission_claim(self):
        code, result = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(result["page_count"], 10)
        self.assertFalse(result["owner_approved"])
        self.assertFalse(result["daker_submission_confirmed"])
        self.assertFalse(result["official_template_binary_verified"])
        self.assertEqual(result["network_requests"], 0)

    def test_wrong_file_name_blocks(self):
        code, result = self.run_cli(self.path.with_name("wrong.pdf"))
        self.assertEqual((code, result["reason_code"]), (2, "WRONG_PDF_FILENAME_OR_SYMLINK"))

    def test_nonexistent_file_sanitizes_local_path(self):
        self.path.unlink()
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_OPEN_OR_PARSER_FAILED"))
        self.assertNotIn(self.tmp.name, json.dumps(result))

    def test_symlink_blocks(self):
        other = self.path.with_name("source.pdf")
        self.path.replace(other)
        self.path.symlink_to(other)
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "WRONG_PDF_FILENAME_OR_SYMLINK"))

    def test_modified_size_blocks(self):
        self.path.write_bytes(self.original + b"a")
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_SIZE_OR_TYPE_CHANGED"))

    def test_same_size_tamper_blocks(self):
        changed = bytearray(self.original)
        changed[15] ^= 1
        self.path.write_bytes(changed)
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_SHA256_MISMATCH"))

    def test_corrupt_magic_with_patched_hash_blocks(self):
        changed = b"!" + self.original[1:]
        self.path.write_bytes(changed)
        with patch.object(preflight, "EXPECTED_SHA256", sha256(changed).hexdigest()):
            code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "INVALID_PDF_MAGIC_OR_TRAILER"))

    def test_missing_required_section_blocks(self):
        with patch.object(preflight, "REQUIRED", {2: ("MISSING_HEADING",)}):
            code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "MISSING_REQUIRED_SECTION_PAGE_2"))

    def test_wrong_links_blocks(self):
        with patch.object(preflight, "EXPECTED_LINKS", frozenset({"https://example.org/different"})):
            code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_LINK_SET_CHANGED"))

    def test_pdf_parser_error_sanitized(self):
        with patch("fitz.open", side_effect=RuntimeError("PRIVATE_PATH_SECRET")):
            code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_OPEN_OR_PARSER_FAILED"))
        self.assertNotIn("PRIVATE_PATH_SECRET", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
