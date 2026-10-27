"""Explicit SEC Streamlit action: no background network, mocked transport only."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from proofinvest import sec_api_client

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
LIVE = "SEC 공식 CompanyConcept 조회 — 명시적 1회 실행"


def screen():
    at = AppTest.from_file(str(APP)).run(timeout=15)
    at.selectbox[0].set_value(LIVE).run(timeout=15)
    return at


class SecLiveStreamlitTests(unittest.TestCase):
    def test_opening_sec_mode_makes_zero_http_requests(self):
        with patch.dict(os.environ, {
            "PROOFINVEST_SEC_USER_AGENT": "ProofInvest contact@proofinvest.org"
        }), patch.object(sec_api_client, "_open_once", side_effect=AssertionError("NETWORK")) as opened:
            at = screen()
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertEqual(len(at.button), 1)
            self.assertFalse(at.metric)
            opened.assert_not_called()

    def test_explicit_click_without_contact_holds_and_never_connects(self):
        with patch.dict(os.environ, {"PROOFINVEST_SEC_USER_AGENT": ""}), \
             patch.object(sec_api_client, "_open_once", side_effect=AssertionError("NETWORK")) as opened:
            at = screen()
            at.button[0].click().run(timeout=15)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any("VALID_SEC_USER_AGENT_REQUIRED" in x.value for x in at.error))
            self.assertFalse(at.metric)
            opened.assert_not_called()

    def test_explicit_click_mocked_success_displays_unverified_result(self):
        verdict = {
            "status": "calculated_unverified", "growth_pct": "6.43",
            "current_usd": "416161000000", "prior_usd": "391035000000",
            "sec_filing_index": "https://www.sec.gov/Archives/edgar/data/"
                                "320193/0000320193-25-000079-index.htm",
            "live_api_called": True, "ai_agent_executed": False,
            "authenticated_external_source": False, "source_rights_verified": False,
        }
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict) as func:
            at = screen()
            func.assert_not_called()
            at.button[0].click().run(timeout=15)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any(m.value == "6.43%" for m in at.metric))
            self.assertTrue(any("독립 인증" in x.value for x in at.caption))
            func.assert_called_once()
            self.assertTrue(func.call_args.kwargs["allow_network"])

    def test_success_data_without_confirmed_http_attempt_is_hidden(self):
        verdict = {
            "status": "calculated_unverified", "growth_pct": "6.43",
            "live_api_called": False, "ai_agent_executed": False,
            "authenticated_external_source": False, "source_rights_verified": False,
        }
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict):
            at = screen()
            at.button[0].click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertFalse(at.metric)
        self.assertTrue(at.error)

    def test_unexpected_claim_of_authentication_fails_closed(self):
        verdict = {
            "status": "calculated_unverified", "growth_pct": "6.43",
            "live_api_called": True, "ai_agent_executed": False,
            "authenticated_external_source": True, "source_rights_verified": False,
        }
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict):
            at = screen()
            at.button[0].click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertFalse(at.metric)
        self.assertTrue(any("표시하지 않습니다" in x.value for x in at.error))


if __name__ == "__main__":
    unittest.main()
