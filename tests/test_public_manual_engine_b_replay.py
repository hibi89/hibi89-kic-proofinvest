"""P56: actual Engine B code replays real manually recorded Apple facts offline."""
from __future__ import annotations

import copy
from unittest import TestCase
from unittest.mock import patch

from proofinvest.public_primary_baseline import APPLE, CURATED, _read
from proofinvest.public_manual_engine_b_replay import (
    replay_manual_apple_through_engine_b, main,
)


class ManualEngineBReplayTests(TestCase):
    def setUp(self):
        self.manual = _read(APPLE)
        self.curated = _read(CURATED)

    def test_real_manually_published_figures_use_actual_engine_b_code(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")) as net:
            result = replay_manual_apple_through_engine_b(self.manual, self.curated)
        net.assert_not_called()
        self.assertEqual(result["engine_b_status"], "reviewed_unverified")
        self.assertEqual(result["engine_b_earnings_cash_signal"],
                         "CFO_BELOW_POSITIVE_EARNINGS")
        self.assertEqual(result["engine_b_working_capital_signals"],
                         ["RECEIVABLES_OUTPACED_REVENUE"])
        obs = result["engine_b_observations"]
        self.assertEqual(obs["net_income_usd"], "112010000000")
        self.assertEqual(obs["operating_cashflow_usd"], "111482000000")
        self.assertEqual(obs["earnings_less_cash_usd"], "528000000")
        self.assertEqual(obs["revenue_growth_pct"], "6.43")
        self.assertEqual(obs["receivables_minus_revenue_growth_pp"], "12.63")
        self.assertEqual(obs["cash_to_net_income_pct"], "99.53")
        self.assertEqual(obs["inventory_growth_pct"], "-21.52")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["automatic_sec_to_guard_end_to_end_verified"])
        self.assertTrue(result["reconstructed_sec_shape_not_raw_api"])
        self.assertFalse(result["actual_sec_raw_companyfacts_used"])
        self.assertEqual(len(result["derived_input_sha256_not_original_sec"]), 64)

    def test_original_inputs_not_mutated_and_no_downloads(self):
        before_manual, before_curated = copy.deepcopy(self.manual), copy.deepcopy(self.curated)
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")), \
             patch("urllib.request.urlretrieve", side_effect=AssertionError("NO_DOWNLOAD")):
            result = replay_manual_apple_through_engine_b(self.manual, self.curated)
        self.assertEqual(before_manual, self.manual)
        self.assertEqual(before_curated, self.curated)
        self.assertFalse(result["persistent_derived_record_written"])
        self.assertFalse(result["guard_decision_modified"])
        self.assertFalse(result["trade_executed"])
        self.assertFalse(result["fraud_proven"])
        self.assertEqual(result["network_requests"], 0)

    def test_change_manual_revenue_rejected_before_engine_b(self):
        altered = copy.deepcopy(self.manual)
        altered["current"]["net_sales"] = "416162"
        with patch("proofinvest.public_manual_engine_b_replay.review_accounting_integrity",
                   side_effect=AssertionError("MUST_NOT_CALL_ENGINE_B")):
            with self.assertRaises(ValueError):
                replay_manual_apple_through_engine_b(altered, self.curated)

    def test_curated_10k_amount_tampering_prevents_replay(self):
        altered = copy.deepcopy(self.curated)
        altered["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"][0]["val"] += 1
        with self.assertRaisesRegex(ValueError, "PUBLIC_ISSUER_PDF_VS_CURATED_SEC_REVENUE_CONFLICT"):
            replay_manual_apple_through_engine_b(self.manual, altered)

    def test_fiscal_asof_issuer_or_source_rights_rejected(self):
        for kind in ("cik", "fiscal", "asof", "rights", "fake_pdf", "currency"):
            altered = copy.deepcopy(self.manual)
            if kind == "cik":
                altered["cik"] = "0000000001"
            elif kind == "fiscal":
                altered["prior"]["end"] = "2024-09-27"
            elif kind == "asof":
                altered["as_of"] = "2025-10-30"
            elif kind == "rights":
                altered["source"]["distribution_rights_verified"] = True
            elif kind == "fake_pdf":
                altered["source"]["pdf_original_sha256_authenticated"] = True
            else:
                altered["currency"] = "KRW"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                replay_manual_apple_through_engine_b(altered, self.curated)

    def test_core_bad_status_or_forged_authenticity_blocked(self):
        with patch("proofinvest.public_manual_engine_b_replay.review_accounting_integrity",
                   return_value={"schema": "kuodra.accounting-integrity-offline.v1",
                                 "status": "reviewed_unverified",
                                 "source_authenticated": True}):
            with self.assertRaisesRegex(ValueError, "DERIVED_ENGINE_B_TRUST_OR_STATUS_MISMATCH"):
                replay_manual_apple_through_engine_b(self.manual, self.curated)

    def test_core_edited_number_or_fake_positive_result_blocked(self):
        from proofinvest.accounting_integrity import review_accounting_integrity as real
        def tampered(*args, **kwargs):
            out = real(*args, **kwargs)
            out["receivables_minus_revenue_growth_pp"] = "0.00"
            return out
        with patch("proofinvest.public_manual_engine_b_replay.review_accounting_integrity",
                   side_effect=tampered):
            with self.assertRaisesRegex(ValueError, "DERIVED_ENGINE_B_DISAGREES_WITH_PRIMARY_MANUAL_REPLAY"):
                replay_manual_apple_through_engine_b(self.manual, self.curated)

    def test_core_edited_review_signal_blocked(self):
        from proofinvest.accounting_integrity import review_accounting_integrity as real
        def tampered(*args, **kwargs):
            out = real(*args, **kwargs)
            out["working_capital_signals"] = []
            return out
        with patch("proofinvest.public_manual_engine_b_replay.review_accounting_integrity",
                   side_effect=tampered):
            with self.assertRaisesRegex(ValueError, "DERIVED_ENGINE_B_REVIEW_SIGNAL_DISAGREEMENT"):
                replay_manual_apple_through_engine_b(self.manual, self.curated)

    def test_cli_stdout_json_does_not_claim_sec_authentication(self):
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        buf = StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main([]), 0)
        report = json.loads(buf.getvalue())
        self.assertFalse(report["manual_source_authenticated_by_software"])
        self.assertIn("MANUAL", report["manual_issuer_statement"])
        self.assertIsNone(report["future_growth_forecast"])
        self.assertFalse(report["investment_recommendation"])
        self.assertNotIn("facts", report)


