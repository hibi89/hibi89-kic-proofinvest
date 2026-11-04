"""P200 strict GAAP CFO/NI real report iXBRL, reject tamper and wrong years."""
from __future__ import annotations

import io
from hashlib import sha256
import unittest
from unittest.mock import patch

from proofinvest import dell_financial_quality_ixbrl_once as p


def sample() -> bytes:
    parts = ['<html><body><h1>DELL TECHNOLOGIES FORM 10-K</h1>',
             '<div>January 30, 2026 January 31, 2025 113,538 95,567 5,936 11,185</div>',
             '<xbrli:unit id="u1"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>']
    for fy, start, end, income, cash in (
        ("c26", "2025-02-01", "2026-01-30", "5,936", "11,185"),
        ("c25", "2024-02-03", "2025-01-31", "4,576", "4,521"),
    ):
        parts.append(
            f'<xbrli:context id="{fy}"><xbrli:period><xbrli:startDate>{start}</xbrli:startDate>'
            f'<xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>')
        parts.append(
            f'<ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="{fy}" '
            f'unitRef="u1" scale="6">{income}</ix:nonFraction>'
            f'<ix:nonFraction name="us-gaap:NetCashProvidedByUsedInOperatingActivities" '
            f'contextRef="{fy}" unitRef="u1" scale="6">{cash}</ix:nonFraction>')
    parts.append('</body></html>')
    return "".join(parts).encode()


class Reply(io.BytesIO):
    def __init__(self, data, *, url=p._URL):
        super().__init__(data)
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": "text/html", "Content-Length": str(len(data))}
    def geturl(self):
        return self.url


class RealEngineBFinancialQuality(unittest.TestCase):
    def test_genuine_xbrl_cash_flow_vs_net_income_two_years(self):
        facts = p.extract_dell_real_cashflow_income_xbrl(sample())
        self.assertEqual(facts["FY2026"]["operating_cash_flow"]["amount_usd_millions"], "11185")
        self.assertEqual(facts["FY2026"]["net_income"]["amount_usd_millions"], "5936")
        self.assertEqual(facts["FY2025"]["operating_cash_flow"]["amount_usd_millions"], "4521")
        self.assertEqual(facts["FY2025"]["net_income"]["amount_usd_millions"], "4576")
        self.assertEqual(facts["FY2026"]["cash_minus_income_usd_millions"], "5249")
        self.assertEqual(facts["FY2025"]["cash_minus_income_usd_millions"], "-55")
        self.assertEqual(facts["FY2026"]["cash_conversion_ratio"], "1.8843")
        self.assertEqual(facts["FY2025"]["cash_conversion_ratio"], "0.9880")
        self.assertNotEqual(facts["FY2026"]["human_only_signal"],
                            facts["FY2025"]["human_only_signal"])

    def test_bad_currency_year_dimension_and_xbrl_tag_blocks(self):
        d = sample()
        for variant in (
            d.replace(b'5,936</ix:nonFraction>', b'5,935</ix:nonFraction>'),
            d.replace(b'4,521</ix:nonFraction>', b'4,522</ix:nonFraction>'),
            d.replace(b'iso4217:USD', b'iso4217:EUR'),
            d.replace(b'2025-02-01', b'2025-02-02'),
            d.replace(b'us-gaap:NetIncomeLoss', b'fake:NetIncomeLoss'),
            d.replace(b'contextRef="c26"', b'contextRef="missing"'),
            d.replace(b'<ix:nonFraction', b'<div').replace(b'</ix:nonFraction>', b'</div>'),
        ):
            with self.subTest(digest=sha256(variant).hexdigest()[:10]):
                with self.assertRaises(ValueError):
                    p.extract_dell_real_cashflow_income_xbrl(variant)

    def test_one_get_origin_hash_must_match_no_network(self):
        calls = []
        with patch.object(p, "_open", side_effect=AssertionError("NO_NETWORK")):
            result = p.verify_dell_financial_quality_xbrl_once(
                opener=lambda req: (calls.append(req), Reply(sample()))[1])
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["reason_code"], "ISSUER_ORIGINAL_RAW_CONTENT_VERSION_CHANGED")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["sec_http_requests"], 0)
        self.assertEqual(result["http_get_attempted"], 1)
        self.assertIsNone(result["xbrl_facts"])
        self.assertFalse(result["raw_file_persisted"])
        self.assertFalse(result["source_commercial_ai_rights_verified"])
        self.assertFalse(result["trade_executed"])

    def test_no_redirect_or_wrong_mime_allowed(self):
        for new_url in ("https://www.sec.gov/no", "https://example.com/elsewhere"):
            called=[]
            result=p.verify_dell_financial_quality_xbrl_once(
                opener=lambda req: (called.append(req), Reply(sample(),url=new_url))[1])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(len(called), 1)
            self.assertEqual(result["guard_policy_preview"], "HOLD")
            self.assertEqual(result["sec_http_requests"], 0)

    def test_no_remote_substitution_or_ai(self):
        output=p.extract_dell_real_cashflow_income_xbrl(sample())
        self.assertEqual(output["FY2026"]["operating_cash_flow"]["xbrl_concept"],
                         "us-gaap:netcashprovidedbyusedinoperatingactivities")
        self.assertEqual(output["FY2026"]["net_income"]["xbrl_concept"], "us-gaap:netincomeloss")


if __name__ == "__main__":
    unittest.main()
