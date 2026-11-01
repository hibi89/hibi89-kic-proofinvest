"""P92: two-year trend only when all declared peer and target facts exist.

All data are generated synthetic SEC-shaped filings, no real issuer facts.
"""
from __future__ import annotations

from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.peer_cash_conversion import compare_peer_cash_conversion
from proofinvest.peer_cash_trend import review_two_year_cash_conversion
from tests.test_peer_cash_conversion import prepared, NI, CFO
from tests.test_industry_packet_builder import build

PRIOR_START = "2023-10-01"
PRIOR_END = "2024-09-30"
CURRENT_END = "2025-09-30"
FILED = "2025-10-15"


def extend_with_prior(*, with_peer=True, two_peers=False,
                      prior_ni=50, prior_cfo=50,
                      peer_prior_ni=80, peer_prior_cfo=20,
                      peer_prior_file_date=FILED):
    """Rebuild an Engine C packet so modified source byte hashes are exact."""
    _, target, peers = prepared(extra_peer=two_peers)
    amounts = [(prior_ni, prior_cfo)] + [
        (peer_prior_ni, peer_prior_cfo) if i == 0 else (80, 40)
        for i in range(len(peers))
    ]
    updated = []
    for i, ((cik, acc, raw), (income, cash)) in enumerate(zip(
            [target, *peers], amounts)):
        obj = json.loads(raw)
        if i == 0 or with_peer:
            for tag, value in ((NI, income), (CFO, cash)):
                row = {
                    "accn": acc, "form": "10-K",
                    "start": PRIOR_START, "end": PRIOR_END,
                    "filed": peer_prior_file_date if i == 1 else FILED,
                    "val": value,
                }
                obj["facts"]["us-gaap"][tag]["units"]["USD"].append(row)
        updated.append((cik, acc, json.dumps(obj, sort_keys=True).encode()))
    tgt, peer_rows = updated[0], updated[1:]
    packet = build(
        tgt[2], peer_rows[0][2],
        target=(tgt[0], tgt[1], "SYNTHETIC_TARGET", tgt[2]),
        peers=[(cik, acc, "SYNTHETIC_PEER_" + str(i), raw)
               for i, (cik, acc, raw) in enumerate(peer_rows, 1)],
    )
    return packet, tgt, peer_rows


class PeerCashTrendTests(unittest.TestCase):
    def test_same_10k_two_year_cash_conversion_and_peer_gap(self):
        packet, target, peers = extend_with_prior()
        initial_hashes = [sha256(x[2]).hexdigest() for x in [target, *peers]]
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK")) as http:
            report = compare_peer_cash_conversion(
                packet, target_source=target, peer_sources=peers)
        http.assert_not_called()
        self.assertEqual(report["status"],
                         "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(report["two_year_trend_status"],
                         "COMPLETE_TWO_YEAR_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(report["two_year_eligible_peer_count"], 1)
        self.assertEqual(report["cash_conversion_target_pct"], "33.33")
        self.assertEqual(report["cash_conversion_peer_median_pct"], "50.00")
        self.assertEqual(report["two_year_target_change_pp"], "-66.67")
        self.assertEqual(report["two_year_peer_median_change_pp"], "25.00")
        self.assertEqual(report["two_year_target_minus_peer_change_pp"], "-91.67")
        self.assertEqual(report["rows"][0]["cash_conversion_trend"][
            "prior_conversion_pct"], "100.00")
        self.assertEqual(report["rows"][1]["cash_conversion_trend"][
            "prior_conversion_pct"], "25.00")
        self.assertEqual(report["rows"][1]["cash_conversion_trend"][
            "current_conversion_pct"], "50.00")
        self.assertEqual(initial_hashes, [sha256(x[2]).hexdigest()
                                          for x in [target, *peers]])
        for field in ("issuer_source_authenticated", "audit_written",
                      "data_rights_verified", "accounting_fraud_proven",
                      "point_in_time_verified", "guard_policy_modified",
                      "trade_executed", "ai_generated"):
            self.assertIs(report[field], False)
        self.assertEqual(json.loads(json.dumps(report)), report)

    def test_two_peers_median_of_year_over_year_changes(self):
        packet, target, peers = extend_with_prior(two_peers=True)
        result = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertEqual(result["peer_count"], 2)
        self.assertEqual(result["two_year_eligible_peer_count"], 2)
        self.assertEqual(result["two_year_peer_median_change_pp"], "37.50")
        self.assertEqual(result["two_year_target_minus_peer_change_pp"], "-104.17")
        self.assertEqual(
            [r["cash_conversion_trend"]["change_pp"] for r in result["rows"]],
            ["-66.67", "25.00", "50.00"])

    def test_missing_prior_peer_withholds_only_trend_not_current_comparison(self):
        packet, target, peers = extend_with_prior(with_peer=False)
        out = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertEqual(out["status"],
                         "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(out["cash_conversion_target_pct"], "33.33")
        self.assertEqual(out["cash_conversion_peer_median_pct"], "50.00")
        self.assertEqual(out["two_year_trend_status"],
                         "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD")
        self.assertEqual(out["two_year_eligible_peer_count"], 0)
        self.assertIsNone(out["two_year_target_change_pp"])
        self.assertIsNone(out["two_year_peer_median_change_pp"])
        self.assertIsNone(out["two_year_target_minus_peer_change_pp"])
        self.assertEqual(out["rows"][0]["cash_conversion_trend"][
            "status"], "TWO_YEAR_LOCAL_COMPARISON_ORIGIN_UNVERIFIED")
        self.assertEqual(out["rows"][1]["cash_conversion_trend"][
            "reason_code"], "PRIOR_CASH_OR_EARNINGS_MISSING_OR_CONFLICT")

    def test_zero_prior_income_and_negative_prior_cashflow(self):
        packet, target, peers = extend_with_prior(prior_ni=0)
        out = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertIsNone(out["two_year_target_minus_peer_change_pp"])
        self.assertEqual(out["rows"][0]["cash_conversion_trend"][
            "reason_code"], "PRIOR_NON_POSITIVE_NET_INCOME")
        packet, target, peers = extend_with_prior(prior_cfo=-10)
        out = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertEqual(out["rows"][0]["cash_conversion_trend"][
            "prior_conversion_pct"], "-20.00")
        self.assertEqual(out["rows"][0]["cash_conversion_trend"][
            "change_pp"], "53.33")

    def test_mismatched_filing_date_withheld_not_false_success(self):
        packet, target, peers = extend_with_prior(
            peer_prior_file_date="2025-10-14")
        out = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertEqual(out["status"],
                         "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(out["two_year_trend_status"],
                         "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD")
        self.assertEqual(out["rows"][1]["cash_conversion_trend"][
            "reason_code"], "PRIOR_PERIOD_OR_FILING_DATE_CONFLICT")

    def test_reject_forged_selected_period_and_historical_bytes(self):
        packet, target, peers = extend_with_prior()
        normal = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        wrong = json.loads(target[2])
        wrong["facts"]["us-gaap"][NI]["units"]["USD"][-1]["val"] = 999
        modified = json.dumps(wrong, sort_keys=True).encode()
        with self.assertRaisesRegex(ValueError, "PEER_CASH_TARGET_SOURCE_PIN_CONFLICT"):
            compare_peer_cash_conversion(
                packet, target_source=(target[0], target[1], modified),
                peer_sources=peers)
        accounting = normal["rows"][0]["cash_conversion_trend"]
        self.assertTrue(accounting["same_accession_and_filing_date_checked"])
        # The low-level verifier rejects a detached current accounting result.
        fake_review = {
            "schema": "kuodra.accounting-integrity-offline.v1",
            "companyfacts_sha256": sha256(target[2]).hexdigest(),
            "status": "reviewed_unverified", "period_end": CURRENT_END,
            "filing_date": FILED, "cash_to_net_income_pct": "90.00",
            "operating_cashflow_usd": "20", "net_income_usd": "60",
            "source_authenticated": False, "accounting_fraud_proven": False,
            "guard_policy_modified": False, "ai_generated": False,
            "trade_executed": False, "live_api_called": False,
        }
        with self.assertRaisesRegex(ValueError, "PEER_TREND_CURRENT_FACT_CONFLICT"):
            review_two_year_cash_conversion(
                target[2], cik=target[0], accession=target[1],
                prior_end=PRIOR_END, current_end=CURRENT_END,
                as_of="2025-10-16", accounting=fake_review,
                expected_filing_date=FILED)

    def test_missing_current_income_preserves_no_trend_not_healthy(self):
        packet, target, peers = prepared(target_income=0)
        result = compare_peer_cash_conversion(
            packet, target_source=target, peer_sources=peers)
        self.assertEqual(result["two_year_trend_status"],
                         "INCOMPLETE_TWO_YEAR_CASH_EVIDENCE_WITHHELD")
        self.assertIsNone(result["two_year_target_change_pp"])
        self.assertEqual(result["rows"][0]["cash_conversion_trend"][
            "reason_code"], "CURRENT_NON_POSITIVE_NET_INCOME")


if __name__ == "__main__":
    unittest.main()
