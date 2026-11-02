"""P112 supply/rights separation, no HTTP, no quotes, no credential input."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
from proofinvest.provider_rights_preflight import evaluate_provider, main


class ProviderRightsPreflightTests(unittest.TestCase):
    def test_all_four_candidates_and_four_real_use_cases_fail_closed(self):
        for vendor in ("massive", "twelve_data", "fred", "nasdaq_gids"):
            for use in ("internal_research", "contest_judge_demo", "public_dashboard", "commercial_product"):
                with self.subTest(vendor=vendor, use=use):
                    r = evaluate_provider(provider=vendor, intended_use=use)
                    self.assertEqual(r["status"], "BLOCKED_VENDOR_RIGHTS_AND_OWNER_APPROVAL_REQUIRED")
                    self.assertEqual(r["guard_decision"], "HOLD")
                    self.assertEqual(r["network_requests_executed"], 0)
                    self.assertFalse(r["data_use_permission_verified"])
                    self.assertFalse(r["derived_analytics_display_permission_verified"])
                    self.assertFalse(r["ndx_identity_independently_verified"])
                    self.assertFalse(r["paid_services_activated"])
                    self.assertFalse(r["trade_executed"])

    def test_public_massive_basic_ndx_listing_not_confused_with_license(self):
        r = evaluate_provider(provider="massive", intended_use="contest_judge_demo")
        self.assertEqual(r["published_ndx_coverage"], "PUBLIC_BASIC_NDX_LISTED")
        self.assertFalse(r["account_entitlement_verified"])
        self.assertFalse(r["redistribution_permission_verified"])

    def test_twelve_data_ndx_basic_remains_unconfirmed(self):
        r = evaluate_provider(provider="twelve_data", intended_use="internal_research")
        self.assertEqual(r["published_ndx_coverage"], "INDEX_API_OFFERED_NDX_BASIC_UNCONFIRMED")

    def test_fred_copyright_and_origin_source_not_licenses(self):
        a = evaluate_provider(provider="fred", intended_use="public_dashboard")
        b = evaluate_provider(provider="nasdaq_gids", intended_use="commercial_product")
        self.assertIn("COPYRIGHT", a["published_ndx_coverage"])
        self.assertIn("LICENSE", b["published_ndx_coverage"])

    def test_invalid_provider_or_usage_cannot_fallback_to_cheaper_plan(self):
        for provider, use in (("qqq", "internal_research"), ("massive", "offline_fixture"),
                              ("MASSIVE", "contest_judge_demo"), (None, "public_dashboard"),
                              ("fred", None)):
            with self.subTest(provider=provider, use=use):
                with self.assertRaises(ValueError):
                    evaluate_provider(provider=provider, intended_use=use)

    def test_cli_redacted_json_exit_blocked_and_no_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("HTTP_FORBIDDEN")):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--provider", "massive", "--use", "contest_judge_demo"])
        self.assertEqual(code, 2)
        obj = json.loads(output.getvalue())
        self.assertEqual(obj["network_requests_executed"], 0)
        self.assertNotIn("api_key", output.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
