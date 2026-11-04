"""P195 official Dell 2026 direct IR bytes: bounded GET and source contract."""
import io
import unittest
from hashlib import sha256
from unittest.mock import patch

from proofinvest import dell_issuer_2026_10k_once as p


def _sample():
    s = ("<html><body><h1>DELL TECHNOLOGIES INC.</h1>"
         "<div>FORM 10-K Fiscal 2026 January 30, 2026 "
         "Fiscal 2025 January 31, 2025</div>"
         "<p>Consolidated net revenue: 113,538 and 95,567</p>"
         "<p>Net income: 5,936; operating cash flow: 11,185</p>"
         "</body></html>")
    return s.encode("utf-8")


class _Reply(io.BytesIO):
    def __init__(self, data, url=p._URL, status=200,
                 mime="text/html", encoding="identity"):
        super().__init__(data)
        self.url, self.status = url, status
        self.headers = {
            "Content-Type": mime,
            "Content-Length": str(len(data)),
            "Content-Encoding": encoding,
        }

    def geturl(self):
        return self.url


class Dell2026OfficialOriginalTests(unittest.TestCase):
    def test_publisher_host_single_get_matching_six_financial_cells(self):
        called = []
        data = _sample()
        def one(req):
            called.append(req)
            return _Reply(data)
        with patch.object(p, "_open", side_effect=AssertionError("OFFLINE_MOCK_ONLY")):
            x = p.probe_dell_official_2026_10k_once(open_once=one)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0].full_url, p._URL)
        self.assertEqual(called[0].get_method(), "GET")
        self.assertEqual(x["status"],
                         "ISSUER_HTTPS_REAL_DELL_2026_10K_BYTES_CROSSCHECKED")
        self.assertEqual(x["issuer_https_get_attempted"], 1)
        self.assertEqual(x["source_original_sha256"], sha256(data).hexdigest())
        self.assertEqual(x["verified_visible_issuer_financial_cells"], 6)
        for flag in ("sec_edgar_identical_original_verified",
                     "source_rights_verified", "original_bytes_uploaded",
                     "original_bytes_written_to_disk", "trade_executed"):
            self.assertIs(x[flag], False, flag)

    def test_tampering_wrong_year_or_issuer_blocks(self):
        for original, fake in (
            (b"113,538", b"113,539"),
            (b"95,567", b"95,568"),
            (b"5,936", b"5,937"),
            (b"11,185", b"11,186"),
            (b"2026", b"2027"),
            (b"DELL TECHNOLOGIES", b"OTHER COMPANIES"),
        ):
            with self.subTest(original=original):
                r=p.probe_dell_official_2026_10k_once(
                    open_once=lambda req: _Reply(_sample().replace(original,fake)))
                self.assertEqual(r["status"], "UNAVAILABLE")
                self.assertEqual(r["issuer_https_get_attempted"], 1)
                self.assertFalse(r["issuer_html_10k_numbers_crosschecked"])
                self.assertEqual(r["guard_policy_preview"], "HOLD")

    def test_wrong_redirect_type_or_encoding_blocks_no_second_get(self):
        for other in (
            lambda d: _Reply(d, url="https://www.sec.gov/other"),
            lambda d: _Reply(d, status=403),
            lambda d: _Reply(d, mime="application/json"),
            lambda d: _Reply(d, encoding="gzip"),
        ):
            requested = []
            def one(req):
                requested.append(req)
                return other(_sample())
            x=p.probe_dell_official_2026_10k_once(open_once=one)
            self.assertEqual(len(requested), 1)
            self.assertEqual(x["status"], "UNAVAILABLE")
            self.assertEqual(x["sec_http_requests"], 0)

    def test_transport_failure_does_not_leak_source_or_retry(self):
        called=[]
        def fail(req):
            called.append(req)
            raise TimeoutError("DO_NOT_LOG_PRIVATE_INFO")
        r=p.probe_dell_official_2026_10k_once(open_once=fail)
        self.assertEqual(len(called), 1)
        self.assertEqual(r["status"], "UNAVAILABLE")
        self.assertEqual(r["reason_code"], "ONE_ISSUER_GET_UNAVAILABLE_NO_RETRY")
        self.assertEqual(r["issuer_https_get_attempted"], 1)
        self.assertNotIn("DO_NOT_LOG_PRIVATE_INFO", str(r))


    def test_cli_main_calls_probe_once_and_returns_correct_exit(self):
        import contextlib
        import json
        for status, expected_exit in (
            ("ISSUER_HTTPS_REAL_DELL_2026_10K_BYTES_CROSSCHECKED", 0),
            ("UNAVAILABLE", 2),
        ):
            with self.subTest(status=status):
                log = io.StringIO()
                with patch.object(p, "probe_dell_official_2026_10k_once",
                                  return_value={"status":status}) as run:
                    with contextlib.redirect_stdout(log):
                        result=p.main()
                self.assertEqual(result, expected_exit)
                self.assertEqual(json.loads(log.getvalue())["status"], status)
                run.assert_called_once()


if __name__=="__main__":
    unittest.main()
