"""P65: opt-in Apple original HTML 24-cell guard in full offline preflight.

Constructed HTML exercises the real parser, but is NOT authenticated Apple
or SEC original bytes. Never use fake issuer data to assert real provenance.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.real_data_preflight import (
    _apple_2025_original_table_gate, inspect_offline_data_files,
)
from tests.test_apple_local_html_crosscheck import sample_html
from tests.test_real_data_preflight import create_files, args


_APPLE = dict(
    cik="0000320193",
    accession="0000320193-25-000079",
    as_of="2025-10-31",
    current_end="2025-09-27",
    prior_end="2024-09-28",
)


class AppleFullPreflightGateTests(unittest.TestCase):
    def test_same_raw_bytes_pass_24_statement_cells_without_trust_upgrade(self):
        raw = sample_html()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
            receipt = _apple_2025_original_table_gate(raw, **_APPLE)
        network.assert_not_called()
        self.assertEqual(receipt["status"], "24_LOCAL_VALUES_MATCH_ORIGIN_UNVERIFIED")
        self.assertEqual(receipt["matched_numeric_cells"], 24)
        self.assertEqual(receipt["original_local_html_sha256"], sha256(raw).hexdigest())
        self.assertFalse(receipt["source_authenticated"])
        self.assertFalse(receipt["data_rights_verified"])
        self.assertFalse(receipt["original_bytes_retained"])

    def test_numeric_mutation_fails_even_with_right_issuer_and_dates(self):
        raw = sample_html().replace(b"416,161", b"416,162", 1)
        with self.assertRaisesRegex(ValueError,
                                    "LOCAL_HTML_OPERATIONS_ORIGINAL_VS_MANUAL_CONFLICT"):
            _apple_2025_original_table_gate(raw, **_APPLE)

    def test_wrong_issuer_accession_or_period_blocks(self):
        for field, value in (
            ("cik", "0000000001"),
            ("accession", "0000320193-24-000001"),
            ("as_of", "2025-11-01"),
            ("current_end", "2025-09-28"),
            ("prior_end", "2024-09-29"),
        ):
            with self.subTest(field=field):
                identity = dict(_APPLE)
                identity[field] = value
                with self.assertRaisesRegex(ValueError,
                                            "APPLE_ORIGINAL_TARGET_MISMATCH"):
                    _apple_2025_original_table_gate(sample_html(), **identity)

    def test_forged_parser_authentication_claim_is_refused(self):
        raw = sample_html()
        with patch(
            "proofinvest.apple_local_html_crosscheck.verify_local_apple_10k_html",
            return_value={
                "status": "LOCAL_ORIGINAL_HTML_BYTES_MATCH_MANUAL_FINANCIAL_ROWS_ORIGIN_UNVERIFIED",
                "matched_numeric_cells": 24,
                "statements_matched": ["operations", "balance", "cash"],
                "original_local_html_sha256": sha256(raw).hexdigest(),
                "original_bytes_retained": False,
                "sec_original_file_authenticated": True,
                "full_sec_guard_a_b_c_real_data_verified": False,
            },
        ):
            with self.assertRaisesRegex(
                ValueError, "APPLE_ORIGINAL_TABLE_TRUST_OR_VALUES_INVALID"
            ):
                _apple_2025_original_table_gate(raw, **_APPLE)

    def test_opt_in_blocks_non_apple_triplet_but_default_untouched(self):
        with TemporaryDirectory() as directory:
            archive, market, industry, _ = create_files(Path(directory))
            unmodified = inspect_offline_data_files(**args(archive, market, industry))
            self.assertEqual(unmodified["status"],
                             "local_structure_pass_origin_unverified")
            self.assertIsNone(unmodified["apple_10k_original_table_check"])
            denied = inspect_offline_data_files(
                **args(archive, market, industry),
                apple_10k_24_cell_check=True,
            )
            self.assertEqual(denied["status"], "blocked")
            self.assertEqual(denied["reason_code"], "APPLE_10K_24_CELL_CHECK_BLOCKED")
            self.assertFalse(denied["source_authenticated"])
            self.assertFalse(denied["audit_retained"])
            self.assertFalse(denied["three_engine_real_world_validated"])

    def test_option_must_be_boolean(self):
        result = inspect_offline_data_files(
            prior_end="2024-09-28", current_end="2025-09-27",
            needle="APPLE_RECEIPT", apple_10k_24_cell_check="true",
        )
        self.assertEqual(result["reason_code"], "INVALID_APPLE_CHECK_OPTION")

    def test_cli_opt_in_refuses_wrong_issuer_without_disclosing_paths(self):
        with TemporaryDirectory() as directory:
            archive, _, _, _ = create_files(Path(directory))
            cmd = [
                sys.executable, "-m", "proofinvest.real_data_preflight",
                "--sec-bundle", str(archive),
                "--prior-end", "2024-09-30",
                "--current-end", "2025-09-30",
                "--needle", "Revenue from continuing operations",
                "--apple-10k-24-cell-check",
            ]
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            output = json.loads(proc.stdout)
            self.assertEqual(output["reason_code"], "APPLE_10K_24_CELL_CHECK_BLOCKED")
            self.assertNotIn(str(archive), proc.stdout)
            self.assertFalse(output["source_authenticated"])


if __name__ == "__main__":
    unittest.main()
