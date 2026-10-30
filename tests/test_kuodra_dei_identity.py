"""P24 DEI self-claim mismatches block local SEC and Guard, never certify origin."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from proofinvest.dei_identity_review import review_embedded_dei_identity
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.kuodra_loose_sec_compatibility import inspect_loose_sec_files
from proofinvest.local_sec_guard_report import review_local_sec_with_guard

CIK = SYNTHETIC_CIK
FACT_CIK = b'<ix:nonNumeric name="dei:EntityCentralIndexKey">1</ix:nonNumeric>'
FACT_TYPE = b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>'


def inspect(raw):
    return review_embedded_dei_identity(raw, cik=CIK)


class DEIOriginalIdentityTests(unittest.TestCase):
    def test_matching_both_dei_claims_remain_self_reported_not_authenticated(self):
        report = inspect(b"<html><ix:hidden>" + FACT_CIK + FACT_TYPE + b"</ix:hidden></html>")
        self.assertEqual(report["status"], "self_claims_consistent_unverified")
        self.assertTrue(report["cik_self_claim_matches_operator"])
        self.assertTrue(report["form_self_claim_matches_operator"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["full_original_to_accession_link_verified"])

    def test_conflicting_cik_or_form_fails_closed(self):
        wrongs = (
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">2</ix:nonNumeric>',
            b'<ix:nonNumeric name="dei:DocumentType">10-Q</ix:nonNumeric>',
        )
        for fact in wrongs:
            with self.subTest(fact=fact):
                r = inspect(b"<html>" + fact + b"</html>")
                self.assertEqual(r["status"], "conflict")
                self.assertEqual(r["reason_code"], "DEI_ISSUER_OR_DOCUMENT_TYPE_MISMATCH")

    def test_absent_or_single_self_claim_not_external_authentication(self):
        self.assertEqual(inspect(b"<html>ordinary filing text</html>")["status"], "unavailable")
        self.assertEqual(inspect(FACT_CIK)["status"], "partial_self_claims_consistent_unverified")
        self.assertEqual(inspect(FACT_TYPE)["status"], "partial_self_claims_consistent_unverified")
        self.assertFalse(inspect(FACT_CIK)["issuer_authenticated"])

    def test_same_value_repeated_allowed_conflicting_duplicate_blocks(self):
        self.assertEqual(inspect(FACT_CIK + FACT_CIK + FACT_TYPE)["status"],
                         "self_claims_consistent_unverified")
        r = inspect(FACT_CIK + b'<ix:nonNumeric name="dei:EntityCentralIndexKey">2</ix:nonNumeric>')
        self.assertEqual(r["status"], "conflict")
        self.assertEqual(r["reason_code"], "DEI_DUPLICATE_CONFLICTING_CLAIMS")

    def test_script_fake_dei_markup_cannot_be_parsed_as_fact(self):
        html = b"<script>" + FACT_CIK + b"</script>"
        self.assertEqual(inspect(html)["status"], "unavailable")

    def test_ambiguous_nesting_and_unclosed_fact_block(self):
        cases = (
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey"><b>1</b></ix:nonNumeric>',
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">1',
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">1&#x31;</ix:nonNumeric>',
            b'<ix:nonNumeric name="dei:DocumentType"/>',
        )
        for original in cases:
            with self.subTest(original=original):
                self.assertEqual(inspect(original)["status"], "ambiguous")

    def test_bounded_bad_utf8_not_a_false_match(self):
        r = inspect(FACT_CIK + b"\xff")
        self.assertEqual(r["status"], "unavailable")
        self.assertFalse(r["issuer_authenticated"])

    def test_read_only_loose_source_preflight_blocks_conflicting_dei(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            f1, f2, f3 = (root/"submissions.json",root/"companyfacts.json",root/"original.html")
            f1.write_bytes(synthetic_submissions())
            f2.write_bytes(json.dumps(synthetic_companyfacts()).encode())
            f3.write_bytes(SYNTHETIC_HTML + b'<ix:nonNumeric name="dei:DocumentType">10-Q</ix:nonNumeric>')
            kwargs = dict(
                submissions_path=f1, companyfacts_path=f2, original_path=f3,
                cik=CIK, accession=SYNTHETIC_ACCESSION, as_of=AS_OF,
                collected_at=COLLECTED_AT,
            )
            result = inspect_loose_sec_files(**kwargs)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_code"], "ORIGINAL_DEI_SELF_CLAIM_CONFLICT_OR_AMBIGUOUS")
            self.assertFalse(result["source_authenticated"])
            self.assertFalse((root/"audit.sqlite").exists())

    def test_guard_does_not_open_sqlite_for_identity_conflict(self):
        with tempfile.TemporaryDirectory() as t:
            db = Path(t)/"audit.sqlite"
            kwargs = dict(
                submissions_json=synthetic_submissions(),
                companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                original_filing=SYNTHETIC_HTML + b'<ix:nonNumeric name="dei:DocumentType">10-Q</ix:nonNumeric>',
                cik=CIK, accession=SYNTHETIC_ACCESSION,
                as_of=AS_OF, collected_at=COLLECTED_AT,
                current_end="2025-09-30", prior_end="2024-09-30",
                needle=PHRASE, run_id="p24-conflict", audit_db_path=db,
            )
            with self.assertRaisesRegex(ValueError, "ORIGINAL_DEI_SELF_CLAIM_CONFLICT_OR_AMBIGUOUS"):
                review_local_sec_with_guard(**kwargs)
            self.assertFalse(db.exists())

    def test_matching_dei_keeps_existing_guard_hold(self):
        with tempfile.TemporaryDirectory() as t:
            out = review_local_sec_with_guard(
                submissions_json=synthetic_submissions(),
                companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                original_filing=SYNTHETIC_HTML + FACT_CIK + FACT_TYPE,
                cik=CIK, accession=SYNTHETIC_ACCESSION,
                as_of=AS_OF, collected_at=COLLECTED_AT,
                current_end="2025-09-30", prior_end="2024-09-30",
                needle=PHRASE, run_id="p24-dei-match",
                audit_db_path=Path(t)/"audit.sqlite",
            )
            self.assertEqual(out["guard"]["decision"], "HOLD")
            self.assertFalse(out["limits"]["external_source_authenticated"])


if __name__ == "__main__":
    unittest.main()
