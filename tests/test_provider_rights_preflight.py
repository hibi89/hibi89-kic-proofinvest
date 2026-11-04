"""P112 supply/rights separation, no HTTP, no quotes, no credential input."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch
from proofinvest.provider_rights_preflight import evaluate_provider, main


class ProviderRightsPreflightTests(unittest.TestCase):
    def test_all_five_candidates_and_four_real_use_cases_fail_closed(self):
        for vendor in ("massive", "twelve_data", "fred", "nasdaq_gids", "nasdaq_data_link"):
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

    def test_p125_official_terms_blockers_are_specific_not_universal_licenses(self):
        expected = {
            "massive": "PERSONAL_SUBSCRIPTION_EXCLUDES_BUSINESS_AND_THIRD_PARTY_APPLICATION",
            "twelve_data": "FREE_TIER_COMMERCIAL_USE_PROHIBITED",
            "fred": "FRED_API_AI_SYSTEM_USE_RESTRICTIONS_APPLY",
            "nasdaq_gids": "GIDS_NEW_CLIENT_DELAYED_LICENSE_NOT_OFFERED_SINCE_2026_09_01",
        }
        for provider, issue in expected.items():
            with self.subTest(provider=provider):
                r = evaluate_provider(provider=provider,
                                      intended_use="contest_judge_demo")
                self.assertEqual(r["public_terms_reviewed_kst"], "2026-11-03")
                self.assertIn(issue, r["license_blocker_codes"])
                self.assertTrue(r["official_terms_url"].startswith("https://"))
                self.assertTrue(r["official_secondary_url"].startswith("https://"))
                self.assertTrue(r["required_next_evidence"])
                for key in ("intended_use_is_already_licensed",
                            "ai_system_use_rights_verified",
                            "exact_instrument_and_lookback_coverage_verified",
                            "source_update_time_verified",
                            "request_execution_authorized",
                            "redistribution_permission_verified",
                            "owner_network_approval_received"):
                    self.assertIs(r[key], False, (provider, key))
                self.assertEqual(r["network_requests_executed"], 0)

    def test_nasdaq_data_link_2026_terms_stay_blocked_without_order_form(self):
        for use in ("internal_research", "contest_judge_demo",
                    "public_dashboard", "commercial_product"):
            with self.subTest(use=use):
                r = evaluate_provider(provider="nasdaq_data_link",
                                      intended_use=use)
                self.assertEqual(r["public_terms_reviewed_kst"], "2026-11-05")
                self.assertEqual(r["published_ndx_coverage"],
                                 "EXACT_NDX_DATASET_COVERAGE_UNCONFIRMED")
                self.assertIn(
                    "2026_11_01_NASDAQ_DATA_LINK_TERMS_IN_EFFECT",
                    r["license_blocker_codes"],
                )
                self.assertIn(
                    "LICENSE_ORDER_FORM_AND_ACCOUNT_ENTITLEMENT_REQUIRED",
                    r["license_blocker_codes"],
                )
                self.assertIn(
                    "EXTERNAL_DERIVED_ANALYTICS_AND_SAAS_RIGHTS_NOT_GRANTED_BY_DEFAULT",
                    r["license_blocker_codes"],
                )
                self.assertEqual(r["official_terms_url"],
                                 "https://data.nasdaq.com/about/terms")
                self.assertFalse(r["request_execution_authorized"])
                self.assertFalse(r["ai_system_use_rights_verified"])
                self.assertFalse(r["redistribution_permission_verified"])
                self.assertEqual(r["network_requests_executed"], 0)
                self.assertEqual(r["guard_decision"], "HOLD")

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
