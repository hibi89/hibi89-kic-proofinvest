"""P196 evidence bound to real one-shot Dell issuer source / no fake rights."""
from __future__ import annotations

import unittest
from proofinvest.dell_2026_publisher_evidence import (
    actual_p195_source_receipt as receipt,
    review_verified_dell_first_party_raw_evidence as review,
)


class DellOriginalBasedEvidenceTests(unittest.TestCase):
    def test_observed_raw_first_party_2026_10k_real_numeric_result(self):
        r=review(as_of="2026-11-05", receipt=receipt())
        self.assertEqual(r["status"],
                         "DELL_REAL_FIRST_PARTY_ORIGINAL_NUMERIC_REVIEW_READY_LIMITED")
        self.assertTrue(r["publisher_https_original_seen"])
        e=r["evidence"]
        self.assertEqual(e["raw_original_byte_count"], 3610307)
        self.assertEqual(e["revenue_yoy_pct"], "18.80")
        self.assertEqual(e["cash_flow_to_net_income_ratio"], "1.8843")
        self.assertEqual(e["cash_flow_exceeds_net_income_usd_millions"], "5249")
        self.assertTrue(e["source_url"].startswith("https://investors.delltechnologies.com/"))
        self.assertEqual(e["actual_issuer_https_gets"], 1)
        for flag in ("sec_edgar_original_byte_equivalence_verified",
                     "source_rights_verified", "full_engine_b_authenticated",
                     "full_engine_abc_ready", "peer_licensed_and_period_aligned",
                     "price_ndx_licensed", "model_input_authorized",
                     "ai_agent_executed", "trade_executed", "raw_original_retained"):
            self.assertIs(r[flag], False, flag)

    def test_tampered_digest_size_url_issuer_rights_and_status_blocks(self):
        for name, val in (
            ("source_original_sha256", "f"*64),
            ("source_original_bytes", 3610308),
            ("public_issuer_report_url", "https://www.sec.gov/no"),
            ("ticker", "AAPL"),
            ("annual_net_revenue_2026_usd_millions", "113539"),
            ("source_rights_verified", True),
            ("issuer_https_host_verified", False),
            ("sec_edgar_identical_original_verified", True),
            ("issuer_https_get_attempted", 2),
            ("status", "UNAVAILABLE"),
        ):
            changed=receipt()
            changed[name]=val
            with self.subTest(name=name):
                r=review(as_of="2026-11-05", receipt=changed)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertIsNone(r["evidence"])
                self.assertFalse(r["publisher_https_original_seen"])

    def test_as_of_cannot_claim_prior_or_unreviewed_future_source(self):
        for d in ("2026-11-03", "2026-11-04", "2026-11-06", None):
            self.assertEqual(review(as_of=d,receipt=receipt())["status"], "BLOCKED")

    def test_receipt_mutation_not_global_evidence_and_no_network(self):
        copy=receipt()
        copy["source_original_sha256"]="0"*64
        self.assertTrue(receipt()["source_original_sha256"].startswith("c4852401"))
        self.assertEqual(review(as_of="2026-11-05",receipt=receipt())["network_requests"],0)


if __name__=="__main__":
    unittest.main()
