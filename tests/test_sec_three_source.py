"""All HTTP mocked: SEC 3-source strict-opt-in provider transport tests."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from proofinvest import sec_three_source as capture
from proofinvest.kic_dl_demo import (
    synthetic_submissions, synthetic_companyfacts, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML


CONTACT = "ProofInvest reviewer reachable@real-reviewer.org"
FIXED = datetime(2025, 10, 16, 12, 0, tzinfo=timezone.utc)
ARGS = dict(
    cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
    current_end="2025-09-30", prior_end="2024-09-30",
    user_agent=CONTACT, allow_network=True, acknowledge_three_requests=True,
)


class _MockResp:
    status = 200

    def __init__(self, url: str, raw: bytes, mime="application/json", length=None):
        self.url = url
        self.raw = raw
        self.headers = {
            "Content-Type": mime,
            "Content-Length": str(len(raw)) if length is None else length,
        }

    def geturl(self):
        return self.url

    def read(self, bound):
        return self.raw[:bound]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _Opener:
    def __init__(self, payload: bytes, fail_url=False, mime="application/json"):
        self.payload = payload
        self.fail_url = fail_url
        self.mime = mime

    def open(self, req, timeout):
        assert req.full_url == f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json"
        return _MockResp(
            req.full_url + ("/redirected" if self.fail_url else ""),
            self.payload, mime=self.mime,
        )


class ThreeSourceSecCaptureTests(unittest.TestCase):
    @contextmanager
    def _fake_success(self):
        raw = json.dumps(synthetic_companyfacts()).encode()
        with (patch.object(capture, "_utcnow", return_value=FIXED),
              patch.object(capture.time, "sleep") as sleep,
              patch.object(capture, "fetch_submissions",
                           return_value=synthetic_submissions()) as subs,
              patch.object(capture, "fetch_original",
                           return_value=(SYNTHETIC_HTML, "text/html")) as original,
              patch.object(capture.urllib.request, "build_opener",
                           return_value=_Opener(raw)) as opener):
            yield subs, original, opener, sleep

    def test_default_no_network_even_with_contact(self):
        with patch.object(capture, "fetch_submissions",
                          side_effect=AssertionError("NETWORK FORBIDDEN")) as f:
            result = capture.run_sec_three_source_review(
                **(ARGS | {"allow_network": False}))
        self.assertEqual(result["reason_code"], "EXPLICIT_THREE_REQUEST_APPROVAL_REQUIRED")
        self.assertEqual(result["http_requests_attempted"], 0)
        f.assert_not_called()

    def test_second_confirmation_required(self):
        with patch.object(capture, "fetch_submissions",
                          side_effect=AssertionError("NETWORK FORBIDDEN")) as f:
            result = capture.run_sec_three_source_review(
                **(ARGS | {"acknowledge_three_requests": False}))
        self.assertEqual(result["http_requests_attempted"], 0)
        f.assert_not_called()

    def test_invalid_contact_or_targets_abort_without_http(self):
        mutations = (
            {"user_agent": "App nobody@example.com"},
            {"cik": "0000000000"},
            {"accession": "0000000001-25-999999"[:-1]},
            {"prior_end": "2025-09-29"},
            {"claimed_growth_pct": "one hundred"},
        )
        for changed in mutations:
            with self.subTest(changed=changed):
                with patch.object(capture, "fetch_submissions",
                                  side_effect=AssertionError("NO HTTP")) as f:
                    res = capture.run_sec_three_source_review(**(ARGS | changed))
                self.assertEqual(res["http_requests_attempted"], 0)
                f.assert_not_called()

    def test_mock_exactly_three_sources_and_transport_provenance_hashes(self):
        with self._fake_success() as (subs, original, opener, sleep):
            result = capture.run_sec_three_source_review(**ARGS)
        self.assertEqual(result["status"], "three_sec_https_responses_captured_unverified")
        self.assertEqual(result["http_requests_attempted"], 3)
        self.assertTrue(result["live_sec_http_called"])
        self.assertEqual(subs.call_count, 1)
        self.assertEqual(original.call_count, 1)
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(result["raw_response_sha256"]["submissions"],
                         hashlib.sha256(synthetic_submissions()).hexdigest())
        self.assertEqual(result["raw_response_sha256"]["original_filing"],
                         hashlib.sha256(SYNTHETIC_HTML).hexdigest())
        self.assertTrue(result["source_uris"]["companyfacts"].startswith("https://data.sec.gov/"))
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["financial_facts_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["capture_bytes_persisted"])
        self.assertEqual(result["numeric_review"]["growth_pct"], "100.00")

    def test_unauthorized_backdated_asof_prevented_by_capture_day(self):
        with patch.object(capture, "_utcnow",
                          return_value=datetime(2025, 10, 14, tzinfo=timezone.utc)):
            with patch.object(capture, "fetch_submissions",
                              return_value=synthetic_submissions()) as subs:
                with patch.object(capture.time, "sleep") as sleep:
                    result = capture.run_sec_three_source_review(**ARGS)
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(result["http_requests_attempted"], 1)
        sleep.assert_not_called()
        subs.assert_called_once()

    def test_missing_requested_filing_stops_after_one_request(self):
        wrong = ARGS | {"accession": "0000000001-25-999999"}
        with patch.object(capture, "_utcnow", return_value=FIXED):
            with patch.object(capture, "fetch_submissions",
                              return_value=synthetic_submissions()) as subs:
                with patch.object(capture.time, "sleep") as sleep:
                    result = capture.run_sec_three_source_review(**wrong)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(result["http_requests_attempted"], 1)
        sleep.assert_not_called()
        subs.assert_called_once()

    def test_wrong_companyfacts_cik_aborts_before_original_fetch(self):
        facts = synthetic_companyfacts()
        facts["cik"] = 2
        with patch.object(capture, "_utcnow", return_value=FIXED):
            with patch.object(capture, "fetch_submissions",
                              return_value=synthetic_submissions()):
                with patch.object(capture.time, "sleep"):
                    with patch.object(capture.urllib.request, "build_opener",
                                      return_value=_Opener(json.dumps(facts).encode())):
                        with patch.object(capture, "fetch_original") as original:
                            result = capture.run_sec_three_source_review(**ARGS)
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertEqual(result["stage"], "companyfacts")
        original.assert_not_called()

    def test_companyfacts_redirect_url_fails_after_two_calls(self):
        facts = json.dumps(synthetic_companyfacts()).encode()
        with patch.object(capture, "_utcnow", return_value=FIXED):
            with patch.object(capture, "fetch_submissions",
                              return_value=synthetic_submissions()):
                with patch.object(capture.time, "sleep"):
                    with patch.object(capture.urllib.request, "build_opener",
                                      return_value=_Opener(facts, fail_url=True)):
                        with patch.object(capture, "fetch_original") as original:
                            result = capture.run_sec_three_source_review(**ARGS)
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertEqual(result["stage"], "companyfacts")
        original.assert_not_called()

    def test_original_fetch_failure_never_yields_success(self):
        with patch.object(capture, "_utcnow", return_value=FIXED):
            with patch.object(capture, "fetch_submissions",
                              return_value=synthetic_submissions()):
                with patch.object(capture.time, "sleep"):
                    with patch.object(capture.urllib.request, "build_opener",
                                      return_value=_Opener(json.dumps(synthetic_companyfacts()).encode())):
                        with patch.object(capture, "fetch_original",
                                          side_effect=ValueError("simulated original failure")):
                            result = capture.run_sec_three_source_review(**ARGS)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["stage"], "original_filing")
        self.assertEqual(result["http_requests_attempted"], 3)
        self.assertFalse(result["source_authenticated"])

    def test_cli_never_runs_network_without_explicit_two_flags(self):
        from io import StringIO
        from contextlib import redirect_stdout
        import os
        output = StringIO()
        with patch.dict(os.environ, {"PROOFINVEST_SEC_USER_AGENT": CONTACT}):
            with patch.object(capture, "fetch_submissions",
                              side_effect=AssertionError("NO HTTP")) as client:
                with redirect_stdout(output):
                    code = capture.main([
                        "--cik", SYNTHETIC_CIK, "--accession", SYNTHETIC_ACCESSION,
                        "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                    ])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["http_requests_attempted"], 0)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
