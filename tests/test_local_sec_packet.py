"""Offline local SEC-shaped triple-file integration and adversarial failure tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.local_sec_packet import (
    _read_regular_local, build_local_sec_review_packet,
)


def _parts():
    return {
        "submissions_json": synthetic_submissions(),
        "companyfacts_json": json.dumps(synthetic_companyfacts()).encode("utf-8"),
        "original_filing": SYNTHETIC_HTML,
        "cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "as_of": AS_OF,
        "collected_at": COLLECTED_AT,
        "current_end": "2025-09-30",
        "prior_end": "2024-09-30",
        "needle": PHRASE,
        "claimed_growth_pct": "100.00",
    }


class OfflineLocalSecPacketTests(unittest.TestCase):
    def test_real_canonical_triple_file_e2e_and_negative_trust(self):
        result = build_local_sec_review_packet(**_parts())
        self.assertEqual(result["schema"], "proofinvest.offline-local-sec-review.v1")
        self.assertEqual(result["status"], "reviewable_untrusted_local_evidence")
        self.assertEqual(result["mode"], "LOCAL_FILES_OFFLINE_UNAUTHENTICATED")
        self.assertEqual(result["financial"]["growth_pct"], "100.00")
        self.assertEqual(result["financial"]["status"], "calculated_unverified")
        self.assertEqual(result["source"]["literal_occurrences"], 1)
        self.assertFalse(result["source"]["span_proves_financial_claim"])
        self.assertTrue(all(x is False for x in result["attestations"].values()))
        self.assertEqual(result, build_local_sec_review_packet(**_parts()))

    def test_mismatched_cik_accession_and_filing_future_fail(self):
        for wrong in (
            {"cik": "0000000002"},
            {"accession": "0000000002-25-000001"},
            {"accession": "0000000001-25-999999"},
            {"as_of": "2025-10-14"},
        ):
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValueError):
                    build_local_sec_review_packet(**(_parts() | wrong))

    def test_future_collected_at_and_no_timezone_fail(self):
        for stamp in ("2025-10-17T00:00:00Z", "2025-10-16T12:00:00",
                      "2025-10-16T23:59:59-04:00", "invalid"):
            with self.subTest(stamp=stamp):
                with self.assertRaises(ValueError):
                    build_local_sec_review_packet(**(_parts() | {"collected_at": stamp}))

    def test_ambiguous_or_missing_source_phrase_fails(self):
        for mutation in (
            {"original_filing": SYNTHETIC_HTML + PHRASE.encode()},
            {"needle": "NOT_PRESENT_ANYWHERE"},
            {"needle": "<script><" },
            {"needle": "\n"},
        ):
            with self.subTest(keys=list(mutation)):
                with self.assertRaises(ValueError):
                    build_local_sec_review_packet(**(_parts() | mutation))

    def test_numeric_conflict_retained_but_not_authenticated(self):
        result = build_local_sec_review_packet(
            **(_parts() | {"claimed_growth_pct": "300.00"}))
        self.assertEqual(result["financial"]["status"], "conflict")
        self.assertEqual(result["financial"]["reason_code"], "GROWTH_CLAIM_CONFLICT")
        self.assertFalse(result["attestations"]["financial_values_authenticated"])

    def test_invalid_financial_rows_fail_closed(self):
        broken = synthetic_companyfacts()
        broken["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"][0]["val"] = "not a number"
        raw = json.dumps(broken).encode()
        with self.assertRaisesRegex(ValueError, "NUMERIC_UNAVAILABLE"):
            build_local_sec_review_packet(**(_parts() | {"companyfacts_json": raw}))

    def test_json_duplicate_keys_and_nonfinite_values_rejected(self):
        for raw in (b'{"cik":1,"cik":2}', b'{"cik":1,"x":NaN}', b'{"cik":1,"x":Infinity}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    build_local_sec_review_packet(**(_parts() | {"companyfacts_json": raw}))

    def test_no_network_or_implicit_sec_authentication(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as outbound:
            report = build_local_sec_review_packet(**_parts())
        outbound.assert_not_called()
        self.assertFalse(report["attestations"]["live_sec_http_called"])

    def test_truncated_caller_original_is_not_claimed_read(self):
        with self.assertRaises(ValueError):
            build_local_sec_review_packet(**(_parts() | {"original_filing": b""}))

    def test_filesystem_symlink_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "real.json"
            src.write_bytes(synthetic_submissions())
            dest = Path(root) / "alias.json"
            try:
                dest.symlink_to(src)
            except OSError:
                self.skipTest("symlink unavailable on this platform")
            with self.assertRaisesRegex(ValueError, "SYMLINK"):
                _read_regular_local(dest, 8_000_000)

    def test_real_cli_reads_three_files_and_outputs_only_json(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            sources = {}
            for name, content in (
                ("submissions", synthetic_submissions()),
                ("companyfacts", json.dumps(synthetic_companyfacts()).encode("utf-8")),
                ("original", SYNTHETIC_HTML),
            ):
                file = directory / (name + ".dat")
                file.write_bytes(content)
                sources[name] = file
            proc = subprocess.run([
                sys.executable, "-m", "proofinvest.local_sec_packet",
                "--submissions-json", str(sources["submissions"]),
                "--companyfacts-json", str(sources["companyfacts"]),
                "--original-file", str(sources["original"]),
                "--cik", SYNTHETIC_CIK, "--accession", SYNTHETIC_ACCESSION,
                "--as-of", AS_OF, "--collected-at", COLLECTED_AT,
                "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                "--needle", PHRASE,
            ], capture_output=True, text=True, check=False, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["financial"]["growth_pct"], "100.00")
            self.assertTrue(all(v is False for v in report["attestations"].values()))
            self.assertNotIn("<script>", proc.stdout)
            self.assertFalse(proc.stderr)


if __name__ == "__main__":
    unittest.main()
