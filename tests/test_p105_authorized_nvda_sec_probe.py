"""P105 owner-only SEC command: offline unit checks; never access SEC."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from unittest import TestCase
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from scripts import p105_authorized_nvda_sec_probe as probe
from tests.test_ticker_sec_financial_bridge import valid_case

UA = "KUODRA Unit Test research-unit@fixtures.dev"


class ProbeTests(TestCase):
    def test_reject_unapproved_invalid_contact_date_before_http(self):
        cases = [
            dict(as_of="2026-11-02", user_agent=UA, approved=False),
            dict(as_of="2026-11-02", user_agent="fake", approved=True),
            dict(as_of="2100-01-01", user_agent=UA, approved=True),
            dict(as_of="bad", user_agent=UA, approved=True),
        ]
        with patch.object(probe, "collect_ticker_sec_sources",
                          side_effect=AssertionError("NO_HTTP")) as collector:
            for kw in cases:
                result = probe.verify_nvda_once(**kw)
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertEqual(result["http_requests_attempted"], 0)
            collector.assert_not_called()

    def test_failure_403_receipt_is_redacted_and_no_retry(self):
        receipt = {
            "status": "unavailable", "stage": "ticker_map",
            "reason_code": "SEC_ACCESS_DENIED_403",
            "http_requests_attempted": 1, "contact": UA,
        }
        with patch.object(probe, "collect_ticker_sec_sources",
                          return_value=(receipt, None)) as collect:
            result = probe.verify_nvda_once(
                as_of="2026-11-02", user_agent=UA, approved=True)
        collect.assert_called_once_with(
            ticker="NVDA", as_of="2026-11-02", user_agent=UA,
            allow_network=True, acknowledge_four_requests=True,
        )
        self.assertEqual(result["reason_code"], "SEC_ACCESS_DENIED_403")
        self.assertEqual(result["http_requests_attempted"], 1)
        self.assertEqual(result["stage"], "ticker_map")
        self.assertNotIn(UA, json.dumps(result))
        self.assertFalse(result["raw_sources_saved"])

    def test_success_uses_existing_four_sources_only_and_erases_memory_dict(self):
        receipt, raw = valid_case()
        receipt["ticker"] = "NVDA"
        # Valid fixture has read-only SEC annual revenue while 10-K HTML is
        # generic, so original review remains unavailable/HOLD.
        with patch.object(probe, "collect_ticker_sec_sources",
                          return_value=(receipt, raw)) as collect, \
             patch.object(transport, "_open_once",
                          side_effect=AssertionError("NO_EXTRA_HTTP")) as opened:
            result = probe.verify_nvda_once(
                as_of="2025-10-16", user_agent=UA, approved=True)
        self.assertEqual(collect.call_count, 1)
        opened.assert_not_called()
        self.assertEqual(result["status"], "SEC_RESPONSES_RECEIVED_UNVERIFIED", result)
        self.assertEqual(result["http_requests_attempted"], 4)
        self.assertEqual(result["annual_revenue"]["status"], "REVENUE_CALCULATED_UNVERIFIED")
        self.assertEqual(result["engine_a"], "UNAVAILABLE")
        self.assertEqual(result["engine_c"], "UNAVAILABLE")
        self.assertFalse(result["full_a_b_c_ready"])
        self.assertFalse(result["raw_sources_saved"])
        self.assertFalse(result["guard_executed"])
        self.assertEqual(raw, {})
        self.assertNotIn(UA, json.dumps(result))

    def test_reject_collector_attempts_over_four_and_clear_source(self):
        raw = {"ticker_map": b"X"}
        receipt = {"status": "four_sec_responses_in_memory_unverified",
                   "http_requests_attempted": 5}
        with patch.object(probe, "collect_ticker_sec_sources",
                          return_value=(receipt, raw)):
            result = probe.verify_nvda_once(
                as_of="2026-11-02", user_agent=UA, approved=True)
        self.assertEqual(result["reason_code"], "REQUEST_LIMIT_CONTRACT_INVALID")
        self.assertEqual(raw, {})

    def test_noninteractive_terminal_requires_no_contact_and_no_http(self):
        out=StringIO()
        with patch.object(probe.sys.stdin, "isatty", return_value=False), \
             patch.object(probe, "collect_ticker_sec_sources",
                          side_effect=AssertionError("NO_HTTP")) as collector, \
             redirect_stdout(out):
            code=probe.main([])
        collector.assert_not_called()
        self.assertEqual(code,2)
        self.assertEqual(json.loads(out.getvalue())["reason_code"],
                         "INTERACTIVE_TERMINAL_REQUIRED")

    def test_cli_refusal_has_no_collection_and_no_contact_prompt(self):
        out=StringIO()
        with patch.object(probe.sys.stdin, "isatty", return_value=True), \
             patch("builtins.input", return_value="NO"), \
             patch.object(probe.getpass, "getpass",
                          side_effect=AssertionError("CONTACT_NOT_REQUESTED")), \
             patch.object(probe, "collect_ticker_sec_sources",
                          side_effect=AssertionError("NO_HTTP")) as collector, \
             redirect_stdout(out):
            rc=probe.main([])
        collector.assert_not_called()
        self.assertEqual(rc,2)
        self.assertIn("EXPLICIT_LOCAL_APPROVAL_REQUIRED",out.getvalue())

    def test_masked_contact_not_echoed_to_stdout(self):
        out=StringIO()
        with patch.object(probe.sys.stdin, "isatty", return_value=True), \
             patch("builtins.input", return_value="READ SEC NVDA"), \
             patch.object(probe.getpass, "getpass",
                          return_value="research-unit@fixtures.dev"), \
             patch.object(probe, "verify_nvda_once",
                          return_value=probe._failure("SEC_ACCESS_DENIED_403",
                                                      attempted=1)) as called, \
             redirect_stdout(out):
            rc=probe.main(["--as-of","2026-11-02"])
        self.assertEqual(rc,2)
        self.assertNotIn("research-unit@fixtures.dev",out.getvalue())
        self.assertEqual(called.call_count,1)
        self.assertEqual(called.call_args.kwargs["approved"],True)
        self.assertEqual(called.call_args.kwargs["as_of"],"2026-11-02")


if __name__=="__main__":
    import unittest
    unittest.main()
