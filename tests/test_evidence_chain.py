"""Only synthetic supplied records used to test the offline workflow bridge."""
import copy
import unittest

from proofinvest.evidence_chain import evaluate_offline_chain


def fixture():
    url = "https://example.org/issuer-filing.pdf"
    financial = {
        "evidence_type": "MANUAL_PRIMARY_SOURCE_VERIFICATION",
        "subject": "Synthetic Sample Holdings",
        "corp_code": "00126380",
        "financial_statement": "CFS",
        "metric": "revenue", "unit": "KRW_MILLIONS",
        "report_year": 2024, "report_type": "ANNUAL",
        "current": {
            "fiscal_year": 2024, "period_start": "2024-01-01",
            "period_end": "2024-12-31", "amount": "11620",
        },
        "previous": {
            "fiscal_year": 2023, "period_start": "2023-01-01",
            "period_end": "2023-12-31", "amount": "10000",
        },
        "result": {"absolute_change": "1620", "growth_pct_rounded_2dp": "16.20"},
        "primary_source": {"url": url, "publisher": "Synthetic Example", "visual_verified": True},
        "dart_filing": {"direct_viewer_verified": True},
    }
    research = {
        "target_name": "Synthetic Sample Holdings", "target_id": "00126380",
        "as_of": "2026-10-24",
        "sources": [{
            "id": "S1", "title": "Synthetic Issuer Financial Filing",
            "url": url, "published_at": "2025-03-11",
            "collected_at": "2026-10-24", "license": "not_verified",
        }],
        "findings": [{
            "claim": "Synthetic 2024 revenue exceeds previous revenue",
            "source_ids": ["S1"], "as_of": "2026-10-24",
        }],
    }
    common = {
        "state": "verified", "year": 2024, "fs_div": "CFS",
        "unit": "KRW", "report_code": "11011", "period_end": "2024-12-31",
        "issuer_id": "00126380", "evidence_ref": "SYNTHETIC_TEST",
        "source_url": url, "source_kind": "MANUAL_PRIMARY_SOURCE_VERIFICATION",
    }
    facts = [dict(common, metric="liabilities", current_amount="80"),
             dict(common, metric="equity", current_amount="30")]
    return research, financial, facts


def run(research=None, financial=None, risk=None, claim="16.20"):
    r, e, f = fixture()
    return evaluate_offline_chain(
        research_request=r if research is None else research,
        financial_evidence=e if financial is None else financial,
        claimed_growth_pct=claim,
        risk_facts=f if risk is None else risk,
    )


class EvidenceChainTests(unittest.TestCase):
    def test_same_source_run_all_three_stages_but_remains_unverified(self):
        result = run()
        self.assertEqual(result["status"], "structurally_calculated_unverified")
        self.assertEqual(result["research"]["status"], "success")
        self.assertEqual(result["verification"]["state"], "verified")
        self.assertFalse(result["verification"]["dart_viewer_verified"])
        self.assertTrue(result["trace_linked"])
        self.assertEqual(result["risk"]["ratio_pct"], "266.67")
        self.assertFalse(result["risk"]["authenticated_external_source"])
        self.assertFalse(result["ai_agent_executed"])
        self.assertFalse(result["source_rights_verified"])

    def test_wrong_claim_blocks_downstream_risk(self):
        result = run(claim="30")
        self.assertEqual(result["verification"]["state"], "conflict")
        self.assertEqual(result["risk"]["status"], "unavailable")
        self.assertIsNone(result["risk"]["ratio_pct"])

    def test_no_financial_evidence_blocks_risk(self):
        result = run(financial={})
        self.assertFalse(result["trace_linked"])
        self.assertFalse(result["risk"]["risk_calculated"])

    def test_wrong_research_citation_blocks_risk(self):
        r,e,f = fixture()
        r["sources"][0]["url"] = "https://example.org/different.pdf"
        result = run(research=r)
        self.assertFalse(result["trace_linked"])
        self.assertEqual(result["status"], "unavailable")

    def test_no_supported_finding_blocks_risk(self):
        r,e,f = fixture()
        r["findings"][0]["source_ids"] = ["missing"]
        result = run(research=r)
        self.assertFalse(result["trace_linked"])
        self.assertFalse(result["risk"]["risk_calculated"])

    def test_cross_issuer_and_cross_source_risk_facts_blocked(self):
        for field,value in (("issuer_id","00000001"),("source_url","https://example.org/other.pdf"),
                            ("source_kind","SYNTHETIC_FIXTURE")):
            with self.subTest(field=field):
                r,e,f=fixture()
                f[1][field]=value
                out=run(risk=f)
                self.assertTrue(out["trace_linked"])
                self.assertFalse(out["risk"]["risk_calculated"])

    def test_missing_risk_facts_stays_partial(self):
        out=run(risk=[])
        self.assertEqual(out["status"], "partial")
        self.assertFalse(out["risk"]["risk_calculated"])

    def test_research_issuer_mismatch_blocks_even_when_urls_match(self):
        r,e,f=fixture()
        r["target_id"]="00000001"
        out=run(research=r)
        self.assertFalse(out["trace_linked"])

    def test_inputs_not_mutated_or_dependent_on_order(self):
        r,e,f=fixture()
        originals=copy.deepcopy((r,e,f))
        first=run(research=r, financial=e, risk=f)
        second=run(research=r, financial=e, risk=list(reversed(f)))
        self.assertEqual(first, second)
        self.assertEqual((r,e,f), originals)

    def test_invalid_research_request_fails_closed(self):
        result=evaluate_offline_chain(
            research_request=[], financial_evidence=None, claimed_growth_pct="16.20"
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["risk"]["risk_calculated"])


if __name__ == "__main__":
    unittest.main()
