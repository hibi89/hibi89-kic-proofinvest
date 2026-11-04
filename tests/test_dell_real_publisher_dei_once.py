"""P201 actual first-party issuer iXBRL DEI identity vs published SEC index."""
from __future__ import annotations

from hashlib import sha256
import io
import unittest
from unittest.mock import patch

from proofinvest import dell_real_publisher_dei_once as p


def sample() -> bytes:
    return ("""<html><body><h1>DELL TECHNOLOGIES FORM 10-K</h1>
     <p>January 30, 2026 January 31, 2025 113,538 95,567 5,936 11,185</p>
     <ix:nonNumeric name="dei:EntityCentralIndexKey">0001571996</ix:nonNumeric>
     <ix:nonNumeric name="dei:EntityRegistrantName">Dell Technologies Inc.</ix:nonNumeric>
     <ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric>
     <ix:nonNumeric name="dei:DocumentPeriodEndDate">2026-01-30</ix:nonNumeric>
     <ix:nonNumeric name="dei:DocumentFiscalYearFocus">2026</ix:nonNumeric>
     <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">FY</ix:nonNumeric>
     </body></html>""").encode()


class Reply(io.BytesIO):
    def __init__(self, body, url=p._URL):
        super().__init__(body)
        self.status = 200
        self.url=url
        self.headers = {"Content-Type":"text/html", "Content-Length":str(len(body))}
    def geturl(self):
        return self.url


class DellRealIssuerIdentityTests(unittest.TestCase):
    def test_exact_public_index_and_raw_dei_identity(self):
        result=p.extract_dell_real_sec_document_identity(sample())
        self.assertEqual(result["cik"], "0001571996")
        self.assertEqual(result["form"], "10-K")
        self.assertEqual(result["fiscal_end"], "2026-01-30")
        self.assertEqual(result["verified_dei_tag_types"], 6)
        self.assertFalse(result["publisher_bytes_identical_to_sec_original"])

    def test_tamper_cik_ticker_form_year_period_issuer_prohibited(self):
        raw=sample()
        for before,after in (
            (b'0001571996',b'0000000001'),
            (b'Dell Technologies Inc.</ix:nonNumeric>',b'Other Inc.</ix:nonNumeric>'),
            (b'10-K</ix:nonNumeric>',b'10-Q</ix:nonNumeric>'),
            (b'2026-01-30</ix:nonNumeric>',b'2026-01-31</ix:nonNumeric>'),
            (b'2026</ix:nonNumeric>',b'2025</ix:nonNumeric>'),
            (b'FY</ix:nonNumeric>',b'Q4</ix:nonNumeric>'),
            (b'<ix:nonNumeric name="dei:EntityCentralIndexKey">',
             b'<ix:nonNumeric name="dei:FakeIndexKey">'),
        ):
            changed=raw.replace(before,after)
            with self.subTest(digest=sha256(changed).hexdigest()[:10]):
                with self.assertRaises(ValueError):
                    p.extract_dell_real_sec_document_identity(changed)

    def test_long_unrelated_ixbrl_notes_ignored_but_dei_cap_remains(self):
        public=sample().replace(
            b"</body>",
            b'<ix:nonNumeric name="dell:UnrelatedTextNarrative">'
            + b"x" * 10000 + b"</ix:nonNumeric></body>"
        )
        proof=p.extract_dell_real_sec_document_identity(public)
        self.assertEqual(proof["verified_dei_tag_types"],6)
        invalid=sample().replace(
            b'<ix:nonNumeric name="dei:EntityRegistrantName">',
            b'<ix:nonNumeric name="dei:EntityRegistrantName">'
            + b"A"*401
        )
        with self.assertRaises(ValueError):
            p.extract_dell_real_sec_document_identity(invalid)

    def test_real_data_source_version_required_and_one_get(self):
        called=[]
        with patch.object(p,"_open",side_effect=AssertionError("NO_EXTERNAL")):
            res=p.verify_dell_real_source_identity_once(
                opener=lambda req:(called.append(req),Reply(sample()))[1])
        self.assertEqual(len(called),1)
        self.assertEqual(res["reason_code"],"SOURCE_VERSION_NOT_PREVIOUSLY_VERIFIED")
        self.assertEqual(res["status"],"BLOCKED")
        self.assertEqual(res["http_get_attempted"],1)
        self.assertEqual(res["sec_http_requests"],0)
        self.assertIsNone(res["identity"])
        for flag in ("issuer_original_bytes_authenticated_via_sec_edgar",
                     "source_redistribution_ai_rights","stock_ndx_licenses",
                     "raw_body_saved","raw_body_uploaded","trade_executed"):
            self.assertIs(res[flag],False)

    def test_reject_redirect_other_source_and_no_retry(self):
        sent=[]
        res=p.verify_dell_real_source_identity_once(
            opener=lambda req:(sent.append(req), Reply(sample(),url="https://www.sec.gov/no"))[1])
        self.assertEqual(len(sent),1)
        self.assertEqual(res["status"],"BLOCKED")
        self.assertEqual(res["sec_http_requests"],0)

    def test_duplicate_dei_conflicts_not_overridden(self):
        bad=sample().replace(b'</body>',
                             b'<ix:nonNumeric name="dei:DocumentType">10-Q</ix:nonNumeric></body>')
        with self.assertRaises(ValueError):
            p.extract_dell_real_sec_document_identity(bad)


if __name__ == "__main__":
    unittest.main()
