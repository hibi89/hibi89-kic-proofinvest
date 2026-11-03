"""P167 first-initial local review packet: no paid GET or prior packet required."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.ticker_review_packet import inspect_review_packet_bytes
from proofinvest.ticker_review_source_replay import replay_review_packet_from_original_bytes
from tests.test_ticker_market_pair_evidence import _body, _prepared


def payload():
    workflow, sources, market, industry, _stock, _index = _prepared()
    return dict(
        ticker="NVDA", as_of="2026-02-01",
        sources=sources, market_json=market, industry_json=industry,
        stock_raw=_body("NVDA"), index_raw=_body("NDX", 10000),
    )


class InitialOfflineReviewBuilderTests(unittest.TestCase):
    def test_initial_packet_generated_and_replayed_without_any_approved_provider(self):
        p = payload()
        with (
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NO_SEC_GET")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO_PAID_GET")) as vendor,
        ):
            result = build_offline_initial_review(**p)
        sec.assert_not_called()
        vendor.assert_not_called()
        self.assertEqual(result["status"], "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED", result)
        self.assertTrue(result["local_replay_verified"])
        self.assertTrue(result["market_math_recomputed"])
        self.assertEqual(result["matched_sessions"], 65)
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        for field in ("source_authenticated", "source_rights_verified",
                      "market_vintage_authenticated", "external_sharing_allowed",
                      "guard_executed", "ai_agent_executed", "trade_executed"):
            self.assertFalse(result[field])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["paid_requests"], 0)
        packet_bytes = result["review_packet"]
        self.assertLessEqual(len(packet_bytes), 28672)
        self.assertNotIn(b"close_observations", packet_bytes)
        self.assertNotIn(b"<html", packet_bytes.lower())
        self.assertEqual(
            inspect_review_packet_bytes(packet_bytes)["status"],
            "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED",
        )
        again = replay_review_packet_from_original_bytes(
            packet_bytes, sources=p["sources"],
            stock_raw=p["stock_raw"], index_raw=p["index_raw"],
            market_json=p["market_json"], industry_json=p["industry_json"],
        )
        self.assertEqual(again["status"], "PASS_UNVERIFIED_ORIGIN", again)

    def test_same_sources_reproduce_identical_immutable_packet(self):
        p = payload()
        a = build_offline_initial_review(**p)
        b = build_offline_initial_review(**p)
        self.assertEqual(a["review_packet"], b["review_packet"])
        self.assertEqual(a["accession"], b["accession"])

    def test_wrong_issuer_index_and_future_asof_block(self):
        p = payload()
        for changes in (
            {"ticker": "AAPL"},
            {"index_raw": _body("SPX", 10000)},
            {"stock_raw": _body("AAPL")},
            {"as_of": "2025-11-01"},
            {"as_of": "2035-02-01"},
        ):
            with self.subTest(changes=list(changes)):
                result = build_offline_initial_review(**dict(p, **changes))
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertNotIn("review_packet", result)
                self.assertFalse(result["source_authenticated"])

    def test_missing_or_tampered_required_sources_block(self):
        p = payload()
        for change in (
            {"sources": dict(p["sources"], original_10k=b"x")},
            {"sources": dict(p["sources"], companyfacts=b"{}")},
            {"sources": dict(p["sources"], ticker_map=b"{}")},
            {"sources": dict(p["sources"], submissions=b"{}")},
            {"sources": {}},
            {"stock_raw": b"{}"},
            {"index_raw": b"{}"},
            {"industry_json": b"not valid JSON"},
        ):
            with self.subTest(changes=list(change)):
                result = build_offline_initial_review(**dict(p, **change))
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertNotIn("review_packet", result)

    def test_wrong_types_or_oversized_sources_block_without_disk(self):
        p = payload()
        for change in (
            {"stock_raw": b"x" * 262145},
            {"index_raw": b"x" * 8388609},
            {"market_json": b"x" * 131073},
            {"industry_json": b"x" * 65537},
            {"sources": dict(p["sources"], ticker_map="SECRET")},
            {"stock_raw": None},
        ):
            with self.subTest(changes=list(change)):
                result = build_offline_initial_review(**dict(p, **change))
                self.assertEqual(result["status"], "BLOCKED", result)
                self.assertNotIn("review_packet", result)
                self.assertEqual(result["network_requests"], 0)

    def test_optional_A_C_inputs_absent_are_not_invented(self):
        p = payload()
        p["market_json"] = None
        p["industry_json"] = None
        result = build_offline_initial_review(**p)
        # May be BLOCKED or partially unavailable under strict source policy,
        # but never mark source rights as verified.
        self.assertIs(result["source_rights_verified"], False)
        self.assertIs(result["external_sharing_allowed"], False)
        if result["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED":
            self.assertEqual(
                replay_review_packet_from_original_bytes(
                    result["review_packet"],
                    sources=p["sources"], stock_raw=p["stock_raw"],
                    index_raw=p["index_raw"],
                )["status"], "PASS_UNVERIFIED_ORIGIN",
            )


if __name__ == "__main__":
    unittest.main()
