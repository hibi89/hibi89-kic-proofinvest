"""P193 free official IR single-run no SEC no retry and bounded byte gate."""
from __future__ import annotations

import io
from hashlib import sha256
import unittest

from proofinvest import apple_issuer_2026_ir_probe as p


class Reply(io.BytesIO):
    def __init__(self, raw: bytes, url: str, mime: str):
        super().__init__(raw)
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": mime, "Content-Length": str(len(raw))}

    def geturl(self):
        return self.url


class AppleIRFY2026OnceTests(unittest.TestCase):
    def test_exact_first_party_link_and_two_bounded_gets(self):
        link = "https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/report-2026.html"
        html = ('<html><a href="' + link + '">2026 10-K</a></html>').encode()
        original = b"<html><title>FORM 10-K</title> FY2026 PUBLIC</html>"
        calls = []
        def open_once(req):
            calls.append(req.full_url)
            return Reply(html if len(calls) == 1 else original, req.full_url,
                         "text/html")
        out = p.probe_issuer_ir_fy2026_once(open_once=open_once)
        self.assertEqual(out["status"],
                         "ISSUER_IR_REFERENCED_REAL_2026_DOCUMENT_BYTES_FETCHED_UNVERIFIED")
        self.assertEqual(calls, [p._IR, link])
        self.assertEqual(out["source_2026_report_html_or_pdf_sha256"],
                         sha256(original).hexdigest())
        self.assertEqual(out["network_get_attempted"], 2)
        self.assertEqual(out["sec_http_requests"], 0)
        for flag in ("raw_bytes_persisted", "raw_bytes_uploaded",
                     "sec_edgar_original_authenticated", "source_license_verified",
                     "trade_executed"):
            self.assertFalse(out[flag])

    def test_missing_link_only_one_request_no_retry(self):
        calls = []
        def open_once(req):
            calls.append(req.full_url)
            return Reply(b"<html>no live report</html>", req.full_url, "text/html")
        out = p.probe_issuer_ir_fy2026_once(open_once=open_once)
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertEqual(out["reason_code"],
                         "UNIQUE_OFFICIAL_2026_10K_LINK_NOT_OBSERVED")
        self.assertEqual(calls, [p._IR])

    def test_unrelated_host_and_2025_not_selected(self):
        for html in (
            b'<a href="https://www.sec.gov/2026-10-k.html">2026 10-K</a>',
            b'<a href="https://example.org/2026-10-k.html">2026 10-K</a>',
            b'<a href="https://www.apple.com/report-2025.htm">2025 10-K</a>',
            b'<a href="http://investor.apple.com/2026-10-k.html">2026 10-K</a>',
        ):
            self.assertEqual(p._candidate_urls(html), [])

    def test_redirect_or_oversize_fails_and_never_contacts_sec(self):
        class Redirect(Reply):
            def geturl(self):
                return "https://www.sec.gov/no"
        out = p.probe_issuer_ir_fy2026_once(
            open_once=lambda req: Redirect(b"<html/>", p._IR, "text/html"))
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertEqual(out["network_get_attempted"], 1)
        self.assertEqual(out["sec_http_requests"], 0)


if __name__ == "__main__":
    unittest.main()
