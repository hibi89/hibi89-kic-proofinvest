"""P72 evidence brief proves only manual web numbers, never actual SEC originals."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import unittest
from unittest.mock import patch
from proofinvest import sec_primary_web_brief as b

class WebBriefTests(unittest.TestCase):
    def test_28_cells_and_source_guard(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")) as net:
            report=b.build_web_only_brief()
        net.assert_not_called()
        self.assertEqual(report["manual_cells_checked"],28)
        self.assertEqual(len(report["metrics"]),14)
        self.assertEqual(report["metrics"][0]["fy2025"],"416161")
        self.assertEqual(report["analysis"]["revenue_growth_pct"],"6.43")
        self.assertEqual(report["analysis"]["receivables_minus_revenue_growth_pp"],"12.63")
        self.assertEqual(report["workflow_state"],"ORIGINAL_SEC_BYTES_REQUIRED_GUARD_NOT_RUN")
        self.assertTrue(all(v is False for v in report["unverified"].values()))

    def test_html_no_script_and_all_metrics(self):
        html=b.render_web_only_brief_html(b.build_web_only_brief())
        self.assertEqual(html.count("<tr><th>"),14)
        self.assertIn("ORIGINAL UNVERIFIED",html)
        self.assertIn("GUARD NOT RUN",html)
        self.assertNotIn("<script",html)

    def test_forged_authentication_or_changed_number_is_rejected(self):
        report=b.build_web_only_brief()
        for field,value in (("source_authenticated",True),("guard_executed",True)):
            altered=deepcopy(report)
            altered["unverified"][field]=value
            with self.assertRaisesRegex(ValueError,"WEB_BRIEF_UNTRUSTED"):
                b.render_web_only_brief_html(altered)
        altered=deepcopy(report)
        altered["metrics"][0]["fy2025"]="999999"
        with self.assertRaisesRegex(ValueError,"WEB_BRIEF_UNTRUSTED"):
            b.render_web_only_brief_html(altered)

    def test_both_cli_formats_without_external_http(self):
        with patch("urllib.request.urlopen",side_effect=AssertionError("NO_NETWORK")) as net:
            output=StringIO()
            with redirect_stdout(output):
                self.assertEqual(b.main(["--format","json"]),0)
            self.assertEqual(json.loads(output.getvalue())["manual_cells_checked"],28)
            output=StringIO()
            with redirect_stdout(output):
                self.assertEqual(b.main(["--format","html"]),0)
            self.assertIn("<!doctype html>",output.getvalue())
        net.assert_not_called()
