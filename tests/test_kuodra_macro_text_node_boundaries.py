"""P23: prevent invisible SEC HTML from promoting macro exposure cards."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import synthetic_companyfacts, synthetic_submissions
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_capture_replay import replay_saved_capture
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.visible_text_evidence import confirm_filing_exposure_text_node
from proofinvest.kuodra_macro import review_macro_context
from test_kuodra_macro import QUOTE, observation, exposure

_LITERAL = QUOTE.encode("utf-8")


def inspection(raw: bytes, quote: str = QUOTE, *, position: int | None = None):
    start = raw.index(quote.encode("utf-8")) if position is None else position
    ex = exposure()
    ex.update(literal=quote, start_byte=start,
              end_byte_exclusive=start + len(quote.encode("utf-8")))
    return review_macro_context(
        original_filing=raw, issuer_cik="0000000001",
        as_of="2025-10-16", exposures=[ex],
        observations=[observation()],
    )


class MacroTextNodeP23Tests(unittest.TestCase):
    def test_script_comment_attributes_and_head_are_not_filing_exposures(self):
        sources = (
            b"<html><script>" + _LITERAL + b"</script><body></body></html>",
            b"<html><body><!--" + _LITERAL + b"--></body></html>",
            b'<html><body><p data-risk="' + _LITERAL + b'">no exposure</p></body></html>',
            b"<html><head><title>" + _LITERAL + b"</title></head><body></body></html>",
            b"<html><body><style>" + _LITERAL + b"</style></body></html>",
        )
        for raw in sources:
            with self.subTest(source=raw[:18]):
                result = inspection(raw)
                self.assertEqual(result["cards"], [])
                self.assertEqual(
                    result["candidate_checks"][0]["reason_code"],
                    "EXPOSURE_NOT_IN_ELIGIBLE_HTML_TEXT_NODE",
                )

    def test_ixbrl_hidden_header_resources_and_exclude_do_not_promote(self):
        for tag in ("ix:hidden", "ix:header", "ix:references",
                    "ix:resources", "ix:exclude"):
            with self.subTest(tag=tag):
                raw = (f"<html><body><{tag}>".encode() + _LITERAL
                       + f"</{tag}></body></html>".encode())
                self.assertFalse(inspection(raw)["cards"])

    def test_regular_and_inline_visible_body_remain_eligible(self):
        for raw in (
            b"<html><body><p>" + _LITERAL + b"</p></body></html>",
            b"<html><body><ix:nonFraction>" + _LITERAL
            + b"</ix:nonFraction></body></html>",
        ):
            with self.subTest(raw=raw[:40]):
                result = inspection(raw)
                self.assertEqual(len(result["cards"]), 1)
                self.assertTrue(result["cards"][0]["exposure_exact_html_text_node_verified"])
                self.assertFalse(result["cards"][0]["exposure_browser_visibility_verified"])
                self.assertFalse(result["source_authenticated"])
                self.assertFalse(result["guard_policy_modified"])

    def test_korean_text_with_utf8_prefix_retains_exact_byte_offset(self):
        quote = "매출 증가 및 반도체 수요 노출"
        raw = ("<html><body><p>세계 시장: " + quote + "</p></body></html>").encode()
        located = confirm_filing_exposure_text_node(
            raw, needle=quote,
            expected_start=raw.index(quote.encode()),
            expected_end=raw.index(quote.encode()) + len(quote.encode()),
        )
        self.assertTrue(located["exact_raw_byte_span_verified"])
        self.assertFalse(located["source_authenticated"])
        self.assertEqual(inspection(raw, quote)["cards"][0]["exposure_literal"], quote)

    def test_long_operator_quote_remains_supported_through_1024_bytes(self):
        quote = "The issuer reports recurring operational exposure. " * 12
        self.assertGreater(len(quote), 128)
        self.assertLessEqual(len(quote), 1024)
        raw = b"<p>" + quote.encode() + b"</p>"
        self.assertEqual(inspection(raw, quote)["cards"][0]["exposure_literal"], quote)

    def test_hidden_and_body_same_text_selects_only_actual_body_span(self):
        raw = b"<script>" + _LITERAL + b"</script><p>" + _LITERAL + b"</p>"
        body = raw.index(_LITERAL, raw.index(b"<p>"))
        result = inspection(raw, position=body)
        self.assertEqual(len(result["cards"]), 1)
        self.assertEqual(result["cards"][0]["original_exposure_span"][0], body)
        self.assertFalse(inspection(raw)["cards"])

    def test_duplicate_visible_literals_and_malformed_hidden_fail_closed(self):
        sources = (
            b"<p>" + _LITERAL + b"</p><p>" + _LITERAL + b"</p>",
            b"<p>" + _LITERAL + b"</p><ix:hidden>never closed",
        )
        for raw in sources:
            with self.subTest(case=raw[-16:]):
                self.assertEqual(inspection(raw)["cards"], [])

    def test_invalid_utf8_and_unicode_surrogate_are_never_promoted(self):
        raw = b"<p>" + _LITERAL + b"</p>\xff"
        self.assertFalse(inspection(raw)["cards"])
        invalid = exposure()
        invalid["literal"] = "\ud800" * 10
        raw = b"<p>" + _LITERAL + b"</p>"
        result = review_macro_context(
            original_filing=raw, issuer_cik="0000000001", as_of="2025-10-16",
            exposures=[invalid], observations=[observation()],
        )
        self.assertFalse(result["cards"])

    def test_saved_sec_zip_to_guard_blocks_hidden_macro_without_changing_hold(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p23-") as tmp:
            folder = Path(tmp)
            archive = folder / "source.zip"
            database = folder / "audit.sqlite"
            marker = b"material USD sales exposure"
            raw_filing = SYNTHETIC_HTML.replace(
                b"</body>", b"<script>" + marker + b"</script></body>"
            )
            # If fixture has no literal </body> fallback preserves its full bytes.
            self.assertIn(marker, raw_filing)
            receipt = {
                "schema": "proofinvest.sec-3source-explicit-transport.v1",
                "status": "three_sec_https_responses_captured_unverified",
                "http_requests_attempted": 3, "live_sec_http_called": True,
                "issuer_cik": "0000000001", "accession": "0000000001-25-000001",
                "source_uris": {
                    "submissions": "https://data.sec.gov/submissions/CIK0000000001.json",
                    "companyfacts": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json",
                    "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
                },
                "raw_response_sha256": {
                    "submissions": hashlib.sha256(synthetic_submissions()).hexdigest(),
                    "companyfacts": hashlib.sha256(json.dumps(synthetic_companyfacts()).encode()).hexdigest(),
                    "original_filing": hashlib.sha256(raw_filing).hexdigest(),
                },
                "observed_utc_day": "2025-10-16",
                "submissions_observed_at_utc": "2025-10-16T12:00:00Z",
                "companyfacts_observed_at_utc": "2025-10-16T12:00:01Z",
                "original_observed_at_utc": "2025-10-16T12:00:02Z",
                "capture_bytes_persisted": False, "source_authenticated": False,
                "financial_facts_authenticated": False, "source_rights_verified": False,
                "official_contest_submission": False,
            }
            save_local_capture_bundle(
                archive, receipt=receipt,
                submissions=synthetic_submissions(),
                companyfacts=json.dumps(synthetic_companyfacts()).encode(),
                original_filing=raw_filing,
            )
            pos = raw_filing.index(marker)
            macro = {
                "exposures": [{
                    "series_id": "US_CPI_YOY", "start_byte": pos,
                    "end_byte_exclusive": pos + len(marker),
                    "literal": marker.decode(),
                    "rationale": "Synthetic historical sensitivity, not proven.",
                }],
                "observations": [{
                    **observation("US_CPI_YOY"),
                }],
            }
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_SEC_OR_MODEL_HTTP")) as network:
                result = replay_saved_capture(
                    bundle_path=archive, audit_db=database,
                    run_id="p23-hidden-macro-1",
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE, acknowledge_local_audit_persistence=True,
                    macro_context=macro,
                )
            network.assert_not_called()
            self.assertEqual(result["guard"]["decision"], "HOLD")
            self.assertEqual(result["macro_context"]["cards"], [])
            self.assertFalse(result["source_authenticated"])
            self.assertFalse(result["macro_context"]["guard_policy_modified"])


if __name__ == "__main__":
    unittest.main()
