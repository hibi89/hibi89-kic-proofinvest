"""P164 downloaded A/B/C review packet local reinspection UI regression."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import ticker_research_ui as ui
from proofinvest.ticker_review_packet import (
    build_review_packet, review_packet_json_bytes,
)
from tests.test_ticker_market_pair_evidence import _build, _prepared
from tests.test_ticker_research_ui import FakeSt, Uploaded


_LABEL = "다운로드 패키지 무결성 검사 (네트워크 없음)"


class DownloadedReviewPacketInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = review_packet_json_bytes(build_review_packet(_build(_prepared())))

    def render(self, *, raw=None, clicked=_LABEL):
        st = FakeSt(
            clicked=clicked,
            uploads={"kuodra_p164_packet_file": Uploaded(raw)} if raw is not None else {},
            values={"kuodra_p100_ticker": "NVDA",
                    "kuodra_p100_as_of": "2026-02-01"},
        )
        with (
            patch.dict(os.environ,
                       {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}, clear=True),
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("NETWORK_NOT_ALLOWED")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("VENDOR_NETWORK_NOT_ALLOWED")) as vendor,
        ):
            ui.render_single_ticker_search(st)
        sec.assert_not_called()
        vendor.assert_not_called()
        return st

    def test_downloaded_valid_packet_has_internal_only_result(self):
        st = self.render(raw=self.raw)
        outputs = [value for kind, value in st.messages
                   if kind == "json" and type(value) is dict
                   and value.get("packet_internal_integrity_passed") is True]
        self.assertEqual(len(outputs), 1, st.messages)
        self.assertIn(("success", "검토 패키지 내부 무결성 PASS (원본·공급자 인증 아님)"), st.messages)
        self.assertIn(("metric", ("검사 대상 종목 (미인증)", "NVDA")), st.messages)
        result = outputs[0]
        self.assertEqual(result["status"],
                         "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED")
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        self.assertFalse(result["original_sources_replayed_in_this_check"])
        self.assertFalse(result["market_math_independently_recomputed_in_this_check"])
        for key in ("source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "trade_executed"):
            self.assertFalse(result[key])
        self.assertEqual(result["network_requests"], 0)
        self.assertNotIn("close_observations", repr(outputs))
        self.assertNotIn("raw_vendor_body", repr(outputs))

    def test_tampered_or_oversized_download_is_blocked_without_leaking(self):
        for raw in (self.raw + b" ", b"x" * 28673, b"{}"):
            with self.subTest(size=len(raw)):
                st = self.render(raw=raw)
                self.assertTrue(any(
                    kind == "code" and value == "REVIEW_PACKET_OFFLINE_INTEGRITY_FAILED"
                    for kind, value in st.messages), st.messages)
                self.assertFalse(any(
                    kind == "json" and type(value) is dict
                    and value.get("packet_internal_integrity_passed") is True
                    for kind, value in st.messages))
                self.assertFalse(any(kind == "success" for kind, _ in st.messages))
                self.assertNotIn(repr(raw[:60]), repr(st.messages))

    def test_passive_upload_and_no_upload_never_trigger_validation(self):
        with patch("proofinvest.ticker_review_packet.inspect_review_packet_bytes",
                   side_effect=AssertionError("PASSIVE_REVIEW_FORBIDDEN")) as inspect:
            passive = self.render(raw=self.raw, clicked=None)
            empty = self.render(raw=None, clicked=_LABEL)
        inspect.assert_not_called()
        self.assertFalse(any(
            kind == "json" and type(value) is dict
            and "packet_internal_integrity_passed" in value
            for st in (passive, empty) for kind, value in st.messages))
        self.assertTrue(any(
            label == _LABEL and disabled
            for label, disabled in empty.buttons))


if __name__ == "__main__":
    unittest.main()
