"""SEC HTTPS adapter tests: every request mocked; zero live SEC traffic."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import urllib.error

from proofinvest import sec_api_client as client
from proofinvest.sec_companyfacts import TAG

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/sec_apple_fy2025_curated_companyfacts.json"
ARGS = dict(
    cik="0000320193", accession="0000320193-25-000079",
    current_end="2025-09-27", prior_end="2024-09-28",
    as_of="2025-11-01", allow_network=True,
    user_agent="ProofInvest Research team contact@proofinvest.org",
)


def concept_json():
    fixture = json.loads(FIXTURE.read_text(encoding="utf8"))
    return {
        "cik": fixture["cik"],
        "taxonomy": "us-gaap",
        "tag": TAG,
        "units": fixture["facts"]["us-gaap"][TAG]["units"],
    }


class FakeHTTPResponse:
    def __init__(self, payload=None, *, status=200, url=None,
                 content_type="application/json; charset=utf-8", size=None):
        self.raw = (json.dumps(concept_json() if payload is None else payload)
                    .encode("utf8") if not isinstance(payload, bytes) else payload)
        self.status = status
        self.url = url
        self.headers = {"Content-Type": content_type}
        if size is not None:
            self.headers["Content-Length"] = str(size)

    def geturl(self):
        return self.url or (
            "https://data.sec.gov/api/xbrl/companyconcept/"
            "CIK0000320193/us-gaap/"
            + TAG + ".json"
        )

    def read(self, n):
        return self.raw[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SecHttpAdapterTests(TestCase):
    def test_no_opt_in_never_opens_socket(self):
        with patch.object(client, "_open_once", side_effect=AssertionError("NETWORK")) as opened:
            v = client.run_sec_annual_revenue(**(ARGS | {"allow_network": False}))
            self.assertEqual(v["reason_code"], "NETWORK_OPT_IN_REQUIRED")
            self.assertFalse(v["live_api_called"])
            opened.assert_not_called()

    def test_blank_or_placeholder_contact_blocks_before_network(self):
        for contact in ("", "ProofInvest bot@example.com",
                        "ProofInvest bot@example.invalid",
                        "ProofInvest bot@contact.test", "Something\nHeader: inject"):
            with self.subTest(contact=contact), patch.object(
                    client, "_open_once", side_effect=AssertionError("NETWORK")) as opened:
                v = client.run_sec_annual_revenue(**(ARGS | {"user_agent": contact}))
                self.assertEqual(v["reason_code"], "VALID_SEC_USER_AGENT_REQUIRED")
                opened.assert_not_called()

    def test_single_sec_request_and_verification(self):
        requests = []
        def fake(request, *, timeout):
            requests.append((request, timeout))
            return FakeHTTPResponse()
        with patch.object(client, "_open_once", side_effect=fake):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["growth_pct"], "6.43")
        self.assertEqual(v["status"], "calculated_unverified")
        self.assertTrue(v["live_api_called"])
        self.assertFalse(v["authenticated_external_source"])
        self.assertFalse(v["source_rights_verified"])
        self.assertFalse(v["ai_agent_executed"])
        self.assertEqual(len(requests), 1)
        req, timeout = requests[0]
        self.assertEqual(req.full_url,
                         "https://data.sec.gov/api/xbrl/companyconcept/"
                         "CIK0000320193/us-gaap/" + TAG + ".json")
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.headers["User-agent"], ARGS["user_agent"])
        self.assertEqual(timeout, 12)

    def test_prior_to_filing_blocks_claim_as_future(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse()):
            v = client.run_sec_annual_revenue(**(ARGS | {"as_of": "2025-10-30"}))
        self.assertEqual(v["reason_code"], "FILING_AFTER_AS_OF")
        self.assertIsNone(v["growth_pct"])

    def test_wrong_issuer_accession_fails_before_network(self):
        with patch.object(client, "_open_once", side_effect=AssertionError("NETWORK")) as opened:
            v = client.run_sec_annual_revenue(**(
                ARGS | {"accession": "9999999999-25-000079"}))
            self.assertEqual(v["reason_code"], "INVALID_TARGET")
            opened.assert_not_called()

    def test_sec_429_no_retry_and_no_metrics(self):
        calls = []
        def fake(request, *, timeout):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {}, None)
        with patch.object(client, "_open_once", side_effect=fake):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_NETWORK_OR_HTTP_ERROR")
        self.assertIsNone(v["growth_pct"])
        self.assertEqual(len(calls), 1)

    def test_https_response_redirect_is_rejected(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(
                url="https://thirdparty.example/redirect")):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "UNEXPECTED_RESPONSE_URL")

    def test_wrong_content_type_is_rejected(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(
                content_type="text/html")):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_INVALID_MEDIA_TYPE")

    def test_header_oversize_rejected_before_body(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(
                size=client.MAX_RESPONSE_BYTES + 1)):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_RESPONSE_SIZE_LIMIT")

    def test_actual_body_oversize_rejected(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(
                payload=b" " * (client.MAX_RESPONSE_BYTES + 1))):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_RESPONSE_SIZE_LIMIT")

    def test_malformed_json_rejected(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(
                payload=b"{bad json")):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_INVALID_JSON")

    def test_deeply_nested_json_does_not_crash(self):
        raw = b"[" * 1800 + b"null" + b"]" * 1800
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(payload=raw)):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "SEC_INVALID_JSON")

    def test_wrong_cik_and_wrong_taxonomy_or_concept(self):
        for mutate, expected in [
            ({"cik": 12}, "SEC_CIK_MISMATCH"),
            ({"taxonomy": "ifrs-full"}, "SEC_CONCEPT_MISMATCH"),
            ({"tag": "NetIncomeLoss"}, "SEC_CONCEPT_MISMATCH"),
            ({"units": None}, "SEC_MISSING_UNITS"),
        ]:
            with self.subTest(mutate=mutate):
                body = concept_json() | mutate
                with patch.object(client, "_open_once", return_value=FakeHTTPResponse(body)):
                    v = client.run_sec_annual_revenue(**ARGS)
                self.assertEqual(v["reason_code"], expected)

    def test_no_valid_annual_data_rejected(self):
        body = concept_json()
        body["units"]["USD"][0]["form"] = "10-Q"
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse(body)):
            v = client.run_sec_annual_revenue(**ARGS)
        self.assertEqual(v["reason_code"], "ANNUAL_FACTS_UNAVAILABLE")

    def test_claim_conflict_after_real_shape_fetch(self):
        with patch.object(client, "_open_once", return_value=FakeHTTPResponse()):
            v = client.run_sec_annual_revenue(**(ARGS | {"claimed_growth_pct": "30"}))
        self.assertEqual(v["status"], "conflict")
        self.assertEqual(v["reason_code"], "GROWTH_CLAIM_CONFLICT")

    def test_cli_defaults_off_even_if_contact_present(self):
        cliargs = [
            "--cik", ARGS["cik"], "--accession", ARGS["accession"],
            "--current-end", ARGS["current_end"],
            "--prior-end", ARGS["prior_end"], "--as-of", ARGS["as_of"],
        ]
        captured = io.StringIO()
        with patch.dict(os.environ, {"PROOFINVEST_SEC_USER_AGENT": ARGS["user_agent"]}), \
             patch.object(client, "_open_once", side_effect=AssertionError("NETWORK")) as opened, \
             contextlib.redirect_stdout(captured):
            code = client.main(cliargs)
            opened.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(captured.getvalue())["reason_code"],
                         "NETWORK_OPT_IN_REQUIRED")

    def test_cli_opt_in_fails_closed_without_real_contact(self):
        cliargs = [
            "--allow-network", "--cik", ARGS["cik"],
            "--accession", ARGS["accession"],
            "--current-end", ARGS["current_end"],
            "--prior-end", ARGS["prior_end"], "--as-of", ARGS["as_of"],
        ]
        captured = io.StringIO()
        with patch.dict(os.environ, {"PROOFINVEST_SEC_USER_AGENT": ""}), \
             patch.object(client, "_open_once", side_effect=AssertionError("NETWORK")) as opened, \
             contextlib.redirect_stdout(captured):
            code = client.main(cliargs)
            opened.assert_not_called()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(captured.getvalue())["reason_code"],
                         "VALID_SEC_USER_AGENT_REQUIRED")


if __name__ == "__main__":
    import unittest
    unittest.main()
