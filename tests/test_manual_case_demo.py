"""Synthetic test inputs plus prior manual issuer receipt; no external requests."""
import copy
import json
import subprocess
import sys
import unittest

from proofinvest import manual_case_demo as demo


class PublishedManualCaseTests(unittest.TestCase):
    def test_offline_issuer_chain_claim_agrees_and_risk_withheld(self):
        r = demo.run_manual_case()
        self.assertEqual(r["research"]["status"], "success")
        self.assertTrue(r["trace_linked"])
        self.assertEqual(r["verification"]["computed_pct"], "16.20")
        self.assertEqual(r["verification"]["state"], "verified")
        self.assertFalse(r["risk"]["risk_calculated"])
        self.assertEqual(r["risk"]["status"], "unavailable")
        self.assertEqual(r["status"], "partial")

    def test_conflicting_claim_prevents_risk(self):
        r = demo.run_manual_case("30")
        self.assertEqual(r["verification"]["state"], "conflict")
        self.assertIsNone(r["risk"]["ratio_pct"])

    def test_unreadable_claim_is_unavailable(self):
        r = demo.run_manual_case("not-a-number")
        self.assertEqual(r["verification"]["state"], "unavailable")
        self.assertFalse(r["risk"]["risk_calculated"])

    def test_no_fake_external_or_current_year_authentication(self):
        r = demo.run_manual_case()
        for field in ("authenticated_external_source", "live_api_called", "ai_agent_executed",
                      "source_rights_verified", "latest_fiscal_year_claimed",
                      "actual_pdf_reopened_on_this_execution", "dart_viewer_accessed_on_this_execution"):
            self.assertIs(r[field], False)
        self.assertIs(r["verification"]["dart_viewer_verified"], False)
        self.assertTrue(r["risk_unavailable_due_to_missing_balance_sheet_evidence"])

    def test_official_issuer_page_and_rights_separated(self):
        r = demo.run_manual_case()
        self.assertEqual(r["issuer_ir_listed_at"], "2025-02-18")
        self.assertEqual(r["issuer_ir_listing"], demo.IR_PAGE)
        source = r["research"]["sources"][0]
        self.assertEqual(source["url"], demo.EXPECTED_PDF)
        self.assertEqual(source["rights_review_status"], "not_verified")
        self.assertEqual(source["redistribution_clearance"], "not_established")

    def test_issuer_pdf_and_year_tampering_fail_closed(self):
        evidence = json.loads(demo.EVIDENCE_PATH.read_text(encoding="utf-8"))
        for change in ("pdf", "corp", "year"):
            with self.subTest(change=change):
                e = copy.deepcopy(evidence)
                if change == "pdf":
                    e["primary_source"]["url"] = "https://example.org/forged.pdf"
                elif change == "corp":
                    e["corp_code"] = "00000001"
                else:
                    e["report_year"] = 2025
                with self.assertRaisesRegex(ValueError, "changed"):
                    demo.make_research_request(e)

    def test_real_cli_entrypoint_for_matching_and_conflicting_claims(self):
        for args, state in (([], "verified"), (["--claim", "30"], "conflict")):
            with self.subTest(args=args):
                proc = subprocess.run(
                    [sys.executable, "-m", "proofinvest.manual_case_demo", *args],
                    check=True, text=True, capture_output=True,
                )
                d = json.loads(proc.stdout)
                self.assertEqual(d["verification"]["state"], state)
                self.assertFalse(d["live_api_called"])
                self.assertFalse(d["risk"]["risk_calculated"])


if __name__ == "__main__":
    unittest.main()
