"""Explicit SEC Streamlit action: no background network, mocked transport only."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from proofinvest import sec_api_client
from proofinvest.sec_agent_review import review_sec_verdict

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
            "status": "calculated_unverified",
            "reason_code": "STRUCTURAL_NUMERIC_COMPARISON_ONLY",
            "growth_pct": "6.43",
            "current_usd": "416161000000", "prior_usd": "391035000000",
            "sec_filing_index": "https://www.sec.gov/Archives/edgar/data/"
                                "320193/000032019325000079/0000320193-25-000079-index.htm",
            "live_api_called": True, "ai_agent_executed": False,
            "authenticated_external_source": False, "source_rights_verified": False,
        }
        verdict.update({
            "schema": "proofinvest.sec-companyfacts-offline.v1",
            "source_kind": "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED",
            "http_request_attempted": True, "official_contest_submission": False,
            "risk_calculated": False,
        })
        verdict["bounded_review"] = review_sec_verdict(verdict)
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict) as func:
            at = screen()
            func.assert_not_called()
            at.button[0].click().run(timeout=15)
            self.assertFalse(at.exception, [str(x.message) for x in at.exception])
            self.assertTrue(any(m.value == "6.43%" for m in at.metric))
            self.assertTrue(any("000032019325000079/" in x.value
                                for x in at.markdown))
            self.assertTrue(any("원문 독립 재인증" in x.value for x in at.caption))
            self.assertTrue(any("규칙 기반, AI Agent 아님" in x.value for x in at.subheader))
            self.assertTrue(any("INDEPENDENT_SEC_SOURCE_AND_RIGHTS_REVIEW" in x.value for x in at.info))
            func.assert_called_once()
            self.assertTrue(func.call_args.kwargs["allow_network"])

    def test_conflict_displays_blocked_trace_without_success_metrics(self):
        verdict = {
            "schema": "proofinvest.sec-companyfacts-offline.v1",
            "status": "conflict", "reason_code": "GROWTH_CLAIM_CONFLICT",
            "source_kind": "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED",
            "growth_pct": "6.43", "current_usd": "416161000000",
            "prior_usd": "391035000000", "live_api_called": True,
            "http_request_attempted": True, "authenticated_external_source": False,
            "source_rights_verified": False, "ai_agent_executed": False,
            "official_contest_submission": False, "risk_calculated": False,
        }
        verdict["bounded_review"] = review_sec_verdict(verdict)
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict):
            at = screen()
            at.button[0].click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertFalse(at.metric)
        self.assertTrue(any("GROWTH_CLAIM_CONFLICT" in x.value for x in at.error))
        self.assertTrue(any("REVIEW_DISPUTED_GROWTH_CLAIM" in x.value for x in at.info))
        self.assertTrue(any("규칙 기반, AI Agent 아님" in x.value for x in at.subheader))

    def test_filing_after_as_of_exposes_review_hold_no_metrics(self):
        verdict = {
            "schema": "proofinvest.sec-companyfacts-offline.v1",
            "status": "unavailable", "reason_code": "FILING_AFTER_AS_OF",
            "source_kind": "SEC_HTTPS_CONCEPT_RESPONSE_NOT_INDEPENDENTLY_CERTIFIED",
            "growth_pct": None, "current_usd": None, "prior_usd": None,
            "sec_filing_index": None,
            "live_api_called": True, "http_request_attempted": True,
            "authenticated_external_source": False, "source_rights_verified": False,
            "ai_agent_executed": False, "official_contest_submission": False,
            "risk_calculated": False,
        }
        verdict["bounded_review"] = review_sec_verdict(verdict)
        with patch.object(sec_api_client, "run_sec_annual_revenue", return_value=verdict):
            at = screen()
            at.button[0].click().run(timeout=15)
        self.assertFalse(at.exception)
        self.assertFalse(at.metric)
        self.assertTrue(any("FILING_AFTER_AS_OF" in x.value for x in at.error))
        self.assertTrue(any("REVIEW_FILING_DATE_PERIOD_OR_SOURCE" in x.value
                            for x in at.info))

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
