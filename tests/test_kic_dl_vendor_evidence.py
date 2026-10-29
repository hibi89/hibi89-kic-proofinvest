"""Real offline vendor DL archive -> ProofInvest Guard bridge tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.dl_vendor import core, originals
from proofinvest.dl_vendor_evidence import review_saved_dl_evidence

CIK = "0000320193"
ACCESSION = "0000320193-25-000079"
DAY = "2025-11-01"
FIXTURE = (Path(__file__).resolve().parents[1] /
           "integrations/dl_vendor/fixtures/kic_apple_handoff_synthetic.json")


class KicVendorDlGuardIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "dl.sqlite3"
        raw = FIXTURE.read_bytes()
        index = core.index_submissions(
            raw, cik=CIK, as_of=DAY, forms=core.parse_forms("10-K"),
            provenance="OFFLINE_UNVERIFIED",
            collected_at="2025-11-01T10:30:00Z",
        )
        core.save_index(self.db, raw, index)
        location = originals.locate_original(
            self.db, cik=CIK, accession=ACCESSION,
        )
        with patch("integrations.dl_vendor.originals._timestamp",
                   return_value="2025-11-01T10:32:00Z"):
            saved = originals.persist_original(
                db_path=self.db, receipt=location,
                raw=(b"<html><p>Revenue 100</p>"
                     b"<script>do not show</script></html>"),
                kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
            )
        self.sha = saved["filing_sha256"]

    def query(self, **updates):
        args = dict(db_path=self.db, cik=CIK, accession=ACCESSION,
                    sha256=self.sha, as_of=DAY, term="Revenue")
        args.update(updates)
        return review_saved_dl_evidence(**args)

    def test_offline_original_to_dl_text_to_guard_hold(self):
        result = self.query()
        self.assertEqual(result["status"], "candidates_for_human_review")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertFalse(result["financial_claim_verified"])
        self.assertFalse(result["external_source_authenticated"])
        self.assertFalse(result["trade_executed"])
        self.assertFalse(result["live_api_called"])
        self.assertEqual(result["as_of"], DAY)
        self.assertIn("Revenue", result["candidates"][0]["text"])
        self.assertNotIn("do not show", str(result["candidates"]))

    def test_unmatched_text_cannot_authorize(self):
        result = self.query(term="Missing term")
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["status"], "no_matching_evidence")
        self.assertEqual(result["guard"]["decision"], "HOLD")

    def test_reject_wrong_digest_and_future_cutoff(self):
        with self.assertRaises(ValueError):
            self.query(sha256="f" * 64)
        with self.assertRaises(ValueError):
            self.query(as_of="2025-10-30")

    def test_reject_malformed_identity_and_unbounded_search(self):
        for bad in ({"cik": "0000320194"}, {"accession": "bad"},
                    {"sha256": "X" * 64}, {"term": "\x00Revenue"},
                    {"max_results": 100}, {"max_results": True},
                    {"as_of": "2025-02-30"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.query(**bad)

    def test_read_only_no_new_db_for_missing_path(self):
        absent = self.db.with_name("missing.sqlite3")
        with self.assertRaises(ValueError):
            self.query(db_path=absent)
        self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
