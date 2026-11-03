"""P166 real local packet reconstruction: exact source bytes + A/B/C math."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_review_packet import build_review_packet, review_packet_json_bytes
from proofinvest.ticker_review_source_replay import replay_review_packet_from_original_bytes
from tests.test_ticker_market_pair_evidence import _build, _prepared, _body


def original_case():
    prepared = _prepared()
    workflow, sources, market, industry, stock, index = prepared
    return {
        "raw_packet": review_packet_json_bytes(build_review_packet(_build(prepared))),
        "sources": sources, "stock_raw": _body("NVDA"),
        "index_raw": _body("NDX", 10000),
        "market_json": market, "industry_json": industry,
    }


class DownloadedPacketSourceReplayTests(unittest.TestCase):
    def test_complete_independent_source_and_math_replay_local_only(self):
        args = original_case()
        with patch(
            "proofinvest.ticker_sec_transport._open_once",
            side_effect=AssertionError("SEC_HTTP_FORBIDDEN"),
        ) as sec, patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("VENDOR_HTTP_FORBIDDEN"),
        ) as provider:
            result = replay_review_packet_from_original_bytes(**args)
        sec.assert_not_called()
        provider.assert_not_called()
        self.assertEqual(result["status"], "PASS_UNVERIFIED_ORIGIN", result)
        self.assertEqual(result["reason_code"], "EXACT_ORIGINALS_AND_MATH_RECOMPUTED")
        self.assertEqual(result["ticker"], "NVDA")
        for field in ("packet_internal_integrity_passed",
                      "original_byte_hashes_matched",
                      "local_source_replay_verified",
                      "market_math_recomputed"):
            self.assertIs(result[field], True, field)
        for field in ("source_authenticated", "source_rights_verified",
                      "market_vintage_authenticated", "external_sharing_allowed",
                      "guard_executed", "ai_agent_executed", "trade_executed"):
            self.assertIs(result[field], False, field)
        self.assertEqual(result["network_requests"], 0)
        self.assertNotIn("close_observations", repr(result))

    def test_exact_original_sec_filing_and_price_bytes_must_match(self):
        args = original_case()
        for role in ("ticker_map", "submissions", "companyfacts", "original_10k"):
            modified = dict(args)
            modified["sources"] = dict(args["sources"], **{
                role: args["sources"][role] + b" "
            })
            with self.subTest(role=role):
                value = replay_review_packet_from_original_bytes(**modified)
                self.assertEqual(value["status"], "FAIL")
                self.assertEqual(value["reason_code"], "EXACT_ORIGINAL_BYTES_HASH_MISMATCH")
                self.assertFalse(value["original_byte_hashes_matched"])
        for role in ("stock_raw", "index_raw", "market_json", "industry_json"):
            modified = dict(args)
            modified[role] = args[role] + b" "
            with self.subTest(role=role):
                value = replay_review_packet_from_original_bytes(**modified)
                self.assertEqual(value["reason_code"], "EXACT_ORIGINAL_BYTES_HASH_MISMATCH")
                self.assertFalse(value["original_byte_hashes_matched"])

    def test_missing_optional_source_never_passes(self):
        args = original_case()
        for role in ("market_json", "industry_json"):
            modified = dict(args, **{role: None})
            with self.subTest(role=role):
                verdict = replay_review_packet_from_original_bytes(**modified)
                self.assertEqual(verdict["status"], "FAIL")
                self.assertEqual(verdict["reason_code"], "OPTIONAL_SOURCE_COVERAGE_MISMATCH")

    def test_internal_packet_tampering_fails_before_full_replay(self):
        args = original_case()
        args["raw_packet"] += b" "
        verdict = replay_review_packet_from_original_bytes(**args)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertFalse(verdict["packet_internal_integrity_passed"])
        self.assertFalse(verdict["original_byte_hashes_matched"])

    def test_wrong_price_or_ndx_symbol_cannot_pass_with_rehashed_packet(self):
        args = original_case()
        for role, symbol, price in (
            ("stock_raw", "WRONG", 100),
            ("index_raw", "SPX", 10000),
        ):
            changed = dict(args, **{role: _body(symbol, price)})
            with self.subTest(role=role):
                verdict = replay_review_packet_from_original_bytes(**changed)
                self.assertEqual(verdict["status"], "FAIL")
                self.assertFalse(verdict["market_math_recomputed"])

    def test_input_type_and_size_fail_closed(self):
        args = original_case()
        for change in (
            {"raw_packet": args["raw_packet"] * 2},
            {"sources": dict(args["sources"], companyfacts="NOT_BYTES")},
            {"stock_raw": b"x" * 262145},
            {"index_raw": b"x" * 8388609},
            {"market_json": b"x" * 131073},
            {"industry_json": b"x" * 65537},
        ):
            with self.subTest(keys=list(change)):
                verdict = replay_review_packet_from_original_bytes(
                    **dict(args, **change))
                self.assertEqual(verdict["status"], "FAIL")
                self.assertFalse(verdict["local_source_replay_verified"])
                self.assertEqual(verdict["network_requests"], 0)


if __name__ == "__main__":
    unittest.main()
