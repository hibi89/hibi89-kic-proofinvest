"""Public synthetic judge pack: 3 real code paths, 9 files and immutable ZIP."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from scripts.sec_guard_judge_pack import (
    MANIFEST, SCHEMA, build_bytes, main, verify_bytes,
)


class SecGuardJudgePackTests(unittest.TestCase):
    def test_deterministic_three_case_pack_and_manifest(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as net:
            raw = build_bytes()
            self.assertEqual(raw, build_bytes())
            result = verify_bytes(raw)
        net.assert_not_called()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["cases"], 3)
        self.assertEqual(result["files"], 9)
        self.assertFalse(result["external_source_authenticated"])
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = set(z.namelist())
            self.assertEqual(len(names), 10)
            manifest = json.loads(z.read(MANIFEST))
            self.assertEqual(manifest["evidence_class"],
                             "SYNTHETIC_ONLY_UNVERIFIED")
            for case in ("matched", "conflict", "script"):
                receipt = json.loads(z.read(case + ".json"))
                text = z.read(case + ".md").decode("utf-8")
                self.assertIn("SYNTHETIC / UNVERIFIED", text)
                self.assertIn(receipt["report"]["audit"]["event_hash"], text)
                self.assertIn(case + ".md", manifest["file_list"])
                page = z.read(case + ".html").decode("utf-8")
                self.assertIn('Content-Security-Policy', page)
                self.assertIn('UNVERIFIED LOCAL FILES', page)
                self.assertIn(receipt["report"]["audit"]["event_hash"], page)
                self.assertIn(
                    receipt["report"]["source"]["archived_original_sha256"], page
                )
                self.assertNotIn("<script", page.lower())
                self.assertNotIn("https://", page)
                self.assertIn(case + ".html", manifest["file_list"])

    def test_html_reports_show_distinct_hold_reject_and_unavailable_states(self):
        archive = build_bytes()
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for case, expect in (
                ("matched", 'class="state"'),
                ("conflict", 'class="state reject"'),
                ("script", "unavailable"),
            ):
                with self.subTest(case=case):
                    page = z.read(case + ".html").decode("utf-8")
                    self.assertIn(expect, page)
                    self.assertIn("실거래 불가", page)
                    self.assertIn("UNVERIFIED LOCAL FILES", page)

    def test_any_byte_tampering_fails_exact_archive_check(self):
        orig = build_bytes()
        for index in (0, len(orig)//2, len(orig)-1):
            mutated = bytearray(orig)
            mutated[index] ^= 1
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    verify_bytes(bytes(mutated))
        with self.assertRaises(ValueError):
            verify_bytes(orig + b"UNEXPECTED_TRAILER")

    def test_zip_repacked_with_extra_path_is_rejected(self):
        raw = build_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = {n: z.read(n) for n in z.namelist()}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, content in members.items():
                z.writestr(name, content)
            z.writestr("../real-issuer.pdf", b"not allowed")
        with self.assertRaisesRegex(ValueError, "MISMATCH"):
            verify_bytes(buf.getvalue())

    def test_cli_build_verify_and_never_replace_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-guard.zip"
            self.assertEqual(main(["build", str(path)]), 0)
            first = path.read_bytes()
            self.assertEqual(main(["verify", str(path)]), 0)
            with self.assertRaises(FileExistsError):
                main(["build", str(path)])
            self.assertEqual(path.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
