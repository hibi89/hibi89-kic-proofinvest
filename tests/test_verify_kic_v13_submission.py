"""P133: stdlib-only synthetic tests; never package the private V13 or fitz."""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from scripts import verify_kic_v13_submission as preflight


class _FakePage:
    def __init__(self, number: int, urls: list[str]):
        self.number = number
        self.rect = SimpleNamespace(width=960, height=540)
        self.urls = urls
        self.outside = False

    def get_text(self, mode=None):
        if mode == "words":
            return [(10, 10, 962 if self.outside else 40, 40, "synthetic")]
        return f"PAGE{self.number} SECTION{self.number}"

    def get_links(self):
        return [{"kind": 2, "uri": url} for url in self.urls]


class _FakePDF:
    is_encrypted = False

    def __init__(self):
        self.pages = [_FakePage(i, [f"https://example.org/{i}"] if i <= 5 else [])
                      for i in range(1, 11)]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __len__(self):
        return len(self.pages)

    def __getitem__(self, key):
        return self.pages[key]

    def __iter__(self):
        return iter(self.pages)


class V13PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / preflight.EXPECTED_NAME
        self.original = b"%PDF-1.7\nP133_SYNTHETIC_ONLY\n%%EOF"
        self.path.write_bytes(self.original)
        self.pdf = _FakePDF()
        self.fitz = SimpleNamespace(LINK_URI=2, open=lambda **kwargs: self.pdf)
        self.patches = [
            patch.object(preflight, "EXPECTED_BYTES", len(self.original)),
            patch.object(preflight, "EXPECTED_SHA256", sha256(self.original).hexdigest()),
            patch.object(preflight, "REQUIRED", {i: (f"SECTION{i}",) for i in (2, 3, 4, 5, 7, 8, 9)}),
            patch.object(preflight, "EXPECTED_LINKS",
                         frozenset(f"https://example.org/{i}" for i in range(1, 6))),
            patch.dict(sys.modules, {"fitz": self.fitz}),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

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
        try:
            self.path.symlink_to(other)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symlink privilege unavailable")
            raise
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
        with patch.object(self.fitz, "open", side_effect=RuntimeError("PRIVATE_PATH_SECRET")):
            code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_OPEN_OR_PARSER_FAILED"))
        self.assertNotIn("PRIVATE_PATH_SECRET", json.dumps(result))

    def test_encrypted_pdf_blocks(self):
        self.pdf.is_encrypted = True
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_ENCRYPTED_OR_NOT_TEN_PAGES"))

    def test_page_outside_bounds_blocks(self):
        self.pdf.pages[4].outside = True
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_TEXT_OUTSIDE_PAGE"))

    def test_missing_page_blocks(self):
        self.pdf.pages.pop()
        code, result = self.run_cli()
        self.assertEqual((code, result["reason_code"]), (2, "PDF_ENCRYPTED_OR_NOT_TEN_PAGES"))


if __name__ == "__main__":
    unittest.main()
