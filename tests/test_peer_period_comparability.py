"""P93: source-bound period/US-GAAP concept peer-comparability gates.

All examples are offline synthetic SEC-shaped annual CompanyFacts; no SEC
original is downloaded or treated as authenticated.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.peer_cash_conversion import compare_peer_cash_conversion
from proofinvest.peer_period_comparability import assess_peer_period_comparability
from proofinvest.sec_companyfacts import TAG
from tests.test_industry_packet_builder import build
from tests.test_peer_cash_conversion import prepared, NI, CFO
from tests.test_peer_cash_trend import extend_with_prior

START_NOW = "2024-10-02"
START_PRIOR = "2023-10-02"


def _modified_peer(target, peers, *,
                   now_cash_start=None, now_revenue_start=None,
                   prior_cash_start=None, prior_revenue_start=None,
                   revenue_tag=None):
    new_peers = list(peers)
    cik, acc, raw = new_peers[0]
    obj = json.loads(raw)
    facts = obj["facts"]["us-gaap"]
    for key in (NI, CFO):
        for row in facts[key]["units"]["USD"]:
            if row["end"] == "2025-09-30" and now_cash_start:
                row["start"] = now_cash_start
            elif row["end"] == "2024-09-30" and prior_cash_start:
                row["start"] = prior_cash_start
    if now_revenue_start or prior_revenue_start:
        for row in facts[TAG]["units"]["USD"]:
            if row["end"] == "2025-09-30" and now_revenue_start:
                row["start"] = now_revenue_start
            elif row["end"] == "2024-09-30" and prior_revenue_start:
                row["start"] = prior_revenue_start
    if revenue_tag is not None:
        facts[revenue_tag] = facts.pop(TAG)
    new_peers[0] = (cik, acc, json.dumps(obj, sort_keys=True).encode())
    return new_peers


def _packet(target, peers):
    return build(
        target[2], peers[0][2],
        target=(target[0], target[1], "SYNTHETIC_TARGET", target[2]),
        peers=[(cik, acc, "SYNTHETIC_PEER_" + str(i), raw)
               for i, (cik, acc, raw) in enumerate(peers, 1)],
    )


class PeerPeriodComparabilityTests(unittest.TestCase):
    def test_complete_identical_windows_preserve_all_ratios(self):
        packet, target, peers = extend_with_prior()
        source_hashes = [sha256(entry[2]).hexdigest()
                         for entry in [target, *peers]]
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_PROVIDER_HTTP")) as web:
            result = compare_peer_cash_conversion(
                packet, target_source=target, peer_sources=peers)
        web.assert_not_called()
        self.assertEqual(result["cash_conversion_target_pct"], "33.33")
        self.assertEqual(result["two_year_target_minus_peer_change_pp"], "-91.67")
        audit = result["period_comparability"]
        self.assertEqual(audit["current_status"],
                         "MATCHED_CURRENT_ANNUAL_WINDOW_LOCAL_ONLY")
        self.assertEqual(audit["two_year_status"],
                         "MATCHED_TWO_YEAR_ANNUAL_WINDOWS_LOCAL_ONLY")
        self.assertEqual(audit["revenue_concept_status"],
                         "SAME_US_GAAP_TAG_LOCAL_ONLY")
        self.assertEqual(audit["candidate_count"], 2)
        self.assertEqual(audit["missing_current_count"], 0)
        self.assertEqual(audit["missing_two_year_count"], 0)
        self.assertTrue(audit["current_cash_median_eligible"])
        self.assertTrue(audit["two_year_cash_median_eligible"])
        self.assertEqual(audit["coverage"][0]["cash_annual_start"],
                         {"prior": "2023-10-01", "current": "2024-10-01"})
        self.assertEqual([row["companyfacts_sha256"]
                          for row in audit["coverage"]], source_hashes)
        self.assertTrue(audit["same_annual_dates_not_accounting_policy_equivalence"])
        for key in ("cross_issuer_accounting_policy_verified",
                    "original_source_authenticated",
                    "historical_vintage_authenticated", "data_rights_verified",
                    "guard_policy_modified", "audit_written", "trade_executed"):
            self.assertIs(audit[key], False)
        self.assertEqual(json.loads(json.dumps(result)), result)

    def test_mismatched_cash_and_revenue_current_start_withholds_current_and_trend(self):
        _, target, peers = extend_with_prior()
        altered = _modified_peer(target, peers, now_cash_start=START_NOW)
        result = compare_peer_cash_conversion(
            _packet(target, altered), target_source=target, peer_sources=altered)
        self.assertEqual(result["status"], "PERIOD_WINDOW_COMPARISON_WITHHELD")
        self.assertEqual(result["two_year_trend_status"],
                         "PERIOD_WINDOW_TWO_YEAR_COMPARISON_WITHHELD")
        self.assertEqual(result["period_comparability"]["current_status"],
                         "CASH_REVENUE_CURRENT_WINDOW_MISMATCH")
        self.assertIsNone(result["cash_conversion_peer_median_pct"])
        self.assertIsNone(result["target_minus_peer_median_pp"])
        self.assertIsNone(result["two_year_peer_median_change_pp"])
        self.assertEqual(result["rows"][1]["cash_conversion_pct"], "50.00")
        self.assertEqual(result["rows"][1]["cash_conversion_trend"]["change_pp"],
                         "25.00")

    def test_same_company_current_matches_but_competitor_fiscal_start_differs(self):
        _, target, peers = extend_with_prior()
        altered = _modified_peer(target, peers,
                                 now_cash_start=START_NOW,
                                 now_revenue_start=START_NOW)
        out = compare_peer_cash_conversion(
            _packet(target, altered), target_source=target, peer_sources=altered)
        audit = out["period_comparability"]
        self.assertEqual(audit["current_status"],
                         "CROSS_ISSUER_CURRENT_WINDOW_MISMATCH")
        self.assertTrue(audit["coverage"][1]["current_revenue_cash_window_match"])
        self.assertFalse(audit["current_cash_median_eligible"])
        self.assertEqual(out["status"], "PERIOD_WINDOW_COMPARISON_WITHHELD")
        self.assertEqual(out["eligible_peer_count"], 1)
        self.assertIsNone(out["cash_conversion_target_pct"])

    def test_prior_year_different_cash_start_suppresses_only_trend(self):
        _, target, peers = extend_with_prior()
        altered = _modified_peer(target, peers, prior_cash_start=START_PRIOR)
        out = compare_peer_cash_conversion(
            _packet(target, altered), target_source=target, peer_sources=altered)
        self.assertEqual(out["status"],
                         "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(out["cash_conversion_peer_median_pct"], "50.00")
        self.assertEqual(out["period_comparability"]["two_year_status"],
                         "CASH_REVENUE_PRIOR_WINDOW_MISMATCH")
        self.assertEqual(out["two_year_trend_status"],
                         "PERIOD_WINDOW_TWO_YEAR_COMPARISON_WITHHELD")
        self.assertIsNone(out["two_year_target_change_pp"])

    def test_same_peer_prior_year_window_differs_from_target(self):
        _, target, peers = extend_with_prior()
        altered = _modified_peer(target, peers,
                                 prior_cash_start=START_PRIOR,
                                 prior_revenue_start=START_PRIOR)
        out = compare_peer_cash_conversion(
            _packet(target, altered), target_source=target, peer_sources=altered)
        self.assertEqual(out["period_comparability"]["two_year_status"],
                         "CROSS_ISSUER_PRIOR_WINDOW_MISMATCH")
        self.assertEqual(out["cash_conversion_target_pct"], "33.33")
        self.assertIsNone(out["two_year_target_minus_peer_change_pp"])

    def test_different_revenue_tag_is_visible_but_not_automatically_fraud(self):
        _, target, peers = extend_with_prior()
        altered = _modified_peer(target, peers, revenue_tag="Revenues")
        out = compare_peer_cash_conversion(
            _packet(target, altered), target_source=target, peer_sources=altered)
        audit = out["period_comparability"]
        self.assertEqual(audit["revenue_concept_status"],
                         "DIFFERENT_US_GAAP_REVENUE_TAGS_REVIEW_REQUIRED")
        self.assertEqual(audit["revenue_concepts"],
                         ["RevenueFromContractWithCustomerExcludingAssessedTax",
                          "Revenues"])
        self.assertEqual(out["status"],
                         "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(out["two_year_trend_status"],
                         "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertIs(out["cross_issuer_accounting_policy_verified"], False)
        self.assertIs(audit["original_source_authenticated"], False)

    def test_missing_current_and_prior_reason_coverage_remains_visible(self):
        packet, target, peers = prepared(remove_peer_cfo=True)
        out = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        audit = out["period_comparability"]
        self.assertEqual(audit["current_status"],
                         "INCOMPLETE_CURRENT_ACCOUNTING_EVIDENCE")
        self.assertEqual(audit["two_year_status"],
                         "CURRENT_WINDOW_BLOCKS_TREND_COMPARISON")
        self.assertEqual(audit["missing_current_count"], 1)
        self.assertEqual(audit["missing_two_year_count"], 2)
        self.assertFalse(audit["current_cash_median_eligible"])
        self.assertEqual(audit["coverage"][1]["withheld_reason"],
                         "CURRENT_ACCOUNTING_UNAVAILABLE")
        self.assertIsNone(out["cash_conversion_target_pct"])

    def test_untrusted_row_flags_bad_sha_and_forged_period_refused(self):
        packet, target, peers = extend_with_prior()
        full = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        original = full["rows"]
        args = {"prior_end": "2024-09-30", "current_end": "2025-09-30"}
        for patch_type, value in (
            ("auth", True),
            ("sha", "0" * 64),
            ("current", "NOT-A-DATE"),
        ):
            mutated = deepcopy(original)
            if patch_type == "auth":
                mutated[1]["source_authenticated"] = value
            elif patch_type == "sha":
                mutated[1]["companyfacts_sha256"] = value
            else:
                mutated[1]["revenue_period_starts"][1] = value
            with self.subTest(kind=patch_type), self.assertRaisesRegex(
                    ValueError, "PEER_PERIOD_"):
                assess_peer_period_comparability(mutated, **args)


if __name__ == "__main__":
    unittest.main()
