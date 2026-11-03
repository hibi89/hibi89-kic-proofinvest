"""P166 real local packet reconstruction: exact source bytes + A/B/C math."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch
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


class SourceReplayUiTests(unittest.TestCase):
    @staticmethod
    def render(args, *, clicked, include_mode=True):
        import os
        from unittest.mock import patch
        from proofinvest import ticker_research_ui as ui
        from tests.test_ticker_research_ui import FakeSt, Uploaded
        uploads = {
            "kuodra_p164_packet_file": Uploaded(args["raw_packet"]),
            "kuodra_p166_stock": Uploaded(args["stock_raw"]),
            "kuodra_p166_index": Uploaded(args["index_raw"]),
            "kuodra_p166_market": Uploaded(args["market_json"]),
            "kuodra_p166_industry": Uploaded(args["industry_json"]),
        }
        for key, value in args["sources"].items():
            uploads["kuodra_p166_" + key] = Uploaded(value)
        st = FakeSt(
            clicked=clicked,
            checks={"kuodra_p166_replay_mode": include_mode},
            uploads=uploads,
            values={"kuodra_p100_ticker": "NVDA",
                    "kuodra_p100_as_of": "2026-02-01"},
        )
        with (
            patch.dict(os.environ,
                       {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}, clear=True),
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NO_SEC_NET")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO_VENDOR_NET")) as vendor,
        ):
            ui.render_single_ticker_search(st)
        sec.assert_not_called()
        vendor.assert_not_called()
        return st

    def test_real_review_ui_reports_original_source_replay_without_authenticating(self):
        st = self.render(
            original_case(),
            clicked="원본 SEC + 주가·NDX A/B/C 독립 재계산 (네트워크 없음)",
        )
        self.assertTrue(any(
            kind == "success" and
            "원본 6종 해시 + SEC/Engine A/B/C 산술 재계산 PASS" in value
            for kind, value in st.messages
        ), st.messages)
        matched = [v for k, v in st.messages if k == "json"
                   and type(v) is dict
                   and v.get("local_source_replay_verified") is True]
        self.assertEqual(len(matched), 1, st.messages)
        self.assertTrue(matched[0]["market_math_recomputed"])
        self.assertEqual(matched[0]["guard_policy_preview"], "HOLD")
        self.assertFalse(matched[0]["source_rights_verified"])
        self.assertFalse(matched[0]["source_authenticated"])
        self.assertEqual(matched[0]["network_requests"], 0)
        self.assertNotIn("close_observations", repr(matched))

    def test_ui_rejects_changed_original_without_previous_pass(self):
        args = original_case()
        args["sources"] = dict(
            args["sources"], companyfacts=args["sources"]["companyfacts"] + b" ")
        st = self.render(
            args, clicked="원본 SEC + 주가·NDX A/B/C 독립 재계산 (네트워크 없음)",
        )
        self.assertTrue(any(k == "code" and v == "EXACT_ORIGINAL_BYTES_HASH_MISMATCH"
                            for k, v in st.messages), st.messages)
        self.assertFalse(any(k == "success" and "원본 6종 해시" in v
                             for k, v in st.messages))

    def test_passive_upload_only_or_closed_mode_does_not_run_replay(self):
        args = original_case()
        with patch(
            "proofinvest.ticker_review_source_replay.replay_review_packet_from_original_bytes",
            side_effect=AssertionError("NO_PASSIVE_OR_CLOSED_REPLAY"),
        ) as replay:
            for clicked, enabled in ((None, True), (None, False)):
                st = self.render(args, clicked=clicked, include_mode=enabled)
                self.assertFalse(any(
                    k == "success" and "원본 6종" in v
                    for k, v in st.messages))
        replay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
