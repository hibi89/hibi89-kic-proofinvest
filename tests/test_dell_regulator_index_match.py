"""P203 SEC submission index public metadata vs actually observed issuer raw."""
from __future__ import annotations

import unittest
from proofinvest import dell_regulator_index_match as m


class RegulatorIndependentIdentityTests(unittest.TestCase):
    def get(self,**updates):
        params={
            "reviewed_as_of":"2026-11-05",
            "index":m.official_sec_index_reference(),
            "publisher":m.actual_p195_source_receipt(),
            "xbrl":m.observed_ixbrl_receipt(),
        }
        params.update(updates)
        return m.verify_regulator_issuer_filing_index(**params)

    def test_actual_sec_index_public_identity_matches_real_firstparty_raw_xbrl(self):
        r=self.get()
        self.assertEqual(r["status"],"INDEPENDENT_SEC_FILING_INDEX_MATCHED_WITH_LIVE_ISSUER_XBRL")
        self.assertTrue(r["independent_regulator_index_metadata_reconciled"])
        self.assertTrue(r["issuer_xbrl_fiscal_context_matched"])
        self.assertEqual(r["evidence"]["cik"],"0001571996")
        self.assertEqual(r["evidence"]["accession"],"0001571996-26-000008")
        self.assertTrue(r["evidence"]["index_and_publisher_display_sizes_differ"])
        for flag in ("raw_sec_edgar_original_authenticated",
                     "sec_original_bytes_obtained",
                     "commercial_and_model_processing_rights_proven",
                     "licensed_real_stock_ndx_peers","full_abc_engine_ready",
                     "trade_executed"):
            self.assertFalse(r[flag])
        self.assertEqual(r["network_requests"],0)

    def test_forged_accession_cik_filing_date_form_or_size_rejected(self):
        for k,value in (
            ("accession","0001571996-26-000009"),
            ("cik","0000000000"),("form","10-Q"),
            ("fiscal_end","2026-01-31"),("filed","2026-03-17"),
            ("document","unknown.htm"),("document_size_index_bytes",3610307),
        ):
            index=m.official_sec_index_reference()
            index[k]=value
            with self.subTest(field=k):
                self.assertEqual(self.get(index=index)["status"],"BLOCKED")

    def test_forged_publisher_source_or_xbrl_rejected(self):
        for k,value in (
            ("source_original_sha256","0"*64),
            ("source_original_bytes",4000000),
            ("ticker","NVDA"),("source_rights_verified",True),
            ("sec_edgar_identical_original_verified",True),
        ):
            packet=m.actual_p195_source_receipt()
            packet[k]=value
            self.assertEqual(self.get(publisher=packet)["status"],"BLOCKED")
        packet=m.observed_ixbrl_receipt()
        packet["xbrl_concept"]="fake:revenues"
        self.assertEqual(self.get(xbrl=packet)["status"],"BLOCKED")

    def test_source_vintage_before_or_after_review_fails_closed(self):
        for d in ("2026-11-04","2026-11-06","2026-03-15","2030-01-01",None):
            self.assertEqual(self.get(reviewed_as_of=d)["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
