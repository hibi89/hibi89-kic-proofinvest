"""P57 issuer-hosted FY2025 10-K manually viewed numbers -> real Engine B tools."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import unittest
from unittest.mock import patch

from proofinvest.apple_audited_10k_replay import (
    TEN_K, _make_derived_facts, _read, main, replay_audited_10k_manual_excerpt,
)
from proofinvest.public_primary_baseline import APPLE, CURATED


class Apple10KManualReplayTests(unittest.TestCase):
    def setUp(self):
        self.doc = _read(TEN_K)
        self.manual = _read(APPLE)
        self.curated = _read(CURATED)

    def run_replay(self, doc=None, manual=None, curated=None):
        return replay_audited_10k_manual_excerpt(
            self.doc if doc is None else doc,
            self.manual if manual is None else manual,
            self.curated if curated is None else curated,
        )

    def test_real_issuer_10k_reconciles_with_unmodified_engine_b_modules(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
            out = self.run_replay()
        net.assert_not_called()
        self.assertTrue(out["press_release_10k_manual_numeric_match"])
        self.assertTrue(out["prior_engine_b_replay_passed"])
        self.assertEqual(out["engine_b_balance_status"], "reviewed_unverified")
        self.assertEqual(out["engine_b_cashflow_status"], "reviewed_unverified")
        self.assertEqual(out["balance_2025_liabilities_to_equity_pct"], "387.22")
        self.assertEqual(out["balance_2024_liabilities_to_equity_pct"], "540.88")
        self.assertTrue(out["balance_2025_identity_match"])
        self.assertTrue(out["balance_2024_identity_match"])
        self.assertEqual(out["fcf_proxy_2025_usd_millions"], "98767")
        self.assertEqual(out["fcf_proxy_2024_usd_millions"], "108807")
        self.assertEqual(out["fcf_proxy_yoy_pct"], "-9.23")
        self.assertTrue(out["fcf_proxy_is_non_gaap"])
        self.assertEqual(out["receivables_minus_sales_growth_pp"], "12.63")
        self.assertEqual(out["review_signals"], ["RECEIVABLES_OUTPACED_REVENUE"])
        self.assertEqual(len(out["derived_input_sha256_not_original_sec"]), 64)

    def test_source_is_manual_not_independently_authenticated(self):
        out = self.run_replay()
        for key in ("original_auditor_opinion_automatically_verified",
                    "original_raw_10k_bytes_authenticated",
                    "original_sec_companyfacts_authenticated",
                    "original_sec_submissions_authenticated",
                    "data_rights_verified", "automatic_sec_3_source_guard_real_data_validated",
                    "real_world_market_and_industry_validated",
                    "fraud_proven", "investment_recommendation",
                    "source_authenticated", "guard_policy_modified",
                    "trade_executed", "original_html_retained", "derived_facts_retained"):
            with self.subTest(key=key):
                self.assertIs(out[key], False)
        self.assertEqual(out["network_requests"], 0)
        self.assertEqual(out["ai_requests"], 0)
        self.assertIn("NOT_ORIGINAL_BYTES", out["source_kind"])

    def test_inputs_are_unchanged_and_derived_facts_not_returned(self):
        snapshots = deepcopy((self.doc, self.manual, self.curated))
        result = self.run_replay()
        self.assertEqual((self.doc, self.manual, self.curated), snapshots)
        self.assertNotIn("facts", result)
        self.assertNotIn("derived_bytes", result)
        self.assertNotIn("original_html", result)

    def test_tampered_issuer_10k_vs_press_release_denied(self):
        for label, field, period in (("sales", "sales", "current"),
                                     ("cfo", "operating_cashflow", "current"),
                                     ("receivables", "accounts_receivable_net", "current"),
                                     ("inventory", "inventory_net", "prior"),
                                     ("net_income", "net_income", "current")):
            doc = deepcopy(self.doc)
            # Keep accounting identities intact where possible: cross-source
            # mismatch, not a self-reconciliation failure, should still block.
            doc[period][field] = str(int(doc[period][field]) + 1)
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.run_replay(doc=doc)

    def test_balances_must_reconcile_on_both_issuer_years(self):
        for period in ("current", "prior"):
            doc = deepcopy(self.doc)
            doc[period]["liabilities"] = str(int(doc[period]["liabilities"]) + 1)
            with self.subTest(period=period), self.assertRaisesRegex(
                    ValueError, "TEN_K_MANUAL_BALANCE_IDENTITY_FAILED"):
                self.run_replay(doc=doc)

    def test_10k_income_components_must_reconcile(self):
        doc = deepcopy(self.doc)
        doc["current"]["products"] = "307004"
        with self.assertRaisesRegex(ValueError, "TEN_K_MANUAL_INCOME_RECONCILIATION_FAILED"):
            self.run_replay(doc=doc)
        doc = deepcopy(self.doc)
        doc["prior"]["gross_margin"] = "180684"
        with self.assertRaisesRegex(ValueError, "TEN_K_MANUAL_INCOME_RECONCILIATION_FAILED"):
            self.run_replay(doc=doc)

    def test_10k_issuer_accession_fiscal_and_unit_bound(self):
        for change in ("cik", "issuer", "accession", "as_of", "filing", "unit",
                       "currency", "fiscal", "statement"):
            doc = deepcopy(self.doc)
            if change == "cik": doc["cik"] = "0000000001"
            elif change == "issuer": doc["issuer"] = "Other Company"
            elif change == "accession": doc["accession"] = "0000320193-25-000080"
            elif change == "as_of": doc["as_of"] = "2025-10-30"
            elif change == "filing": doc["filed_at"] = "2025-10-30"
            elif change == "unit": doc["unit"] = "USD"
            elif change == "currency": doc["currency"] = "KRW"
            elif change == "fiscal": doc["fiscal"]["current_start"] = "2024-09-30"
            else: doc["statement_basis"] = "UNAUDITED_PRESS_RELEASE"
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_replay(doc=doc)

    def test_forged_source_original_rights_and_document_refused(self):
        for change in ("url", "index", "rawsha", "rights", "api", "manual",
                       "opinion", "page"):
            doc = deepcopy(self.doc)
            source = doc["source"]
            if change == "url": source["url"] = "https://example.org/fake.htm"
            elif change == "index": source["sec_index_reference"] = "https://example.org"
            elif change == "rawsha": source["source_raw_html_sha256_verified"] = True
            elif change == "rights": source["distribution_rights_verified"] = True
            elif change == "api": source["original_sec_api_authenticated"] = True
            elif change == "manual": source["issuer_html_viewed_manually"] = False
            elif change == "opinion": source["independent_auditor_opinion_printed_page"] = 47
            else: source["financial_statement_printed_pages"] = [1, 2, 3]
            with self.subTest(change=change), self.assertRaisesRegex(
                    ValueError, "TEN_K_MANUAL_SOURCE_TRUST_CONTRACT_INVALID"):
                self.run_replay(doc=doc)

    def test_invalid_or_unknown_financial_fields_refused(self):
        for value in (True, 0.5, "-1", "NaN", "01", "1e9", None):
            doc = deepcopy(self.doc)
            doc["current"]["capex_payments"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.run_replay(doc=doc)
        doc = deepcopy(self.doc)
        doc["current"]["EXTRA"] = "123"
        with self.assertRaisesRegex(ValueError, "TEN_K_MANUAL_ROW_FIELDS_INVALID"):
            self.run_replay(doc=doc)

    def test_forged_engine_b_balance_auth_is_rejected(self):
        from proofinvest.kuodra_sec_balance import review_sec_balance_sheet as original
        def forged(*args, **kwargs):
            result = original(*args, **kwargs)
            result["source_authenticated"] = True
            return result
        with patch("proofinvest.apple_audited_10k_replay.review_sec_balance_sheet",
                   side_effect=forged), self.assertRaisesRegex(
                       ValueError, "TEN_K_ENGINE_B_BALANCE_REVIEW_MISMATCH"):
            self.run_replay()

    def test_wrong_engine_b_fcf_is_rejected(self):
        from proofinvest.kuodra_sec_cashflow import review_sec_annual_cashflow as original
        def wrong(*args, **kwargs):
            result = original(*args, **kwargs)
            result["free_cashflow_proxy_usd"] = "999"
            return result
        with patch("proofinvest.apple_audited_10k_replay.review_sec_annual_cashflow",
                   side_effect=wrong), self.assertRaisesRegex(
                       ValueError, "TEN_K_ENGINE_B_CASHFLOW_REVIEW_MISMATCH"):
            self.run_replay()

    def test_existing_manual_replay_must_pass_before_new_engines(self):
        with patch("proofinvest.apple_audited_10k_replay.replay_manual_apple_through_engine_b",
                   return_value={"source_authenticated": True}):
            with self.assertRaisesRegex(ValueError, "TEN_K_PRIOR_MANUAL_ENGINE_B_TRUST_FAILED"):
                self.run_replay()

    def test_cli_offline_receipt_does_not_claim_raw_auth(self):
        stream = StringIO()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")), \
             redirect_stdout(stream):
            self.assertEqual(main([]), 0)
        parsed = json.loads(stream.getvalue())
        self.assertEqual(parsed["status"],
                         "MANUAL_FIRST_PARTY_10K_NUMBERS_CROSSCHECKED_WITH_P55_AND_ENGINE_B")
        self.assertFalse(parsed["original_sec_companyfacts_authenticated"])
        self.assertTrue(parsed["fcf_proxy_is_non_gaap"])


if __name__ == "__main__":
    unittest.main()
