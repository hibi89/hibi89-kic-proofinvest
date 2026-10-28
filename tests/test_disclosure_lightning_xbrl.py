"""Synthetic Inline XBRL candidate extraction; never proof of SEC facts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from disclosure_lightning import core, originals, xbrl


CIK = "0000320193"
ACCESSION = "0000320193-25-000901"
AS_OF = "2099-12-31"
FIXTURE = (Path(__file__).resolve().parents[1]
           / "disclosure_lightning/fixtures/sec_submissions_synthetic.json")
INLINE = b'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:xbrli="http://www.xbrl.org/2003/instance">
<head><ix:header><xbrli:context id="ctx-2025">
<xbrli:entity><xbrli:identifier scheme="urn:synthetic">320193</xbrli:identifier></xbrli:entity>
<xbrli:period><xbrli:startDate>2024-09-29</xbrli:startDate>
<xbrli:endDate>2025-09-27</xbrli:endDate></xbrli:period>
<xbrli:scenario><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">synthetic:All</xbrldi:explicitMember></xbrli:scenario>
</xbrli:context><xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
</ix:header></head><body>
<ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
 contextRef="ctx-2025" unitRef="usd" scale="6" sign="-" decimals="-3">123&#52;56</ix:nonFraction>
<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="missing-context">Synthetic Corp</ix:nonNumeric>
<ix:nonFraction name="us-gaap:Assets" contextRef="ctx-2025" continuedAt="fact-cont">42</ix:nonFraction>
</body></html>'''


class InlineXbrlEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="dl-xbrl-test-")
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "ledger.sqlite3"
        raw_index = FIXTURE.read_bytes()
        indexed = core.index_submissions(
            raw_index, cik=CIK, as_of=AS_OF, forms=core.parse_forms("10-K"),
            provenance="OFFLINE_UNVERIFIED", collected_at="2026-10-28T00:00:00Z",
        )
        core.save_index(self.db, raw_index, indexed)
        self.receipt = originals.locate_original(
            self.db, cik=CIK, accession=ACCESSION,
        )

    def test_inline_values_keep_raw_context_unit_period_and_untrusted_flags(self):
        saved = originals.persist_original(
            db_path=self.db, receipt=self.receipt, raw=INLINE,
            kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
        )
        result = xbrl.from_saved_original(
            db_path=self.db, cik=CIK, accession=ACCESSION,
            sha256=saved["filing_sha256"], as_of=AS_OF,
        )
        self.assertEqual(result["schema"], "disclosure-lightning.inline-xbrl-candidates.v1")
        self.assertEqual(result["as_of"], AS_OF)
        self.assertEqual(result["candidate_count"], 3)
        self.assertFalse(result["normalization_performed"])
        self.assertFalse(result["financial_claim_verified"])
        self.assertFalse(result["source_authenticity_verified"])

        revenue, name, continued = result["facts"]
        self.assertEqual(revenue["name"],
                         "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax")
        self.assertEqual(revenue["lexical_value"], "123456")
        self.assertEqual(revenue["scale"], "6")
        self.assertEqual(revenue["sign"], "-")
        self.assertEqual(revenue["context_ref_status"], "RESOLVED_UNVERIFIED")
        self.assertEqual(revenue["context_period_fields"], {
            "startdate": "2024-09-29", "enddate": "2025-09-27",
        })
        self.assertEqual(revenue["unit_ref_status"], "RESOLVED_UNVERIFIED")
        self.assertEqual(revenue["unit_source"]["children"][0]["text"], "iso4217:USD")
        self.assertFalse(revenue["source_locator"]["exact_raw_byte_range_verified"])
        self.assertEqual(name["context_ref_status"], "UNKNOWN_OR_AMBIGUOUS")
        self.assertEqual(name["unit_ref_status"], "NOT_APPLICABLE")
        self.assertFalse(name["financial_claim_verified"])
        self.assertEqual(continued["continued_at"], "fact-cont")
        self.assertFalse(continued["continued_text_complete"])

    def test_duplicate_context_reference_is_ambiguous(self):
        duplicated = INLINE.replace(
            b"</xbrli:context>",
            b"</xbrli:context><xbrli:context id=\"ctx-2025\"><xbrli:period>"
            b"<xbrli:instant>2025-09-27</xbrli:instant></xbrli:period></xbrli:context>",
            1,
        )
        result = xbrl.extract_inline_facts(
            duplicated, content_type="text/html",
            filing_sha256=hashlib.sha256(duplicated).hexdigest(),
            issuer_cik=CIK, accession=ACCESSION, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual(result["facts"][0]["context_ref_status"], "UNKNOWN_OR_AMBIGUOUS")
        self.assertIsNone(result["facts"][0]["context_period_fields"])

    def test_namespace_prefixes_are_resolved_by_uri(self):
        aliased = (INLINE.replace(b"xmlns:ix=", b"xmlns:inline=")
                   .replace(b"xmlns:xbrli=", b"xmlns:instance=")
                   .replace(b"ix:", b"inline:")
                   .replace(b"xbrli:", b"instance:"))
        result = xbrl.extract_inline_facts(
            aliased, content_type="text/html",
            filing_sha256=hashlib.sha256(aliased).hexdigest(),
            issuer_cik=CIK, accession=ACCESSION, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertEqual(result["candidate_count"], 3)
        self.assertEqual(result["facts"][0]["context_ref_status"], "RESOLVED_UNVERIFIED")
        self.assertEqual(result["facts"][0]["unit_ref_status"], "RESOLVED_UNVERIFIED")

    def test_incomplete_fact_is_reported_as_truncated_not_complete(self):
        partial = (b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">'
                   b'<body><ix:nonFraction name="us-gaap:Assets" contextRef="c1">123')
        result = xbrl.extract_inline_facts(
            partial, content_type="text/html",
            filing_sha256=hashlib.sha256(partial).hexdigest(),
            issuer_cik=CIK, accession=ACCESSION, source_uri=self.receipt["source_uri"],
            input_origin="OFFLINE_FILE_UNVERIFIED",
        )
        self.assertTrue(result["truncated"])
        self.assertFalse(result["complete_candidate_extraction"])
        self.assertEqual(result["candidate_count"], 0)

    def test_read_only_cli_returns_saved_xbrl_candidates(self):
        saved = originals.persist_original(
            db_path=self.db, receipt=self.receipt, raw=INLINE,
            kind="text/html", origin="OFFLINE_FILE_UNVERIFIED",
        )
        repo = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "disclosure_lightning.xbrl",
             "--db", str(self.db), "--cik", CIK, "--accession", ACCESSION,
             "--sha256", saved["filing_sha256"], "--as-of", AS_OF],
            cwd=repo, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        self.assertEqual(output["filing_sha256"], saved["filing_sha256"])
        self.assertEqual(output["candidate_count"], 3)
        self.assertFalse(output["financial_claim_verified"])
        self.assertFalse(output["normalization_performed"])

    def test_rejects_non_html_or_wrong_digest(self):
        with self.assertRaisesRegex(ValueError, "CONTENT_TYPE"):
            xbrl.extract_inline_facts(
                INLINE, content_type="application/pdf",
                filing_sha256=hashlib.sha256(INLINE).hexdigest(),
                issuer_cik=CIK, accession=ACCESSION, source_uri=self.receipt["source_uri"],
                input_origin="OFFLINE_FILE_UNVERIFIED",
            )
        with self.assertRaisesRegex(ValueError, "INTEGRITY"):
            xbrl.extract_inline_facts(
                INLINE, content_type="text/html", filing_sha256="0" * 64,
                issuer_cik=CIK, accession=ACCESSION, source_uri=self.receipt["source_uri"],
                input_origin="OFFLINE_FILE_UNVERIFIED",
            )
        with self.assertRaisesRegex(ValueError, "RECEIPT_NOT_FOUND"):
            xbrl.from_saved_original(
                db_path=self.db, cik=CIK, accession=ACCESSION,
                sha256="0" * 64, as_of=AS_OF,
            )


if __name__ == "__main__":
    unittest.main()
