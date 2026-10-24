"""Offline recovery archive: deterministic, strictly allowlisted and restorable."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import synthetic_demo_bundle as bundle


class SyntheticRecoveryBundleTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.archive = self.root / "demo.zip"

    def test_deterministic_and_valid_manifest(self):
        a = bundle.build_bytes()
        b = bundle.build_bytes()
        self.assertEqual(a, b)
        self.archive.write_bytes(a)
        restored = bundle.read_verified(self.archive)
        self.assertEqual(set(restored), set(bundle.SOURCES))
        fixture = json.loads(restored["fixtures/synthetic_annual.json"].decode("utf-8"))
        self.assertEqual(len(fixture), 4)
        self.assertTrue(all(row["rcept_no"] == "" for row in fixture))
        with zipfile.ZipFile(self.archive, "r") as z:
            manifest = json.loads(z.read(bundle.MANIFEST).decode("utf-8"))
        self.assertEqual(manifest["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertIs(manifest["officially_submitted"], False)

    def test_public_bundle_excludes_private_submissions_and_keys(self):
        self.archive.write_bytes(bundle.build_bytes())
        contents = bundle.read_verified(self.archive)
        self.assertNotIn("docs/roles/lead/MASTER_PROGRESS.json", contents)
        self.assertFalse(any(name.endswith((".pdf", ".pptx", ".env", ".sqlite", ".db")) for name in contents))
        self.assertTrue(all(name.startswith("proofinvest/") or name in (
            "README.md", "requirements-ui.txt", "streamlit_app.py", "fixtures/synthetic_annual.json"
        ) for name in contents))

    def test_tampered_code_rejected_even_when_zip_crc_valid(self):
        self.archive.write_bytes(bundle.build_bytes())
        original = bundle.read_verified(self.archive)
        original["proofinvest/engine.py"] += b"\n# TAMPERED\n"
        # Re-pack entries while keeping original manifest/hash to simulate corruption.
        with zipfile.ZipFile(self.archive, "r") as z:
            manifest = z.read(bundle.MANIFEST)
        with zipfile.ZipFile(self.archive, "w") as z:
            for name, data in {**original, bundle.MANIFEST: manifest}.items():
                z.writestr(bundle._entry(name, data), data)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            bundle.read_verified(self.archive)

    def test_extra_archive_path_is_rejected_before_extract(self):
        blob = bundle.build_bytes()
        self.archive.write_bytes(blob)
        with zipfile.ZipFile(self.archive, "a") as z:
            z.writestr("../private.pdf", b"NO")
        with self.assertRaisesRegex(ValueError, "unapproved paths"):
            bundle.read_verified(self.archive)
        path = self.root / "recover"
        with self.assertRaisesRegex(ValueError, "unapproved paths"):
            bundle.extract_verified(self.archive, path)
        self.assertFalse(path.exists())

    def test_verified_bundle_recovers_core_cli_independently(self):
        self.archive.write_bytes(bundle.build_bytes())
        target = self.root / "fresh"
        bundle.extract_verified(self.archive, target)
        self.assertTrue((target / "proofinvest" / "snapshot_store.py").is_file())
        p = subprocess.run(
            [sys.executable, "-m", "proofinvest", "--claim-revenue-growth-pct", "20"],
            cwd=target, capture_output=True, text=True, check=True,
        )
        report = json.loads(p.stdout)
        self.assertEqual(report["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(report["status"], "demo_not_real")

    def test_refuses_overwriting_existing_restore_directory(self):
        self.archive.write_bytes(bundle.build_bytes())
        target = self.root / "target"
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "must not exist"):
            bundle.extract_verified(self.archive, target)


if __name__ == "__main__":
    unittest.main()
