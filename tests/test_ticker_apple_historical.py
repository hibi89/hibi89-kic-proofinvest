"""P126 public Apple FY2025 manual-record case in existing ticker flow."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_apple_historical import (
    review_apple_fy2025_historical, _blocked,
)
from proofinvest import ticker_apple_historical as historical


class AppleHistoricalTickerTests(unittest.TestCase):
    def test_historical_real_reported_manual_numbers_and_guard_hold(self):
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("REAL SEC HTTP FORBIDDEN")) as network, (
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("ANY EXTERNAL HTTP FORBIDDEN"))
        ):
            report = review_apple_fy2025_historical(
                ticker="AAPL", as_of="2025-11-01")
        network.assert_not_called()
        self.assertEqual(report["status"], "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED", report)
        self.assertEqual(report["ticker"], "AAPL")
        self.assertEqual(report["issuer_cik"], "0000320193")
        self.assertEqual(report["accession"], "0000320193-25-000079")
        self.assertEqual(report["filed_at"], "2025-10-31")
        self.assertEqual(report["fiscal_end"], "2025-09-27")
        self.assertEqual(report["sales_2025_usd_millions"], "416161")
        self.assertEqual(report["sales_2024_usd_millions"], "391035")
        self.assertEqual(report["sales_growth_pct"], "6.43")
        self.assertEqual(report["cashflow_minus_capex_2025_usd_millions"], "98767")
        self.assertEqual(report["cashflow_minus_capex_2024_usd_millions"], "108807")
        self.assertEqual(report["receivables_minus_sales_growth_pp"], "12.63")
        self.assertEqual(report["guard_policy_preview"]["decision"], "HOLD")
        self.assertTrue(report["fcf_proxy_is_non_gaap"])
        for key in ("source_authenticated", "source_rights_verified",
                    "original_html_authenticated", "raw_sec_api_used",
                    "publisher_origin_automatically_verified",
                    "as_of_latest_filing_researched", "current_filing_status_verified",
                    "guard_executed", "audit_written", "human_approved",
                    "trade_executed", "ai_agent_executed", "official_submission"):
            self.assertIs(report[key], False, key)
        self.assertEqual(report["network_requests"], 0)
        self.assertTrue(report["issuer_hosted_10k_url"].startswith("https://"))
        self.assertTrue(report["issuer_press_release_url"].startswith("https://"))
        self.assertEqual(len(report["manual_10k_json_sha256"]), 64)
        self.assertEqual(len(report["manual_press_json_sha256"]), 64)
        self.assertEqual(len(report["manual_companyfacts_excerpt_sha256"]), 64)
        self.assertNotIn("facts", report)
        self.assertNotIn("original_html", report)
        json.dumps(report, sort_keys=True, allow_nan=False)

    def test_no_filing_lookahead_as_of_before_october_31(self):
        for day in ("2025-10-30", "2024-01-01", "2025-10-01"):
            with self.subTest(day=day), patch.object(
                historical, "_read",
                side_effect=AssertionError("MUST_NOT_READ_PRE_FILING"),
            ):
                r = review_apple_fy2025_historical(ticker="AAPL", as_of=day)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertEqual(r["reason_code"], "FILING_NOT_YET_AVAILABLE_AS_OF")
                self.assertFalse(r["source_authenticated"])

    def test_wrong_issuer_invalid_dates_cannot_load_apple(self):
        for ticker, day in (
            ("NVDA", "2025-11-01"), ("AAPL!","2025-11-01"),
            ("AAPL", "not-a-date"), ("AAPL", "2025-13-01"),
            ("AAPL", "2025-11-01T00:00:00"), ("AAPL", None),
            (None, "2025-11-01"),
        ):
            with self.subTest(ticker=ticker, day=day), patch.object(
                historical, "_read",
                side_effect=AssertionError("INVALID_INPUT_MUST_NOT_READ"),
            ):
                r = review_apple_fy2025_historical(ticker=ticker, as_of=day)
                self.assertEqual(r["status"], "BLOCKED")
                self.assertFalse(r["trade_executed"])

    def test_asof_late_date_remains_historical_not_current(self):
        r = review_apple_fy2025_historical(ticker=" aapl ", as_of="2026-11-03")
        self.assertEqual(r["status"], "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED")
        self.assertEqual(r["filed_at"], "2025-10-31")
        self.assertEqual(r["requested_as_of"], "2026-11-03")
        self.assertFalse(r["as_of_latest_filing_researched"])
        self.assertFalse(r["raw_sec_api_used"])

    def test_tampered_manual_first_party_numbers_fail_closed(self):
        raw = historical._read(historical.TEN_K)
        forged = deepcopy(raw)
        forged["current"]["sales"] = "416162"
        with patch.object(historical, "_read", return_value=forged):
            r = review_apple_fy2025_historical(ticker="AAPL", as_of="2025-11-01")
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["reason_code"], "APPLE_HISTORICAL_REPLAY_UNAVAILABLE")
        self.assertNotIn("sales_2025_usd_millions", r)

    def test_forged_publisher_auth_or_guard_allow_is_refused(self):
        valid = historical.review_apple_fy2025_historical(
            ticker="AAPL", as_of="2025-11-01")
        self.assertEqual(valid["status"], "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED")
        from proofinvest.apple_audited_10k_replay import (
            replay_audited_10k_manual_excerpt as original
        )
        def fake(*args, **kwargs):
            v = original(*args, **kwargs)
            v["source_authenticated"] = True
            return v
        with patch.object(historical, "replay_audited_10k_manual_excerpt", side_effect=fake):
            r = review_apple_fy2025_historical(ticker="AAPL", as_of="2025-11-01")
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["reason_code"], "APPLE_MANUAL_REPLAY_TRUST_CONTRACT_INVALID")
        from proofinvest.guard_sec_adapter import evaluate_sec_guard
        def unsafe(*args, **kwargs):
            v = deepcopy(evaluate_sec_guard(*args, **kwargs))
            v["guard"]["decision"] = "APPROVE"
            return v
        with patch.object(historical, "evaluate_sec_guard", side_effect=unsafe):
            r = review_apple_fy2025_historical(ticker="AAPL", as_of="2025-11-01")
        self.assertEqual(r["status"], "BLOCKED")
        self.assertEqual(r["reason_code"], "GUARD_UNVERIFIED_EVIDENCE_POLICY_CHANGED")


if __name__ == "__main__":
    unittest.main()
