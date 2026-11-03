"""P127 issuer-hosted one-shot HTTPS transport, completely mocked offline."""
from __future__ import annotations

from hashlib import sha256
import io
import unittest
from unittest.mock import patch

from proofinvest import apple_issuer_original_probe_once as probe
from tests.test_apple_local_html_crosscheck import sample_html


class Response(io.BytesIO):
    def __init__(self, raw: bytes, *, url: str = probe._URL,
                 status: int = 200, headers: dict | None = None):
        super().__init__(raw)
        self.url = url
        self.status = status
        self.headers = headers or {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": str(len(raw)),
        }
    def geturl(self):
        return self.url


class IssuerOriginalOnceTests(unittest.TestCase):
    def test_one_public_https_get_replays_existing_24_real_reported_numeric_cells(self):
        raw = sample_html()
        requests = []
        def one(request):
            requests.append(request)
            return Response(raw)
        with patch.object(probe, "_default_open",
                          side_effect=AssertionError("USE_EXPLICIT_MOCK")):
            result = probe.probe_apple_issuer_original_once(open_once=one)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].full_url, probe._URL)
        self.assertEqual(requests[0].get_method(), "GET")
        self.assertEqual(requests[0].get_header("Accept-encoding"), "identity")
        self.assertEqual(result["status"],
                         "ISSUER_HTTPS_HTML_24_NUMERIC_CELLS_MATCHED_ORIGIN_UNVERIFIED")
        self.assertEqual(result["original_html_sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["original_html_bytes"], len(raw))
        self.assertEqual(result["matched_numeric_cells"], 24)
        self.assertTrue(result["issuer_tls_host_matched"])
        self.assertEqual(result["issuer_get_attempted"], 1)
        self.assertEqual(result["issuer_get_budget"], 1)
        self.assertEqual(result["sec_http_requests"], 0)
        self.assertEqual(result["vendor_market_api_requests"], 0)
        for key in ("original_html_written_to_disk", "original_html_uploaded",
                    "sec_original_authenticated", "source_authenticated",
                    "source_rights_verified", "external_display_allowed",
                    "ai_processing_allowed", "trade_executed",
                    "audit_written", "owner_private_file_transferred",
                    "official_contest_submission"):
            self.assertIs(result[key], False, key)

    def test_wrong_host_redirect_or_http_error_is_hard_block_no_followup(self):
        for url, status in (
            ("https://www.sec.gov/not-allowed", 200),
            (probe._URL, 302), (probe._URL, 403),
        ):
            with self.subTest(url=url,status=status):
                count = []
                def once(req):
                    count.append(req)
                    return Response(sample_html(), url=url, status=status)
                result = probe.probe_apple_issuer_original_once(open_once=once)
                self.assertEqual(len(count), 1)
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertEqual(result["reason_code"],
                                 "ISSUER_REDIRECT_OR_HTTP_STATUS_BLOCKED")
                self.assertEqual(result["matched_numeric_cells"], 0)
                self.assertIsNone(result["original_html_sha256"])

    def test_no_unbounded_html_or_nonhtml_accepted(self):
        raw = sample_html()
        for headers, data, why in (
            ({"Content-Type": "application/json"}, raw, "ISSUER_CONTENT_TYPE_UNEXPECTED"),
            ({"Content-Type": "text/html", "Content-Encoding": "gzip"},
             raw, "ISSUER_RESPONSE_ENCODING_UNEXPECTED"),
            ({"Content-Type": "text/html", "Content-Length": "5000001"},
             raw, "ISSUER_RESPONSE_LENGTH_INVALID"),
            ({"Content-Type": "text/html", "Content-Length": "NaN"},
             raw, "ISSUER_RESPONSE_LENGTH_INVALID"),
            ({"Content-Type": "text/html", "Content-Length": str(len(raw)+5)},
             raw, "ISSUER_HTML_LENGTH_MISMATCH"),
        ):
            with self.subTest(why=why, headers=headers):
                response = Response(data, headers=headers)
                result = probe.probe_apple_issuer_original_once(
                    open_once=lambda req: response)
                self.assertEqual(result["reason_code"], why)
                self.assertEqual(result["status"], "UNAVAILABLE")

        with patch.object(probe, "_MAX", 10):
            result = probe.probe_apple_issuer_original_once(
                open_once=lambda req: Response(raw))
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertEqual(result["reason_code"], "ISSUER_RESPONSE_LENGTH_INVALID")

    def test_real_byte_mismatch_does_not_claim_matching_financials(self):
        raw = sample_html().replace(b"416,161", b"416,162")
        result = probe.probe_apple_issuer_original_once(
            open_once=lambda req: Response(raw))
        self.assertEqual(result["status"],
                         "ISSUER_BYTES_FETCHED_NUMERIC_CROSSCHECK_BLOCKED")
        self.assertEqual(result["reason_code"],
                         "ACTUAL_ISSUER_HTML_LAYOUT_OR_VALUES_UNVERIFIED")
        self.assertEqual(result["original_html_sha256"], sha256(raw).hexdigest())
        self.assertEqual(result["matched_numeric_cells"], 0)
        self.assertFalse(result["sec_original_authenticated"])

    def test_network_failure_is_one_attempt_and_no_exception_leak(self):
        calls = []
        def fail(request):
            calls.append(request)
            raise TimeoutError("simulated failure with credentials=DO_NOT_PRINT")
        out = probe.probe_apple_issuer_original_once(open_once=fail)
        self.assertEqual(len(calls), 1)
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertEqual(out["issuer_get_attempted"], 1)
        self.assertEqual(out["reason_code"],
                         "ISSUER_ONE_SHOT_GET_OR_PARSE_FAILED_NO_RETRY")
        self.assertNotIn("DO_NOT_PRINT", repr(out))
        self.assertIsNone(out["original_html_sha256"])

    def test_default_url_is_fixed_official_publisher_host_and_no_sec_fallback(self):
        self.assertEqual(probe._HOST, "d18rn0p25nwr6d.cloudfront.net")
        self.assertNotIn("sec.gov", probe._URL)
        self.assertTrue(probe._URL.startswith("https://"+probe._HOST+"/"))
        with patch.object(probe, "_URL", "https://www.sec.gov/Archives/example"), \
             patch.object(probe, "_default_open",
                          side_effect=AssertionError("SEC REQUEST PROHIBITED")):
            out = probe.probe_apple_issuer_original_once()
        self.assertEqual(out["reason_code"], "ISSUER_ALLOWLIST_MISMATCH")
        self.assertEqual(out["issuer_get_attempted"], 0)


if __name__ == "__main__":
    unittest.main()
