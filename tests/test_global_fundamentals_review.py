"""Global US issuer review that requires zero Nasdaq or stock-feed API data."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.global_fundamentals_review import (
    build_marketless_global_review, verify_marketless_global_review,
    marketless_global_review_html,
)


def review(ticker="NVDA"):
    return build_marketless_global_review(ticker=ticker)


class GlobalFundamentalsReviewTests(unittest.TestCase):
    def test_nvda_real_issuer_and_two_peers_without_market_source(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("LIVE_HTTP_FORBIDDEN")) as network:
            packet = review()
            self.assertTrue(verify_marketless_global_review(packet), packet)
            html = marketless_global_review_html(packet)
        network.assert_not_called()
        self.assertEqual(packet["status"], "GLOBAL_ISSUER_B_C_LIMITED_GUARD_HOLD")
        self.assertEqual(packet["ticker"], "NVDA")
        self.assertEqual(packet["engine_a"]["status"],
                         "UNAVAILABLE_NO_ENTITLED_MARKET_OR_NDX_DATA")
        self.assertIsNone(packet["engine_a"]["beta"])
        self.assertEqual(packet["engine_b"]["revenue_growth_pct"], "65.47")
        self.assertEqual(packet["engine_b"]["cashflow_to_net_income_ratio"], "0.8555")
        self.assertEqual([p["ticker"] for p in packet["engine_c"]["peers"]],
                         ["AMD", "INTC"])
        self.assertEqual([p["revenue_growth_pct"] for p in packet["engine_c"]["peers"]],
                         ["34.34", "-0.47"])
        self.assertEqual(packet["guard"]["decision"], "HOLD")
        self.assertEqual(packet["guard"]["reason_codes"],
                         ["CLAIM_UNAVAILABLE", "RISK_UNAVAILABLE"])
        self.assertEqual(packet["market_api_requests"], 0)
        self.assertEqual(packet["llm_requests"], 0)
        self.assertEqual(len(packet["trace"]), 4)
        self.assertTrue(packet["publisher_original_observed"])
        for flag in ("source_rights_verified", "external_sharing_allowed",
                     "sec_original_identical", "full_abc_complete",
                     "ai_agent_executed", "trade_executed",
                     "investment_recommendation", "human_approved"):
            self.assertIs(packet[flag], False, flag)
        self.assertIn(b"<html", html)
        self.assertNotIn(b"<script", html.lower())
        self.assertNotIn(b"apikey", html.lower())
        self.assertNotIn(b"Time Series (Daily)", html)

    def test_descriptive_review_candidates_not_fraud_or_guard_authorization(self):
        nvda = review("NVDA")
        dell = review("DELL")
        self.assertTrue(verify_marketless_global_review(nvda))
        self.assertTrue(verify_marketless_global_review(dell))
        self.assertEqual([s["code"] for s in nvda["engine_b"]["screening_signals"]],
                         ["INVENTORY_GROWTH_GAP"])
        self.assertEqual([s["code"] for s in dell["engine_b"]["screening_signals"]],
                         ["RECEIVABLES_GROWTH_GAP", "INVENTORY_GROWTH_GAP"])
        self.assertEqual(nvda["engine_b"]["screening_status"],
                         "REVIEW_CANDIDATES_PRESENT")
        self.assertEqual(dell["engine_b"]["screening_status"],
                         "REVIEW_CANDIDATES_PRESENT")
        for report in (nvda, dell):
            self.assertTrue(report["engine_b"]["screening_not_fraud_conclusion"])
            self.assertFalse(report["engine_b"]["fraud_proven"])
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertFalse(report["external_sharing_allowed"])
            self.assertFalse(report["full_abc_complete"])
            self.assertIn(b"REVIEW_CANDIDATE",
                          marketless_global_review_html(report))
        forged = deepcopy(nvda)
        forged["engine_b"]["screening_signals"].clear()
        unsigned = deepcopy(forged)
        unsigned.pop("integrity_sha256")
        forged["integrity_sha256"] = sha256(json.dumps(
            unsigned, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertFalse(verify_marketless_global_review(forged))

    def test_dell_real_issuer_b_peer_unavailable(self):
        packet = review("DELL")
        self.assertTrue(verify_marketless_global_review(packet), packet)
        self.assertEqual(packet["engine_b"]["revenue_growth_pct"], "18.80")
        self.assertEqual(packet["engine_b"]["cashflow_to_net_income_ratio"], "1.8843")
        self.assertEqual(packet["engine_c"]["peers"], [])
        self.assertEqual(packet["engine_c"]["status"],
                         "UNAVAILABLE_NO_SOURCE_BOUND_PEER_COHORT")
        self.assertEqual(packet["guard"]["decision"], "HOLD")

    def test_unknown_ticker_vintage_and_input_type_are_blocked(self):
        for args in ({"ticker": "AAPL"}, {"ticker": "nvda"},
                     {"ticker": "NVDA", "as_of": "2026-11-06"},
                     {"ticker": "NVDA", "as_of": "2027-01-01"},
                     {"ticker": None}):
            with self.subTest(args=args):
                data=build_marketless_global_review(**args)
                self.assertEqual(data["status"], "BLOCKED")
                self.assertFalse(verify_marketless_global_review(data))
                with self.assertRaises(ValueError):
                    marketless_global_review_html(data)

    def test_tampered_metrics_rights_guard_and_hash_do_not_replay(self):
        packet=review()
        self.assertTrue(verify_marketless_global_review(packet))
        for path,value in (
            (("engine_b","revenue_growth_pct"),"100.00"),
            (("source","publisher_raw_sha256"),"a"*64),
            (("source_rights_verified",),True),
            (("engine_c","peers"),[]),
            (("guard","decision"),"APPROVE"),
        ):
            changed=deepcopy(packet)
            at=changed
            for key in path[:-1]:
                at=at[key]
            at[path[-1]]=value
            with self.subTest(path=path):
                unsigned=deepcopy(changed)
                unsigned.pop("integrity_sha256")
                changed["integrity_sha256"]=sha256(json.dumps(
                    unsigned,sort_keys=True,ensure_ascii=False,
                    separators=(",",":"),allow_nan=False).encode()).hexdigest()
                self.assertFalse(verify_marketless_global_review(changed))
                with self.assertRaises(ValueError):
                    marketless_global_review_html(changed)

    def test_failed_issuer_ledger_and_peer_cannot_promote_approval(self):
        with patch("proofinvest.global_fundamentals_review.review_supported_real_ticker",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review()["status"],"BLOCKED")
        with patch("proofinvest.global_fundamentals_review.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(review()["status"],"BLOCKED")
        packet=review()
        self.assertEqual(packet["guard_policy_preview"],"HOLD")
        self.assertEqual(packet["source"]["sec_edgar_raw_identity_verified"],False)

    def test_guard_failure_fails_closed(self):
        with patch("proofinvest.global_fundamentals_review.evaluate_guard",
                   return_value={"decision":"APPROVE"}):
            packet=review("DELL")
            self.assertEqual(packet["status"],"BLOCKED")
            self.assertFalse(verify_marketless_global_review(packet))


if __name__ == "__main__":
    unittest.main()
