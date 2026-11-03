"""P168: redacted input-rights gap report bound to real original local bytes."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.ticker_source_clearance_packet import (
    build_source_clearance_packet, inspect_source_clearance_packet,
)
from tests.test_ticker_offline_review_builder import payload


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _review():
    args = payload()
    output = build_offline_initial_review(**args)
    assert output["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED", output
    return args, output


class SourceClearanceReportTests(unittest.TestCase):
    def test_first_packet_includes_downloadable_rights_gap_report_with_zero_calls(self):
        with (
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("SEC_NETWORK_FORBIDDEN")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("PROVIDER_NETWORK_FORBIDDEN")) as http,
        ):
            args, output = _review()
        sec.assert_not_called()
        http.assert_not_called()
        report = output["source_clearance_report"]
        self.assertLessEqual(len(report), 9216)
        self.assertNotIn(b"close_observations", report)
        self.assertNotIn(b"Time Series (Daily)", report)
        self.assertNotIn(b"<html", report.lower())
        self.assertEqual(
            inspect_source_clearance_packet(report, review_packet=output["review_packet"])["status"],
            "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING",
        )
        parsed = json.loads(report)
        self.assertEqual(parsed["issuer"]["ticker"], "NVDA")
        self.assertEqual(parsed["market_window"]["benchmark"], "NASDAQ_100")
        self.assertEqual(parsed["market_window"]["index_symbol"], "NDX")
        self.assertEqual(parsed["market_window"]["matched_sessions"], 65)
        self.assertEqual(parsed["guard_policy_preview"], "HOLD")
        self.assertEqual(parsed["packet_sha256"], sha256(output["review_packet"]).hexdigest())
        self.assertEqual(len(parsed["files"]), 8)
        self.assertTrue(all(card["sha256"] for card in parsed["files"]))
        self.assertTrue(all(card["publisher_origin_authenticated"] is False
                            for card in parsed["files"]))
        self.assertGreaterEqual(len(parsed["unresolved_clearances"]), 5)
        for flag in ("source_authenticated", "source_rights_verified",
                     "external_sharing_allowed", "commercial_reuse_allowed",
                     "contest_submission_approved", "trade_executed"):
            self.assertIs(parsed[flag], False)
        self.assertEqual(parsed["network_requests"], 0)
        self.assertEqual(parsed["paid_requests"], 0)

    def test_same_originals_yield_same_clearance_bytes(self):
        args, a = _review()
        b = build_offline_initial_review(**args)
        self.assertEqual(a["review_packet"], b["review_packet"])
        self.assertEqual(a["source_clearance_report"], b["source_clearance_report"])

    def test_wrong_original_even_with_valid_packet_blocks_gap_receipt(self):
        args, output = _review()
        for key in ("stock_raw", "index_raw", "market_json", "industry_json"):
            changed = dict(args, **{key: args[key] + b" "})
            with self.subTest(role=key), self.assertRaises(ValueError):
                build_source_clearance_packet(
                    packet=output["review_packet"], sources=changed["sources"],
                    stock_raw=changed["stock_raw"], index_raw=changed["index_raw"],
                    market_json=changed["market_json"],
                    industry_json=changed["industry_json"],
                )
        changed_sources = dict(args["sources"], companyfacts=args["sources"]["companyfacts"] + b" ")
        with self.assertRaises(ValueError):
            build_source_clearance_packet(
                packet=output["review_packet"], sources=changed_sources,
                stock_raw=args["stock_raw"], index_raw=args["index_raw"],
                market_json=args["market_json"], industry_json=args["industry_json"],
            )

    def test_no_report_can_promote_verified_rights_even_after_resigning_digest(self):
        _, output = _review()
        packet = output["review_packet"]
        original = json.loads(output["source_clearance_report"])
        cases = [
            lambda x: x.__setitem__("source_rights_verified", True),
            lambda x: x.__setitem__("external_sharing_allowed", True),
            lambda x: x["files"][5].__setitem__("redistribution_rights_verified", True),
            lambda x: x["files"][5].__setitem__("sha256", "f" * 64),
            lambda x: x["issuer"].__setitem__("ticker", "AAPL"),
            lambda x: x["market_window"].__setitem__("matched_sessions", 31),
            lambda x: x.__setitem__("unresolved_clearances", []),
            lambda x: x.__setitem__("raw_provider_response", "SECRET"),
        ]
        for mutation in cases:
            modified = deepcopy(original)
            mutation(modified)
            modified.pop("receipt_sha256")
            modified["receipt_sha256"] = sha256(_canonical(modified)).hexdigest()
            with self.subTest(changed=modified), self.assertRaises(ValueError):
                inspect_source_clearance_packet(
                    _canonical(modified), review_packet=packet,
                )

    def test_changed_packet_or_trailing_bytes_does_not_pass_inspector(self):
        _, output = _review()
        packet = output["review_packet"]
        report = output["source_clearance_report"]
        with self.assertRaises(ValueError):
            inspect_source_clearance_packet(report + b" ", review_packet=packet)
        with self.assertRaises(ValueError):
            inspect_source_clearance_packet(report, review_packet=packet + b" ")
        with self.assertRaises(ValueError):
            inspect_source_clearance_packet(b'{"schema":"bad"}\n', review_packet=packet)

    def test_optional_absent_files_explicitly_marked_not_verified(self):
        args = payload()
        args["market_json"] = None
        args["industry_json"] = None
        generated = build_offline_initial_review(**args)
        self.assertEqual(generated["status"], "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED", generated)
        receipt = json.loads(generated["source_clearance_report"])
        for card in receipt["files"][-2:]:
            self.assertIsNone(card["sha256"])
            self.assertEqual(card["bytes"], 0)
            self.assertEqual(card["input_state"], "OPTIONAL_SOURCE_NOT_BOUND")
            self.assertIs(card["source_use_rights_verified"], False)


if __name__ == "__main__":
    unittest.main()
