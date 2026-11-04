"""P198: structured XBRL source facts, no unsafe fallback or SEC retry."""
import io
import unittest
from hashlib import sha256
from unittest.mock import patch
from proofinvest import dell_real_ixbrl_2026_once as p


def sample(a="113,538", b="95,567", scale="6", segment=""):
    return (f"""<html><body><h1>Dell Technologies FORM 10-K</h1>
    <p>January 30, 2026 January 31, 2025 113,538 95,567 5,936 11,185</p>
    <xbrli:context id="c26"><xbrli:entity>{segment}</xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-02-01</xbrli:startDate>
    <xbrli:endDate>2026-01-30</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="c25"><xbrli:period>
    <xbrli:startDate>2024-02-03</xbrli:startDate>
    <xbrli:endDate>2025-01-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    contextRef="c26" unitRef="usd" scale="{scale}">{a}</ix:nonFraction>
    <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    contextRef="c25" unitRef="usd" scale="6">{b}</ix:nonFraction>
    </body></html>""").encode()


class Reply(io.BytesIO):
    def __init__(self, data, url=p._URL):
        super().__init__(data)
        self.url = url
        self.status = 200
        self.headers = {"Content-Type": "text/html", "Content-Length": str(len(data))}
    def geturl(self):
        return self.url


class RealIxbrlTests(unittest.TestCase):
    def test_two_annual_undimensioned_usd_context_facts(self):
        facts = p.extract_dell_ixbrl_2026(sample())
        self.assertEqual(facts["FY2026"]["revenue_usd_millions"], "113538")
        self.assertEqual(facts["FY2025"]["revenue_usd_millions"], "95567")
        self.assertEqual(facts["FY2026"]["xbrl_context"], "c26")

    def test_reject_tamper_wrong_period_currency_segment(self):
        for altered in (
            sample(a="113,539"), sample(b="95,568"), sample(scale="3"),
            sample().replace(b"iso4217:USD", b"iso4217:EUR"),
            sample().replace(b"2025-02-01", b"2025-01-01"),
            sample().replace(b'contextRef="c26"', b'contextRef="x"'),
            sample(segment='<xbrli:segment><xbrldi:explicitMember dimension="a:b">a:c</xbrldi:explicitMember></xbrli:segment>'),
            sample().replace(b"us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax", b"fake:revenues"),
            sample().replace(b"<ix:nonFraction", b"<span").replace(b"</ix:nonFraction>", b"</span>"),
        ):
            with self.subTest(variant=sha256(altered).hexdigest()[:8]):
                with self.assertRaises(ValueError):
                    p.extract_dell_ixbrl_2026(altered)

    def test_actual_nested_xbrl_keeps_inner_fact_provenance(self):
        # Reproduces Dell HTML's nested iXBRL nonfraction shapes. Parent's
        # amounts must never be merged into the real annual revenue fact.
        raw = sample()
        raw = raw.replace(
            b'<ix:nonFraction name=',
            b'<ix:nonFraction name="us-gaap:Assets" contextRef="c26" '
            b'unitRef="usd" scale="6">100<ix:nonFraction name=', 1
        ).replace(
            b'</ix:nonFraction>',
            b'</ix:nonFraction>200</ix:nonFraction>', 1
        )
        result = p.extract_dell_ixbrl_2026(raw)
        self.assertEqual(result["FY2026"]["revenue_usd_millions"], "113538")
        self.assertEqual(result["FY2025"]["revenue_usd_millions"], "95567")

    def test_one_public_https_get_and_keep_raw_ephemeral(self):
        got = []
        with patch.object(p, "_open", side_effect=AssertionError("NO_NETWORK")):
            result = p.verify_dell_issuer_ixbrl_once(
                opener=lambda req: (got.append(req), Reply(sample()))[1])
        self.assertEqual(result["status"], "REAL_ISSUER_2026_IXBRL_REVENUES_RECOMPUTED")
        self.assertEqual(len(got), 1)
        self.assertEqual(result["http_get_attempted"], 1)
        self.assertEqual(result["sec_http_calls"], 0)
        for key in ("raw_html_saved", "raw_html_uploaded",
                    "origin_sec_edgar_byte_identical", "stock_ndx_peer_rights_verified",
                    "commercial_model_rights_verified", "full_abc_ready"):
            self.assertFalse(result[key])
        self.assertEqual(result["guard"], "HOLD")
        self.assertEqual(result["trades"], 0)

    def test_redirect_and_malformed_rejected_without_retry(self):
        got = []
        result = p.verify_dell_issuer_ixbrl_once(
            opener=lambda req: (got.append(req), Reply(sample(), "https://www.sec.gov/no"))[1])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["http_get_attempted"], 1)
        self.assertEqual(len(got), 1)
        self.assertEqual(result["sec_http_calls"], 0)

    def test_visible_financial_text_without_xbrl_not_accepted(self):
        with self.assertRaises(ValueError):
            p.extract_dell_ixbrl_2026(
                sample().replace(b"<ix:nonFraction", b"<span").replace(b"</ix:nonFraction>", b"</span>"))


if __name__ == "__main__":
    unittest.main()
