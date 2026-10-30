"""P22: bind P20 local review SHA256 to exact Guard/SQLite input bytes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.kuodra_loose_sec_compatibility import inspect_loose_sec_files
from test_local_sec_guard_report import fixture


def pins(input_data):
    return {
        "submissions": hashlib.sha256(input_data["submissions_json"]).hexdigest(),
        "companyfacts": hashlib.sha256(input_data["companyfacts_json"]).hexdigest(),
        "original_filing": hashlib.sha256(input_data["original_filing"]).hexdigest(),
    }


class PinnedGuardSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kuodra-p22-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "audit.sqlite"
        self.args = fixture(self.db)

    def test_matching_p20_pins_can_hold_and_write_consented_audit(self):
        args = self.args | {"expected_source_sha256": pins(self.args)}
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_DENIED")) as network:
            actual = review_local_sec_with_guard(**args)
        network.assert_not_called()
        self.assertTrue(actual["operator_reviewed_source_digests_matched"])
        self.assertEqual(actual["guard"]["decision"], "HOLD")
        self.assertTrue(actual["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertFalse(actual["limits"]["external_source_authenticated"])

    def test_each_source_swap_fails_before_creating_sqlite(self):
        for key in ("submissions_json", "companyfacts_json", "original_filing"):
            with self.subTest(swapped=key):
                self.db.unlink(missing_ok=True)
                changed = self.args | {"expected_source_sha256": pins(self.args)}
                changed[key] += b" "
                with self.assertRaisesRegex(
                    ValueError, "OPERATOR_REVIEWED_SOURCE_BYTES_CHANGED"
                ):
                    review_local_sec_with_guard(**changed)
                self.assertFalse(self.db.exists())

    def test_incomplete_and_malformed_pins_never_open_sqlite(self):
        original = pins(self.args)
        bad = [
            {}, {"submissions": original["submissions"]},
            {**original, "original_filing": "a" * 63},
            {**original, "original_filing": "G" * 64},
            {**original, "companyfacts": None},
            {**original, "unexpected": "a" * 64},
        ]
        for item in bad:
            with self.subTest(pin=item):
                with self.assertRaisesRegex(ValueError, "INVALID_OPERATOR_SOURCE_DIGESTS"):
                    review_local_sec_with_guard(
                        **(self.args | {"expected_source_sha256": item})
                    )
                self.assertFalse(self.db.exists())

    def test_existing_unpinned_call_remains_bounded_and_unverified(self):
        actual = review_local_sec_with_guard(**self.args)
        self.assertFalse(actual["operator_reviewed_source_digests_matched"])
        self.assertEqual(actual["guard"]["decision"], "HOLD")
        self.assertFalse(actual["limits"]["external_source_authenticated"])

    def _file_args(self):
        sources = {}
        for key in ("submissions_json", "companyfacts_json", "original_filing"):
            path = self.dir / (key + ".input")
            path.write_bytes(self.args[key])
            sources[key] = path
        kw = self.args
        cmd = [
            sys.executable, "-B", "-m", "proofinvest.local_sec_guard_report",
            "--submissions-json", str(sources["submissions_json"]),
            "--companyfacts-json", str(sources["companyfacts_json"]),
            "--original-file", str(sources["original_filing"]),
            "--cik", kw["cik"], "--accession", kw["accession"],
            "--as-of", kw["as_of"], "--collected-at", kw["collected_at"],
            "--current-end", kw["current_end"], "--prior-end", kw["prior_end"],
            "--needle", kw["needle"], "--run-id", kw["run_id"],
            "--audit-db", str(self.db),
            "--acknowledge-local-audit-persistence",
        ]
        return sources, cmd

    def test_real_p20_preview_hashes_bind_cli_with_explicit_consent(self):
        sources, cmd = self._file_args()
        reviewed = inspect_loose_sec_files(
            submissions_path=sources["submissions_json"],
            companyfacts_path=sources["companyfacts_json"],
            original_path=sources["original_filing"],
            cik=self.args["cik"], accession=self.args["accession"],
            as_of=self.args["as_of"], collected_at=self.args["collected_at"],
        )
        self.assertEqual(reviewed["status"], "operator_review_required")
        hashes = reviewed["source_sha256"]
        cmd += [
            "--expected-submissions-sha256", hashes["submissions"],
            "--expected-companyfacts-sha256", hashes["companyfacts"],
            "--expected-original-sha256", hashes["original_filing"],
        ]
        before = {k: path.read_bytes() for k, path in sources.items()}
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=35, check=False)
        self.assertEqual(result.returncode, 0, result.stderr[:400])
        output = json.loads(result.stdout)
        self.assertTrue(output["operator_reviewed_source_digests_matched"])
        self.assertEqual(output["guard"]["decision"], "HOLD")
        self.assertNotIn(PHRASE, result.stdout)
        self.assertEqual(before, {k: path.read_bytes()
                                  for k, path in sources.items()})
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_cli_changed_file_and_partial_pins_do_not_write(self):
        sources, base = self._file_args()
        digest = pins(self.args)
        hashes = [
            "--expected-submissions-sha256", digest["submissions"],
            "--expected-companyfacts-sha256", digest["companyfacts"],
            "--expected-original-sha256", digest["original_filing"],
        ]
        # Partial hashes fail validation before any read/write.
        first = subprocess.run(base + hashes[:2], capture_output=True,
                               text=True, timeout=35, check=False)
        self.assertEqual(first.returncode, 2)
        self.assertFalse(self.db.exists())
        sources["original_filing"].write_bytes(self.args["original_filing"] + b" ")
        second = subprocess.run(base + hashes, capture_output=True,
                                text=True, timeout=35, check=False)
        self.assertEqual(second.returncode, 2)
        self.assertFalse(self.db.exists())
        self.assertNotIn(PHRASE, second.stderr)

    def test_pinned_preview_requires_historical_observation_not_source_truth(self):
        args = self.args | {"expected_source_sha256": pins(self.args)}
        receipt = review_local_sec_with_guard(**args)
        self.assertTrue(receipt["operator_reviewed_source_digests_matched"])
        self.assertFalse(receipt["limits"]["external_source_authenticated"])
        self.assertFalse(receipt["limits"]["source_rights_verified"])
        self.assertFalse(receipt["limits"]["ai_agent_executed"])


if __name__ == "__main__":
    unittest.main()
