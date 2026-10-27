"""KIC-only strict join of a DL archive span and SEC numeric metadata."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from disclosure_lightning.core import index_submissions, save_index
from disclosure_lightning.originals import locate_original, persist_original
from proofinvest.dl_bridge import assess_dl_original_handoff, assess_dl_sec_handoff
from proofinvest.dl_source_span import anchored_source_span
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML, replay_original
from proofinvest.sec_companyfacts import verify_sec_annual_revenue


class KicDlOriginalCrosslinkTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kic-crosslink-")
        self.addCleanup(tmp.cleanup)
        db = Path(tmp.name) / "source.sqlite"
        raw = synthetic_submissions()
        index = index_submissions(
            raw, cik=SYNTHETIC_CIK, as_of=AS_OF,
            forms=frozenset({"10-K", "10-K/A"}), collected_at=COLLECTED_AT,
        )
        save_index(db, raw, index)
        receipt = locate_original(
            db, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        )
        saved = persist_original(
            db_path=db, receipt=receipt, raw=SYNTHETIC_HTML,
            kind="application/octet-stream", origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.span = anchored_source_span(
            db_path=db, cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
            sha256=saved["filing_sha256"], needle=PHRASE,
        )
        numeric = verify_sec_annual_revenue(
            synthetic_companyfacts(), cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION,
            current_end="2025-09-30", prior_end="2024-09-30", as_of=AS_OF,
        )
        self.link = assess_dl_sec_handoff(index, numeric)

    def test_actual_archive_and_numeric_handoff_can_crosslink_without_upgrade(self):
        original = copy.deepcopy((self.link, self.span))
        result = assess_dl_original_handoff(self.link, self.span)
        self.assertEqual(result["status"], "linked_untrusted_original_span_for_review")
        self.assertTrue(result["span_metadata_linked"])
        self.assertEqual(result["source_uri"], self.span["source_uri"])
        self.assertEqual(result["original_filing_sha256"], self.span["filing_sha256"])
        for key in ("authenticated_external_source", "numeric_facts_authenticated",
                    "archived_bytes_rechecked", "live_api_called", "official_contest_submission"):
            self.assertFalse(result[key], key)
        self.assertEqual(original, (self.link, self.span))

    def test_wrong_cik_accession_or_filing_url_rejected(self):
        for field, val in (("issuer_cik", "0000000009"),
                           ("accession", "0000000001-25-999999"),
                           ("source_uri", "https://evil.example/x")):
            with self.subTest(field=field):
                span = dict(self.span, **{field: val})
                res = assess_dl_original_handoff(self.link, span)
                self.assertEqual(res["reason_code"], "ORIGINAL_FILING_IDENTITY_MISMATCH")
                self.assertFalse(res["span_metadata_linked"])

    def test_untrusted_flags_cannot_upgrade_truth(self):
        for field, val in (("authenticated_external_source", True),
                           ("numerical_claim_verified", True),
                           ("live_api_called", True)):
            with self.subTest(field=field):
                self.assertEqual(
                    assess_dl_original_handoff(self.link, dict(self.span, **{field: val}))["status"],
                    "unavailable",
                )
        self.assertEqual(
            assess_dl_original_handoff(dict(self.link, trace_linked=False), self.span)["status"],
            "unavailable",
        )

    def test_bad_digest_bounds_or_boolean_offset_rejected(self):
        for field, value in (("filing_sha256", "0" * 63),
                             ("start_byte", -1),
                             ("end_byte_exclusive", True),
                             ("end_byte_exclusive", 10**8),
                             ("original_bytes_size", 0),
                             ("literal_ascii_phrase", "DIFFERENT")):
            with self.subTest(field=field):
                result = assess_dl_original_handoff(self.link, dict(self.span, **{field: value}))
                self.assertEqual(result["reason_code"], "INVALID_ORIGINAL_SPAN_METADATA")

    def test_forged_html_context_is_never_echoed(self):
        result = assess_dl_original_handoff(
            self.link, dict(self.span, context_escaped_html="<script>unsafe</script>"),
        )
        self.assertEqual(result["status"], "linked_untrusted_original_span_for_review")
        self.assertNotIn("context_escaped_html", result)
        self.assertNotIn("unsafe", str(result))

    def test_demo_exposes_real_synthetic_crosslink_result(self):
        receipt = replay_original()
        self.assertEqual(receipt["kic_original_crosslink"],
                         "linked_untrusted_original_span_for_review")
        self.assertTrue(receipt["original_span_metadata_linked"])
        self.assertFalse(receipt["numeric_facts_authenticated"])


if __name__ == "__main__":
    unittest.main()
