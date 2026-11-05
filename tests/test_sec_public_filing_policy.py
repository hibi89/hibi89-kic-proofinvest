"""P236 official SEC public EDGAR policy not source-byte/license confusion."""
from __future__ import annotations
import unittest
from unittest.mock import patch

from proofinvest import sec_public_filing_policy as p


def verify(**updates):
    args = dict(
        filing_reference=p._SOURCE,issuer="AAPL",
        accession="0000320193-26-000026",as_of="2026-11-05",
        intended_use="LOCAL_FINANCIAL_RESEARCH",
    )
    args.update(updates)
    return p.verify_official_public_edgar_reuse_policy(**args)


class SecOfficialPublicReusePolicyTests(unittest.TestCase):
    def test_two_official_sec_sources_narrow_general_reuse(self):
        x=verify()
        self.assertEqual(x["status"],
                         "OFFICIAL_PUBLIC_EDGAR_GENERAL_REUSE_POLICY_VERIFIED")
        self.assertTrue(x["official_general_public_edgar_filing_reuse_policy_verified"])
        self.assertTrue(x["official_general_public_edgar_copying_policy_verified"])
        self.assertTrue(x["reference_is_manually_reviewed_public_filing"])
        self.assertEqual(x["evidence_owner"],
                         "US_SECURITIES_AND_EXCHANGE_COMMISSION")
        self.assertEqual(x["official_policy_evidence_urls"],[
            "https://www.sec.gov/files/about/webmaster-faq.htm",
            "https://www.sec.gov/about/privacy-information",
        ])
        self.assertEqual(x["policy_reviewed_kst"],"2026-11-05")
        self.assertEqual(x["guard_policy_preview"],"HOLD")
        self.assertEqual(x["automated_sec_gets_performed"],0)
        self.assertEqual(x["external_network_requests"],0)
        self.assertFalse(x["trade_executed"])
        for k in (
            "exact_sec_edgar_original_bytes_authenticated",
            "sec_accession_origin_authenticated",
            "individual_source_document_use_rights_verified",
            "non_edgar_exhibits_or_artwork_cleared",
            "sec_logo_or_trademark_permission",
            "financial_market_data_rights_verified",
            "nasdaq100_ndx_data_rights_verified",
            "peer_data_rights_verified",
            "financial_ai_processing_rights_verified",
            "vendor_contract_or_client_entitlement_verified",
            "sec_api_transport_reauthorized",
            "public_production_authorized",
        ):
            self.assertFalse(x[k],k)

    def test_separately_licensed_third_party_ai_and_trademarks_not_allowed(self):
        for purpose in (
            "NDX_LICENSE", "SEC_LOGO", "AI_TRAINING", "AUTO_SEC_GET",
            "COMMERCIAL_NDX_RESOLD", None, True, "", 2026,
        ):
            with self.subTest(intent=purpose):
                x=verify(intended_use=purpose)
                self.assertEqual(x["status"],"BLOCKED")
                self.assertFalse(
                    x["official_general_public_edgar_filing_reuse_policy_verified"])

    def test_exact_public_reference_replay_rejects_forged_domains(self):
        for field,value in (
            ("filing_reference","https://www.sec.gov.evil.example/a.htm"),
            ("filing_reference","https://www.sec.gov/Archives/edgar/data/320193/fake.htm"),
            ("filing_reference","http://www.sec.gov/Archives/edgar/data/320193/000032019326000026/aapl-20260926.htm"),
            ("filing_reference",None),
            ("issuer","NVDA"),("issuer","aapl"),
            ("accession","0000320193-25-000079"),
            ("as_of","2026-11-06"),
            ("as_of",True),
        ):
            with self.subTest(field=field,value=value):
                x=verify(**{field:value})
                self.assertEqual(x["status"],"BLOCKED")
                self.assertFalse(x["sec_accession_origin_authenticated"])
                self.assertEqual(x["external_network_requests"],0)

    def test_underlying_manual_document_must_stay_unverified(self):
        with patch.object(p,"review_apple_2026_public_financials",
                          return_value={
                              "status":"PUBLIC_FINANCIAL_VALUES_DECIMAL_RECALCULATED_ORIGINAL_UNVERIFIED",
                              "public_filing_url":p._SOURCE,
                              "original_bytes_authenticated":True,
                              "source_rights_verified":False,
                              "guard_policy_preview":"HOLD",
                              "trade_executed":False,
                          }):
            x=verify()
        self.assertEqual(x["status"],"BLOCKED")
        self.assertFalse(
            x["official_general_public_edgar_filing_reuse_policy_verified"])

    def test_independent_public_reuse_no_raw_sec_http(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("SEC_HTTP_FORBIDDEN")) as h:
            x=verify(intended_use="PUBLIC_EDGAR_FACTS_IN_HUMAN_REPORT")
        h.assert_not_called()
        self.assertEqual(x["status"],
                         "OFFICIAL_PUBLIC_EDGAR_GENERAL_REUSE_POLICY_VERIFIED")
        self.assertFalse(x["financial_ai_processing_rights_verified"])
