"""P20: real loose local input intake without forged SEC capture receipts."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_submissions, synthetic_companyfacts,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_loose_sec_compatibility import inspect_loose_sec_files, main
from proofinvest.sec_companyfacts import TAG


class LooseSourceTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(prefix="kuodra-p20-")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.paths = [self.root/"submissions.json",
                      self.root/"companyfacts.json", self.root/"original.html"]
        self.paths[0].write_bytes(synthetic_submissions())
        self.paths[1].write_text(json.dumps(synthetic_companyfacts()),encoding="utf-8")
        self.paths[2].write_bytes(SYNTHETIC_HTML)
        self.kw = {
            "submissions_path": self.paths[0],
            "companyfacts_path": self.paths[1],
            "original_path": self.paths[2],
            "cik": SYNTHETIC_CIK,
            "accession": SYNTHETIC_ACCESSION,
            "as_of": AS_OF,
            "collected_at": COLLECTED_AT,
        }

    def inspect(self, **changes):
        return inspect_loose_sec_files(**(self.kw | changes))

    def test_three_loose_files_no_network_writes_or_html_disclosure(self):
        old = [path.read_bytes() for path in self.paths]
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as net:
            result = self.inspect()
        net.assert_not_called()
        self.assertEqual(result["status"], "operator_review_required")
        self.assertEqual(result["period_candidates"][0]["revenue_concept"], TAG)
        self.assertEqual(result["period_candidates"][0]["growth_pct_unverified"],
                         "100.00")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["original_filing_belongs_to_accession_verified"])
        self.assertFalse(result["audit_written"])
        self.assertFalse(result["model_called"])
        self.assertTrue(result["original_strict_utf8"])
        self.assertGreaterEqual(result["eligible_original_text_candidate_count"], 1)
        self.assertEqual([path.read_bytes() for path in self.paths], old)
        self.assertEqual(sorted(self.root.iterdir()), sorted(self.paths))
        self.assertNotIn(PHRASE,json.dumps(result))

    def test_strict_xhtml_is_optional_not_blocking(self):
        result = self.inspect()
        self.assertEqual(result["status"],"operator_review_required")
        self.assertEqual(result["period_candidates"][0]["optional_ixbrl_status"],
                         "unavailable")

    def test_revenue_concept_fallback_without_faking_primary(self):
        facts = synthetic_companyfacts()
        gaap = facts["facts"]["us-gaap"]
        gaap["SalesRevenueNet"] = gaap.pop(TAG)
        self.paths[1].write_text(json.dumps(facts),encoding="utf-8")
        result = self.inspect()
        self.assertEqual(result["period_candidates"][0]["revenue_concept"],
                         "SalesRevenueNet")

    def test_other_issuer_mismatch_blocks_before_result(self):
        self.assertEqual(self.inspect(cik="0000000002")["status"],"blocked")
        changed = synthetic_companyfacts()
        changed["cik"] = 2
        self.paths[1].write_text(json.dumps(changed),encoding="utf-8")
        self.assertEqual(self.inspect()["status"],"blocked")

    def test_same_accession_different_filing_date_blocks(self):
        facts = synthetic_companyfacts()
        rows = facts["facts"]["us-gaap"][TAG]["units"]["USD"]
        for row in rows:
            row["filed"] = "2025-10-16"
        self.paths[1].write_text(json.dumps(facts),encoding="utf-8")
        self.assertEqual(self.inspect()["reason_code"],
                         "FILING_DATE_COMPANYFACTS_SUBMISSIONS_MISMATCH")

    def test_operator_claimed_collection_after_cutoff_blocked(self):
        report = self.inspect(collected_at="2025-10-17T00:00:00Z")
        self.assertEqual(report["status"],"blocked")
        self.assertEqual(report["reason_code"],
                         "SUBMISSIONS_OR_COMPANYFACTS_FORMAT_INVALID")
        self.assertFalse(report["source_authenticated"])

    def test_missing_or_overwritten_original_is_rejected(self):
        self.paths[2].unlink()
        self.assertEqual(self.inspect()["status"],"blocked")
        self.paths[2].write_bytes(b"")
        self.assertEqual(self.inspect()["status"],"blocked")

    def test_symlink_source_is_rejected(self):
        self.paths[2].unlink()
        try:
            self.paths[2].symlink_to(self.paths[1])
        except (OSError, NotImplementedError):
            self.skipTest("Local platform does not permit symlink")
        self.assertEqual(self.inspect()["status"],"blocked")

    def test_same_path_for_two_sources_rejected(self):
        result = self.inspect(original_path=self.paths[1])
        self.assertEqual(result["reason_code"],"SOURCE_INPUT_PATH_COLLISION")

    def test_invalid_identity_and_nonexistent_target_fail_closed(self):
        self.assertEqual(self.inspect(accession="0000000001-25-000099")["reason_code"],
                         "TARGET_10K_NOT_IN_SAVED_RECENT_SUBMISSIONS")
        self.assertEqual(self.inspect(as_of="not-a-date")["status"],"blocked")
        self.assertEqual(self.inspect(cik="0000000000")["status"],"blocked")

    def test_non_utf8_original_keeps_structural_pair_but_blocks_quote(self):
        self.paths[2].write_bytes(b"<html><p>\xff</p></html>")
        result = self.inspect()
        self.assertEqual(result["status"],"blocked")
        self.assertEqual(result["reason_code"],
                         "ORIGINAL_NOT_STRICT_UTF8_FOR_TEXT_EVIDENCE")
        self.assertEqual(len(result["period_candidates"]),1)
        self.assertEqual(result["eligible_original_text_candidate_count"],0)

    def test_cli_read_only_and_failure_exit_codes(self):
        cli=["--submissions",str(self.paths[0]),
             "--companyfacts",str(self.paths[1]),
             "--original",str(self.paths[2]),"--cik",SYNTHETIC_CIK,
             "--accession",SYNTHETIC_ACCESSION,"--as-of",AS_OF,
             "--collected-at",COLLECTED_AT]
        out=io.StringIO()
        with redirect_stdout(out):
            code=main(cli)
        self.assertEqual(code,0)
        self.assertNotIn(PHRASE,out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"],
                         "operator_review_required")
        self.paths[2].unlink()
        out=io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(cli),2)
        self.assertEqual(json.loads(out.getvalue())["status"],"blocked")

    def test_duplicate_json_key_and_bad_unicode_facts_block(self):
        self.paths[1].write_bytes(b'{"cik":1,"cik":1,"facts":{}}')
        self.assertEqual(self.inspect()["status"],"blocked")
        self.paths[1].write_bytes(b"\xff{")
        self.assertEqual(self.inspect()["status"],"blocked")


if __name__ == "__main__":
    unittest.main()
