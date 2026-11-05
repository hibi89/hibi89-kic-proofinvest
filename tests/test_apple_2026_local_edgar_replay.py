"""P237 bounded local SEC FY2026 iXBRL: positive/negative, never origin proof."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofinvest import apple_2026_local_edgar_replay as p


def synthetic(*, change: str = "") -> bytes:
    # Deliberately *fabricated*. Even a valid-sized matching local source
    # must NEVER certify SEC TLS origin, account rights or a raw-file license.
    contexts = "".join(
        '<xbrli:context id="c%d"><xbrli:entity></xbrli:entity>'
        '<xbrli:period><xbrli:startDate>%s</xbrli:startDate>'
        '<xbrli:endDate>%s</xbrli:endDate></xbrli:period>'
        '</xbrli:context>' % (i+1, *p._DURATIONS[y])
        for i, y in enumerate(("2026", "2025"))
    )
    from proofinvest.apple_fy2026_public_filing_review import public_2026_values
    vals = public_2026_values()
    facts = "".join(
        '<ix:nonFraction name="%s" contextRef="c%d" unitRef="u1" '
        'scale="6">%s</ix:nonFraction>' %
        (names[0], 1 if year == "2026" else 2, vals[key][year])
        for key, names in p._CONCEPTS.items()
        for year in ("2026", "2025")
    )
    meta = "".join(
        '<ix:nonNumeric name="%s">%s</ix:nonNumeric>' % (k, val)
        for k, val in (
            ("dei:EntityCentralIndexKey", "0000320193"),
            ("dei:DocumentType", "10-K"),
            ("dei:DocumentFiscalYearFocus", "2026"),
            ("dei:DocumentPeriodEndDate", "2026-09-26"),
        )
    )
    body = ('<!doctype html><html><head></head><body>' + contexts +
            '<xbrli:unit id="u1"><xbrli:measure>iso4217:USD'
            '</xbrli:measure></xbrli:unit>' + meta + facts +
            change + '</body></html>').encode()
    if len(body) > p._SIZE:
        raise RuntimeError("TEST_FIXTURE_TOO_LARGE")
    return body + b' ' * (p._SIZE - len(body))


class Local2026EdgarTests(unittest.TestCase):
    def test_valid_shape_and_six_facts_still_not_sec_authenticated(self):
        blob = synthetic()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_SEC")) as net:
            out = p.verify_operator_apple_2026_edgar_html(blob)
        net.assert_not_called()
        self.assertEqual(out["status"], "LOCAL_SEC_2026_HTML_6_GAAP_FACTS_MATCH_UNAUTHENTICATED",out)
        self.assertEqual(out["local_html_sha256"], hashlib.sha256(blob).hexdigest())
        self.assertEqual(len(out["six_fact_names"]),6)
        self.assertTrue(out["local_bytes_verified_against_index_size"])
        self.assertTrue(out["local_ixbrl_issuer_period_fact_consistent"])
        for flag in ("transport_tls_sec_origin_authenticated",
                     "sec_edgar_original_byte_identical_authenticated",
                     "individual_original_sha256_published_by_sec",
                     "sec_get_approved_or_executed", "remote_model_requests",
                     "licensed_stock_ndx_peer_data",
                     "source_commercial_or_ai_rights_verified",
                     "full_abc_ready","investment_advice"):
            self.assertFalse(out[flag],flag)
        self.assertEqual(out["guard_policy_preview"],"HOLD")
        self.assertEqual(out["trades"],0)

    def test_conflicted_number_wrong_context_unit_and_dei_rejected(self):
        for alteration in (
            lambda b: b.replace(b"478834",b"478835",1),
            lambda b: b.replace(b"iso4217:USD",b"iso4217:EUR",1),
            lambda b: b.replace(b"2026-09-26",b"2026-09-25",1),
            lambda b: b.replace(b"0000320193",b"0000320194",1),
            lambda b: b.replace(b"10-K",b"10-Q",1),
            lambda b: b.replace(b'contextRef="c1"',b'contextRef="c3"',1),
            lambda b: b.replace(b'unitRef="u1"',b'unitRef="u2"',1),
        ):
            data=alteration(synthetic())
            self.assertEqual(len(data),p._SIZE)
            x=p.verify_operator_apple_2026_edgar_html(data)
            self.assertEqual(x["status"],"BLOCKED",x)

    def test_wrong_file_size_name_date_html_cannot_be_promoted(self):
        blob=synthetic()
        for content,options in (
            (blob[:-1],{}), (b"not a 10k",{}),
            (blob,{"filename":"aapl-20260926.pdf"}),
            (blob,{"as_of":"2026-11-06"}),
            (None,{}),
            (blob[:100]+b"\x00"+blob[101:],{}),
        ):
            with self.subTest(case=(len(content) if content else None,options)):
                x=p.verify_operator_apple_2026_edgar_html(content,**options)
                self.assertEqual(x["status"],"BLOCKED")
                self.assertFalse(x["sec_edgar_original_byte_identical_authenticated"])

    def test_cli_real_file_read_only_no_orig_echo_or_transmission(self):
        from scripts.check_local_apple_2026_edgar import main
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as tmp:
            fp=Path(tmp)/p._NAME
            b=synthetic()
            fp.write_bytes(b)
            with patch("urllib.request.urlopen",side_effect=AssertionError("HTTP")):
                stdout=io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    result=main(["--file",str(fp)])
            self.assertEqual(result,0,stdout.getvalue()[:450])
            self.assertNotIn(str(fp),stdout.getvalue())
            self.assertNotIn("ix:nonFraction",stdout.getvalue())
            self.assertEqual(fp.read_bytes(),b)
            # No original file persistence in output and no implicit model.
