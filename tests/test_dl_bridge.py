"""KIC reads DL's public JSON interface, but does not import its engine."""
from __future__ import annotations

import copy
import unittest

from proofinvest.dl_bridge import assess_dl_sec_handoff
from proofinvest.sec_companyfacts import run_curated_apple_demo


def sample_index():
    cik = "0000320193"
    acc = "0000320193-25-000079"
    listing = f"https://data.sec.gov/submissions/CIK{cik}.json"
    return {
        "provider": "SEC_EDGAR",
        "issuer_cik": cik,
        "as_of_cutoff": "2025-11-01",
        "collected_at": "2025-11-01T10:30:00Z",
        "source_sha256": "a" * 64,
        "source_uri": listing,
        "provenance": "OFFLINE_UNVERIFIED",
        "filings": [{
            "schema_version": "1.0",
            "provider": "SEC_EDGAR", "issuer_cik": cik,
            "accession": acc, "form": "10-K",
            "filed_at": "2025-10-31",
            "source_uri": (
                "https://www.sec.gov/Archives/edgar/data/320193/"
                "000032019325000079/a10k.htm"
            ),
            "index_source_uri": listing,
            "index_raw_sha256": "a" * 64,
            "raw_sha256": None,
            "evidence_status": "OFFLINE_SOURCE_UNVERIFIED",
        }],
    }


class DlBridgeTests(unittest.TestCase):
    def setUp(self):
        self.index = sample_index()
        self.verdict = run_curated_apple_demo(as_of="2025-11-01")

    def test_matches_offline_provenance_without_authenticity_upgrade(self):
        original = copy.deepcopy((self.index, self.verdict))
        out = assess_dl_sec_handoff(self.index, self.verdict)
        self.assertEqual(out["status"], "linked_metadata_only")
        self.assertTrue(out["trace_linked"])
        self.assertEqual(out["numeric_verdict_state"], "calculated_unverified")
        self.assertFalse(out["authenticated_external_source"])
        self.assertFalse(out["original_filing_downloaded"])
        self.assertFalse(out["live_api_called"])
        self.assertEqual(original, (self.index, self.verdict))

    def test_mismatched_numeric_cik_or_accession_fails_closed(self):
        for change in ({"cik": "0000000001"},
                       {"accession": "0000320193-25-000080"},
                       {"as_of": "2025-11-02"}):
            with self.subTest(change=change):
                out = assess_dl_sec_handoff(self.index, {**self.verdict, **change})
                self.assertEqual(out["status"], "unavailable")
                self.assertFalse(out["trace_linked"])

    def test_collection_after_asof_is_not_contemporaneous_proof(self):
        self.index["collected_at"] = "2025-11-01T23:30:00-12:00"
        out = assess_dl_sec_handoff(self.index, self.verdict)
        self.assertEqual(out["reason_code"], "DL_COLLECTION_AFTER_AS_OF")

    def test_wrong_source_url_or_hash_scope_fails_closed(self):
        for mutate in ("bad_uri", "bad_digest", "raw_html_digest"):
            with self.subTest(mutate=mutate):
                index = sample_index()
                if mutate == "bad_uri":
                    index["filings"][0]["source_uri"] = "https://evil.example/a10k.htm"
                elif mutate == "bad_digest":
                    index["filings"][0]["index_raw_sha256"] = "b" * 64
                else:
                    index["filings"][0]["raw_sha256"] = "0" * 64
                self.assertEqual(assess_dl_sec_handoff(index, self.verdict)["status"],
                                 "unavailable")

    def test_fake_numeric_authenticated_flag_never_accepted(self):
        poisoned = {**self.verdict, "authenticated_external_source": True}
        self.assertEqual(assess_dl_sec_handoff(self.index, poisoned)["reason_code"],
                         "UNTRUSTED_NUMERIC_VERDICT")


if __name__ == "__main__":
    unittest.main()
