"""P243 one-shot Massive local API probe: explicit consent and redacted output."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from unittest import TestCase
from unittest.mock import patch

from scripts import p243_massive_basic_probe as cli
from tests.test_market_provider_massive import fixture

KEY = "SYNTHETICLOCALKEYONLY123"
ARGS = ["--ticker","AAPL","--as-of","2026-10-01"]


class MassiveProbeCliTests(TestCase):
    def capture(self,args):
        lines=[]
        with patch("builtins.print",
                   side_effect=lambda *args,**kwargs:
                       lines.append(" ".join(str(item) for item in args))):
            status=cli.main(args)
        return status,json.loads(lines[-1])

    def test_dry_run_never_reads_secret_or_contacts_provider(self):
        with patch.object(cli, "_https_get",side_effect=AssertionError("NO LIVE GET")), (
            patch.object(cli.getpass,"getpass",side_effect=AssertionError("NO KEY"))):
            rc,out=self.capture(ARGS)
        self.assertEqual(rc,0)
        self.assertEqual(out["status"],"DRY_RUN_NO_REQUEST")
        self.assertEqual(out["network_requests"],0)
        self.assertNotIn("stock_body_sha256",out)

    def test_live_with_noninteractive_terminal_blocks_zero_gets(self):
        with patch.object(cli.sys.stdin,"isatty",return_value=False), (
            patch.object(cli, "_https_get",side_effect=AssertionError("NO REQUEST"))):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["network_requests"],0)

    def test_declined_live_request_makes_zero_requests(self):
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value="NO")), (
            patch.object(cli, "_https_get",side_effect=AssertionError("NO REQUEST"))):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["reason_code"],"OWNER_DECLINED")

    def test_one_stock_one_actual_ndx_and_redacted_receipt(self):
        seen=[]
        def fake_get(url):
            seen.append(url)
            if "/ticker/I:NDX/" in url:
                return fixture("I:NDX",index=True)
            return fixture("AAPL")
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=cli._APPROVAL)), (
            patch.object(cli.getpass,"getpass",return_value=KEY)), (
            patch.object(cli,"_https_get",side_effect=fake_get)):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,0,out)
        self.assertEqual(out["network_requests"],2)
        self.assertEqual(out["stock_points"],65)
        self.assertEqual(out["index_points"],65)
        self.assertFalse(out["market_data_rights_verified"])
        self.assertFalse(out["commercial_reuse_allowed"])
        self.assertEqual(len(seen),2)
        self.assertIn("/ticker/AAPL/",seen[0])
        self.assertIn("/ticker/I:NDX/",seen[1])
        self.assertNotIn(KEY,json.dumps(out))
        self.assertNotIn("apiKey",json.dumps(out))
        self.assertNotIn("close_observations",json.dumps(out))

    def test_bad_stock_reply_cannot_trigger_ndx_call_or_retry(self):
        urls=[]
        def fake_get(url):
            urls.append(url)
            return b'{"status":"ERROR"}'
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=cli._APPROVAL)), (
            patch.object(cli.getpass,"getpass",return_value=KEY)), (
            patch.object(cli,"_https_get",side_effect=fake_get)):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["network_requests"],1)
        self.assertEqual(len(urls),1)
        self.assertNotIn(KEY,json.dumps(out))

    def test_redacted_http_403_no_second_request(self):
        def fail(url):
            raise HTTPError(url,403,"SECRET "+KEY,{},None)
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=cli._APPROVAL)), (
            patch.object(cli.getpass,"getpass",return_value=KEY)), (
            patch.object(cli,"_https_get",side_effect=fail)):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["http_status"],403)
        self.assertEqual(out["failed_stage"],"stock")
        self.assertEqual(out["network_requests"],1)
        self.assertNotIn(KEY,json.dumps(out))

    def test_unknown_error_does_not_expose_key(self):
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=cli._APPROVAL)), (
            patch.object(cli.getpass,"getpass",return_value=KEY)), (
            patch.object(cli,"_https_get",side_effect=ValueError(KEY))):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["reason_code"],"PARSER_OR_RESPONSE_UNAVAILABLE")
        self.assertNotIn(KEY,json.dumps(out))

    def test_index_network_error_after_stock(self):
        calls=[]
        def fake(url):
            calls.append(url)
            if len(calls)==2:
                raise URLError(KEY)
            return fixture("AAPL")
        with patch.object(cli.sys.stdin,"isatty",return_value=True), (
            patch.object(cli.sys.stdout,"isatty",return_value=True)), (
            patch("builtins.input",return_value=cli._APPROVAL)), (
            patch.object(cli.getpass,"getpass",return_value=KEY)), (
            patch.object(cli,"_https_get",side_effect=fake)):
            rc,out=self.capture(ARGS+["--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["failed_stage"],"index")
        self.assertEqual(out["network_requests"],2)
        self.assertEqual(out["reason_code"],"NETWORK_OR_TLS_UNAVAILABLE")
        self.assertNotIn(KEY,json.dumps(out))

    def test_bad_date_blocks_before_approval(self):
        with patch.object(cli,"_https_get",side_effect=AssertionError("REQUEST")), (
            patch.object(cli.getpass,"getpass",side_effect=AssertionError("KEY"))):
            rc,out=self.capture(["--ticker","AAPL","--as-of","2099-12-31","--live"])
        self.assertEqual(rc,2)
        self.assertEqual(out["network_requests"],0)


if __name__ == "__main__":
    import unittest
    unittest.main()
