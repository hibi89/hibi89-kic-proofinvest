"""Offline full/partial peer cash conversion with synthetic SEC-shaped files.

No actual SEC issuer, provider calls, original network snapshots or investment
decisions. Existing revenue binding must pass before accounting comparison.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.peer_cash_conversion import compare_peer_cash_conversion
from tests.test_industry_packet_builder import build
from tests.test_real_data_preflight_peer_companyfacts import setup_peer, CIK, ACC
from tests.test_accounting_integrity import fixture as accounting_fixture
from proofinvest.kic_dl_demo import SYNTHETIC_CIK, SYNTHETIC_ACCESSION

NI = "NetIncomeLoss"
CFO = "NetCashProvidedByUsedInOperatingActivities"


def annual(value: int, accession: str) -> dict:
    return {"accn": accession, "form": "10-K",
            "start": "2024-10-01", "end": "2025-09-30",
            "filed": "2025-10-15", "val": value}


def prepared(*, target_income=60, target_cash=20,
             peer_income=80, peer_cash=40, extra_peer=False,
             remove_peer_cfo=False):
    """Create checked industry and two raw CompanyFacts from known test data."""
    with TemporaryDirectory() as tmp:
        _, _, _, peer_file = setup_peer(Path(tmp))
        peer = json.loads(peer_file.read_bytes())
    gaap = peer["facts"]["us-gaap"]
    gaap[NI] = {"units": {"USD": [annual(peer_income, ACC)]}}
    if not remove_peer_cfo:
        gaap[CFO] = {"units": {"USD": [annual(peer_cash, ACC)]}}
    raw_peer = json.dumps(peer, sort_keys=True).encode()
    raw_target = json.dumps(accounting_fixture(
        ni=target_income, cfo=target_cash
    ), sort_keys=True).encode()
    sources = [(CIK, ACC, raw_peer)]
    if extra_peer:
        second = deepcopy(peer)
        second["cik"] = 8
        extra_acc = "0000000008-25-000001"
        for tag in second["facts"]["us-gaap"].values():
            for unit_rows in tag["units"].values():
                for row in unit_rows:
                    row["accn"] = extra_acc
        second["facts"]["us-gaap"][NI]["units"]["USD"][0]["val"] = 80
        second["facts"]["us-gaap"][CFO]["units"]["USD"][0]["val"] = 80
        sources.append(("0000000008", extra_acc,
                        json.dumps(second, sort_keys=True).encode()))
    options = {
        "target": (SYNTHETIC_CIK, SYNTHETIC_ACCESSION, "SYNTHETIC_TARGET",
                   raw_target),
        "peers": [
            (cik, acc, "SYNTHETIC_PEER_" + str(i), raw)
            for i, (cik, acc, raw) in enumerate(sources, 1)
        ],
    }
    packet = build(raw_target, raw_peer, **options)
    return packet, (SYNTHETIC_CIK, SYNTHETIC_ACCESSION, raw_target), sources


class PeerCashConversionTests(unittest.TestCase):
    def test_one_peer_full_comparison_hash_and_no_http(self):
        packet, target, peers = prepared()
        before = [sha256(x[2]).hexdigest() for x in [target, *peers]]
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("EXTERNAL_HTTP_FORBIDDEN")) as http:
            out = compare_peer_cash_conversion(packet,
                                                target_source=target,
                                                peer_sources=peers)
        http.assert_not_called()
        self.assertEqual(out["status"], "COMPLETE_LOCAL_INPUTS_ORIGIN_UNVERIFIED")
        self.assertEqual(out["issuer_cik"], SYNTHETIC_CIK)
        self.assertEqual(out["peer_count"], 1)
        self.assertEqual(out["eligible_peer_count"], 1)
        self.assertEqual(out["cash_conversion_target_pct"], "33.33")
        self.assertEqual(out["cash_conversion_peer_median_pct"], "50.00")
        self.assertEqual(out["target_minus_peer_median_pp"], "-16.67")
        self.assertEqual([x["revenue_growth_pct_from_source"] for x in out["rows"]],
                         ["100.00", "30.00"])
        self.assertEqual(out["rows"][0]["cash_conversion_pct"], "33.33")
        self.assertEqual(out["rows"][1]["cash_conversion_pct"], "50.00")
        self.assertEqual(out["rows"][0]["working_capital_signals"],
                         ["RECEIVABLES_OUTPACED_REVENUE"])
        self.assertEqual([x["companyfacts_sha256"] for x in out["rows"]], before)
        self.assertEqual(before, [sha256(x[2]).hexdigest()
                                  for x in [target, *peers]])
        self.assertFalse(any(out[key] for key in (
            "issuer_source_authenticated", "data_rights_verified",
            "point_in_time_verified", "cross_issuer_accounting_policy_verified",
            "accounting_fraud_proven", "guard_policy_modified",
            "audit_written", "live_sec_called", "ai_generated", "trade_executed",
        )))
        self.assertEqual(out, json.loads(json.dumps(out, allow_nan=False)))

    def test_two_peers_true_decimal_median_not_one_peer(self):
        packet, target, peers = prepared(extra_peer=True)
        result = compare_peer_cash_conversion(packet, target_source=target,
                                              peer_sources=peers)
        self.assertEqual(result["peer_count"], 2)
        self.assertEqual(result["eligible_peer_count"], 2)
        self.assertEqual(result["cash_conversion_peer_median_pct"], "75.00")
        self.assertEqual(result["target_minus_peer_median_pp"], "-41.67")
        self.assertEqual([x["cash_conversion_pct"] for x in result["rows"][1:]],
                         ["50.00", "100.00"])

    def test_missing_peer_cash_suppresses_all_median_and_not_healthy(self):
        packet, target, peers = prepared(remove_peer_cfo=True)
        out = compare_peer_cash_conversion(packet,
                                           target_source=target, peer_sources=peers)
        self.assertEqual(out["status"],
                         "INCOMPLETE_ACCOUNTING_METRICS_COMPARISON_WITHHELD")
        self.assertEqual(out["eligible_peer_count"], 0)
        self.assertIsNone(out["cash_conversion_target_pct"])
        self.assertIsNone(out["cash_conversion_peer_median_pct"])
        self.assertIsNone(out["target_minus_peer_median_pp"])
        self.assertEqual(out["rows"][1]["accounting_status"], "unavailable")
        self.assertIsNone(out["rows"][1]["cash_conversion_pct"])

    def test_zero_target_income_cannot_be_in_median(self):
        packet, target, peers = prepared(target_income=0)
        out = compare_peer_cash_conversion(packet, target_source=target,
                                           peer_sources=peers)
        self.assertEqual(out["eligible_peer_count"], 1)
        self.assertIsNone(out["cash_conversion_target_pct"])
        self.assertIsNone(out["target_minus_peer_median_pp"])
        self.assertEqual(out["rows"][0]["earnings_cash_signal"],
                         "NON_POSITIVE_NET_INCOME_RATIO_UNDEFINED")

    def test_wrong_target_file_or_forged_revenue_hash_rejected(self):
        packet, target, peers = prepared()
        obj = json.loads(target[2])
        obj["facts"]["us-gaap"][NI]["units"]["USD"][0]["val"] = 999
        altered = json.dumps(obj, sort_keys=True).encode()
        with self.assertRaisesRegex(ValueError, "PEER_CASH_TARGET_SOURCE_PIN_CONFLICT"):
            compare_peer_cash_conversion(
                packet,
                target_source=(target[0], target[1], altered),
                peer_sources=peers)
        forged = json.loads(packet)
        forged["target"]["current_revenue_usd"] = "500"
        with self.assertRaisesRegex(ValueError, "PEER_CASH_TARGET_REVENUE_CONFLICT"):
            compare_peer_cash_conversion(
                json.dumps(forged).encode(), target_source=target,
                peer_sources=peers)

    def test_peer_source_binding_identity_and_stale_upload_refused(self):
        packet, target, peers = prepared()
        with self.assertRaises(ValueError):
            compare_peer_cash_conversion(
                packet, target_source=target,
                peer_sources=[(peers[0][0], peers[0][1],
                               peers[0][2] + b" ")])
        with self.assertRaises(ValueError):
            compare_peer_cash_conversion(
                packet, target_source=(peers[0][0], target[1], target[2]),
                peer_sources=peers)
        with self.assertRaises(ValueError):
            compare_peer_cash_conversion(
                packet, target_source=target, peer_sources=peers * 2)
        with self.assertRaises(ValueError):
            compare_peer_cash_conversion(
                packet, target_source=target, peer_sources=[])


if __name__ == "__main__":
    unittest.main()
