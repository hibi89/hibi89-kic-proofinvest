"""P128 exact-byte original local review: synthetic offline tests only."""
from __future__ import annotations

from hashlib import sha256
import os
import unittest
from unittest.mock import patch

from proofinvest import apple_p127_local_evidence as evidence
from proofinvest import ticker_research_ui as ui
from tests.test_apple_local_html_crosscheck import sample_html
from tests.test_ticker_research_ui import FakeSt, Uploaded


class AppleP128EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = sample_html()
        self.patches = [
            patch.object(evidence, "OBSERVED_SIZE", len(self.raw)),
            patch.object(evidence, "OBSERVED_SHA256", sha256(self.raw).hexdigest()),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_prior_observation_does_not_claim_authentication(self):
        receipt = evidence.prior_public_observation()
        self.assertEqual(receipt["status"], "P127_HISTORICAL_OBSERVATION_ONLY")
        self.assertEqual(receipt["network_requests"], 0)
        self.assertFalse(receipt["source_rights_verified"])
        self.assertFalse(receipt["original_bytes_retained"])

    def test_exact_byte_match_replays_24_cells_without_network(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK")) as net:
            result = evidence.review_local_apple_p127_original(
                self.raw, ticker="AAPL", as_of="2025-11-01")
        net.assert_not_called()
        self.assertEqual(result["status"], evidence.SUCCESS)
        self.assertEqual(result["matched_numeric_cells"], 24)
        self.assertTrue(result["local_file_matches_p127_observation"])
        self.assertFalse(result["sec_original_authenticated"])
        self.assertFalse(result["issuer_cryptographic_attestation"])
        self.assertFalse(result["source_rights_verified"])
        self.assertEqual(result["network_requests"], 0)

    def test_different_bytes_or_same_length_tamper_fail_closed(self):
        altered = self.raw.replace(b"416,161", b"416,162")
        self.assertEqual(len(altered), len(self.raw))
        for raw in (altered, self.raw + b" ", b"", b"not html"):
            result = evidence.review_local_apple_p127_original(
                raw, ticker="AAPL", as_of="2025-11-01")
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["reason_code"],
                             "LOCAL_BYTES_DIFFER_FROM_P127_OBSERVATION"
                             if raw else "LOCAL_ORIGINAL_HTML_SIZE_OR_TYPE_BLOCKED")
            self.assertFalse(result["local_file_matches_p127_observation"])

    def test_asof_ticker_type_and_size_guards(self):
        cases = [
            ("NVDA", "2025-11-01", self.raw, "APPLE_TICKER_REQUIRED"),
            ("AAPL", "2025-10-30", self.raw, "FILING_NOT_YET_AVAILABLE_AS_OF"),
            ("AAPL", "2025-02-30", self.raw, "INVALID_AS_OF_DATE"),
            ("AAPL", "2025-11-01", "bad", "LOCAL_ORIGINAL_HTML_SIZE_OR_TYPE_BLOCKED"),
        ]
        for ticker, as_of, raw, reason in cases:
            with self.subTest(reason=reason):
                out = evidence.review_local_apple_p127_original(
                    raw, ticker=ticker, as_of=as_of)
                self.assertEqual(out["reason_code"], reason)
        with patch.object(evidence, "MAX_UPLOAD_SIZE", len(self.raw)-1):
            self.assertEqual(
                evidence.review_local_apple_p127_original(
                    self.raw, ticker="AAPL", as_of="2025-11-01"
                )["reason_code"],
                "LOCAL_ORIGINAL_HTML_SIZE_OR_TYPE_BLOCKED",
            )

    def test_even_same_hash_parser_failure_cannot_upgrade(self):
        with patch.object(evidence, "verify_local_apple_10k_html",
                          side_effect=ValueError("PRIVATE_RAW_DO_NOT_PRINT")):
            out = evidence.review_local_apple_p127_original(
                self.raw, ticker="AAPL", as_of="2025-11-01")
        self.assertEqual(out["status"], "BLOCKED")
        self.assertNotIn("PRIVATE_RAW", str(out))
        self.assertFalse(out["source_rights_verified"])

    def test_ticker_page_requires_explicit_local_file_and_click(self):
        upload = Uploaded(self.raw)
        st = FakeSt(
            clicked="Apple P127 관측 SHA·재무 24칸 로컬 검증 (네트워크 없음)",
            values={"kuodra_p100_ticker": "AAPL", "kuodra_p100_as_of": "2025-11-01"},
            uploads={"kuodra_p128_apple_original": upload},
        )
        with (
            patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO NETWORK")) as net,
        ):
            ui.render_single_ticker_search(st)
        net.assert_not_called()
        shown = [v for k,v in st.messages
                 if k == "json" and isinstance(v, dict)
                 and v.get("status") == evidence.SUCCESS]
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["matched_numeric_cells"], 24)
        self.assertFalse(shown[0]["source_rights_verified"])
        self.assertFalse(any(k == "download" for k,_ in st.messages))

    def test_no_file_no_run_and_prior_date_button_disabled(self):
        for upload, as_of in ((None, "2025-11-01"),
                              (Uploaded(self.raw), "2025-10-30")):
            st = FakeSt(
                clicked="Apple P127 관측 SHA·재무 24칸 로컬 검증 (네트워크 없음)",
                values={"kuodra_p100_ticker": "AAPL", "kuodra_p100_as_of": as_of},
                uploads={"kuodra_p128_apple_original": upload},
            )
            with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
                ui.render_single_ticker_search(st)
            self.assertTrue(any(
                label.startswith("Apple P127 관측") and disabled
                for label, disabled in st.buttons))
            self.assertFalse(any(
                k == "json" and isinstance(v, dict)
                and v.get("status") == evidence.SUCCESS
                for k, v in st.messages
            ))


if __name__ == "__main__":
    unittest.main()
