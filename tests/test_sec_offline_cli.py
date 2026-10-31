"""Local SEC CompanyFacts CLI input, safety, and offline output tests."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from proofinvest import sec_offline_cli

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
BASE = [
    "--cik", "0000320193",
    "--accession", "0000320193-25-000079",
    "--current-end", "2025-09-27",
    "--prior-end", "2024-09-28",
    "--as-of", "2025-11-01",
]


def run_cli(path: Path, args=None):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        exitcode = sec_offline_cli.main([str(path), *(BASE if args is None else args)])
    return exitcode, json.loads(capture.getvalue())


class SecOfflineCliTests(unittest.TestCase):
    def test_local_json_revenue_result(self):
        code, out = run_cli(FIXTURE)
        self.assertEqual(code, 0)
        self.assertEqual(out["growth_pct"], "6.43")
        self.assertEqual(out["status"], "calculated_unverified")
        self.assertFalse(out["live_api_called"])

    def test_pre_filing_date_returns_unavailable(self):
        args = list(BASE)
        args[-1] = "2025-10-30"
        code, out = run_cli(FIXTURE, args)
        self.assertEqual(code, 2)
        self.assertEqual(out["reason_code"], "FILING_AFTER_AS_OF")

    def test_missing_json_fails_without_disclosing_path(self):
        with tempfile.TemporaryDirectory() as folder:
            secret = Path(folder) / "not_found.json"
            code, out = run_cli(secret)
            self.assertEqual(code, 2)
            self.assertEqual(out["reason_code"], "LOCAL_INPUT_REJECTED")
            self.assertNotIn(str(secret), json.dumps(out))

    def test_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.json"
            path.write_text("{invalid", encoding="utf-8")
            code, out = run_cli(path)
            self.assertEqual(code, 2)
            self.assertEqual(out["reason_code"], "LOCAL_INPUT_REJECTED")

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            link = Path(folder) / "link.json"
            try:
                link.symlink_to(FIXTURE)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unavailable")
            self.assertEqual(run_cli(link)[0], 2)

    def test_rejects_large_sparse_input_without_reading_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "huge.json"
            with path.open("wb") as f:
                f.truncate(sec_offline_cli.MAX_INPUT_BYTES + 1)
            self.assertEqual(run_cli(path)[1]["reason_code"], "LOCAL_INPUT_REJECTED")

    def test_unlisted_submitter_accession_has_no_matching_issuer_facts(self):
        # EDGAR accession prefix identifies the submitting account and may
        # legitimately differ from the issuer CIK. This arbitrary accession
        # is rejected because the issuer's CompanyFacts has no matching
        # filing rows, not because the prefix is different.
        args = list(BASE)
        args[3] = "9999999999-25-000079"
        code, out = run_cli(FIXTURE, args)
        self.assertEqual(code, 2)
        self.assertEqual(out["reason_code"], "ANNUAL_FACTS_UNAVAILABLE")
        self.assertFalse(out["authenticated_external_source"])

    def test_rejects_extremely_large_cik_string_in_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "companyfacts.json"
            data = json.loads(FIXTURE.read_text(encoding="utf8"))
            data["cik"] = "1" * 9000
            path.write_text(json.dumps(data), encoding="utf8")
            code, out = run_cli(path)
            self.assertEqual(code, 2)
            self.assertEqual(out["reason_code"], "CIK_MISMATCH")


if __name__ == "__main__":
    unittest.main()
