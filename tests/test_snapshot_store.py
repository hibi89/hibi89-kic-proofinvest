"""Create-once snapshot and read-only retrieval: no live inputs or API."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest import snapshot_store as store


class SyntheticSnapshotPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def test_first_save_then_read_does_not_recalculate(self):
        self.assertEqual(store.save_synthetic_snapshot(self.directory), "CREATED")
        target = self.directory / "synthetic_snapshot_v1.json"
        self.assertTrue(target.is_file())
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("Recalculated during read")):
            saved = store.read_synthetic_snapshot(self.directory)
        self.assertEqual(saved["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(saved["risk"]["표시 비율"], "266.67")
        self.assertFalse(saved["authenticated_external_source"])

    def test_second_save_reuses_snapshot_without_recalculating_or_overwrite(self):
        store.save_synthetic_snapshot(self.directory)
        before = (self.directory / "synthetic_snapshot_v1.json").read_bytes()
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("Duplicate computation")):
            self.assertEqual(store.save_synthetic_snapshot(self.directory), "REUSED_NO_RECALCULATION")
        self.assertEqual((self.directory / "synthetic_snapshot_v1.json").read_bytes(), before)

    def test_read_missing_snapshot_never_computes(self):
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("Must not calculate")):
            with self.assertRaisesRegex(ValueError, "missing or corrupt"):
                store.read_synthetic_snapshot(self.directory)

    def test_corrupt_and_modified_payload_fail_closed(self):
        store.save_synthetic_snapshot(self.directory)
        f = self.directory / "synthetic_snapshot_v1.json"
        record = json.loads(f.read_text(encoding="utf-8"))
        record["payload"]["risk"]["표시 비율"] = "999.99"
        f.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            store.read_synthetic_snapshot(self.directory)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            store.save_synthetic_snapshot(self.directory)

    def test_checksum_does_not_grant_fake_external_authenticity(self):
        store.save_synthetic_snapshot(self.directory)
        f = self.directory / "synthetic_snapshot_v1.json"
        record = json.loads(f.read_text(encoding="utf-8"))
        record["payload"]["authenticated_external_source"] = True
        record["payload_sha256"] = hashlib.sha256(store._canonical(record["payload"])).hexdigest()
        f.write_bytes(store._canonical(record))
        with self.assertRaisesRegex(ValueError, "synthetic, unverified"):
            store.read_synthetic_snapshot(self.directory)

    def test_changed_fixture_digest_rejects_stale_read_without_recalc(self):
        store.save_synthetic_snapshot(self.directory)
        with patch.object(store, "_fixture_digest", return_value="0" * 64):
            with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("Bad recompute")):
                with self.assertRaisesRegex(ValueError, "stale snapshot"):
                    store.read_synthetic_snapshot(self.directory)

    def test_refuses_storage_inside_public_repository(self):
        with self.assertRaisesRegex(ValueError, "public source repository"):
            store.save_synthetic_snapshot(store._REPO_ROOT)

    def test_rejects_symlinked_cache_file(self):
        store.save_synthetic_snapshot(self.directory)
        f = self.directory / "synthetic_snapshot_v1.json"
        f.unlink()
        try:
            f.symlink_to(store._FIXTURE)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink privilege")
        with self.assertRaisesRegex(ValueError, "symlink"):
            store.read_synthetic_snapshot(self.directory)

    def test_stored_receipt_reports_synthetic_lineage_without_recalculating(self):
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("recalculation")):
            # Explicit initial save occurs before any read-only assertions.
            with self.assertRaisesRegex(ValueError, "missing or corrupt"):
                store.read_synthetic_snapshot_with_provenance(self.directory)
        store.save_synthetic_snapshot(self.directory)
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("recalculation")):
            result = store.read_synthetic_snapshot_with_provenance(self.directory)
        self.assertEqual(result["view"]["risk"]["표시 비율"], "266.67")
        p = result["provenance"]
        self.assertEqual(p["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(p["source_path"], "fixtures/synthetic_annual.json")
        self.assertEqual(p["fixture_sha256"], store._fixture_digest())
        self.assertEqual(p["integrity_status"], "LOCAL_CHECKSUM_MATCH_ONLY")
        self.assertFalse(p["external_source_authenticated"])
        self.assertFalse(p["calculation_repeated_on_read"])

    def test_stored_receipt_rejects_corruption_without_fallback(self):
        store.save_synthetic_snapshot(self.directory)
        f = self.directory / "synthetic_snapshot_v1.json"
        f.write_text("BROKEN", encoding="utf-8")
        with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("fallback calculation")):
            with self.assertRaisesRegex(ValueError, "missing or corrupt"):
                store.read_synthetic_snapshot_with_provenance(self.directory)

    def test_snapshot_content_limited_to_synthetic_fields(self):
        store.save_synthetic_snapshot(self.directory)
        payload = store.read_synthetic_snapshot(self.directory)
        self.assertEqual(set(payload), {
            "mode", "source_kind", "year", "authenticated_external_source",
            "live_api_called", "financial_rows", "checks", "risk",
        })
        self.assertTrue(all(r["범위"] in ("CFS", "OFS") for r in payload["financial_rows"]))
        self.assertNotIn("OPENDART_API_KEY", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
