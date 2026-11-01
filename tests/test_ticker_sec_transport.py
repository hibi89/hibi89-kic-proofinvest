"""P99 bounded mocked SEC source chain (never makes external requests)."""
from __future__ import annotations
import json
from hashlib import sha256
import unittest
from unittest.mock import patch
import urllib.error

from proofinvest import ticker_sec_transport as t
from tests.test_ticker_research_intake import mapping, submissions

UA = "KUODRA synthetic-test researcher@mockunit.dev"


class Response:
    def __init__(self, raw, url, media="application/json", status=200,
                 content_length=None):
        self.raw, self.url, self.status = raw, url, status
        self.headers = {"Content-Type": media}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.url
    def read(self, count):
        return self.raw[:count]


def payloads():
    filing = (t.SEC_ARCHIVE + "/1045810/000104581025000020/annual2025.htm")
    return {
        t.MAP_URL: Response(mapping(), t.MAP_URL),
        t.SEC_API + "/submissions/CIK0001045810.json": Response(
            submissions(), t.SEC_API + "/submissions/CIK0001045810.json"),
        t.SEC_API + "/api/xbrl/companyfacts/CIK0001045810.json": Response(
            json.dumps({"cik": 1045810, "facts": {"us-gaap": {"SyntheticRevenue": {}}}}).encode(),
            t.SEC_API + "/api/xbrl/companyfacts/CIK0001045810.json"),
        filing: Response(b"<html>synthetic fixture only</html>", filing, media="text/html"),
    }


class SingleTickerTransportTests(unittest.TestCase):
    def collect(self, **changes):
        args = dict(ticker="NVDA", as_of="2025-10-16", user_agent=UA,
                    allow_network=True, acknowledge_four_requests=True)
        return t.collect_ticker_sec_sources(**(args | changes))

    def test_no_http_default_opt_in_and_double_ack(self):
        with patch.object(t, "_open_once", side_effect=AssertionError("SOCKET")) as op:
            for args in (dict(), dict(allow_network=False),
                         dict(allow_network=True),
                         dict(acknowledge_four_requests=True)):
                report, raws = t.collect_ticker_sec_sources(
                    ticker="NVDA", as_of="2025-10-16", **args
                )
                self.assertEqual(report["status"], "unavailable")
                self.assertEqual(report["http_requests_attempted"], 0)
                self.assertIsNone(raws)
            op.assert_not_called()

    def test_real_user_agent_required_and_invalid_input_before_network(self):
        with patch.object(t, "_open_once", side_effect=AssertionError("SOCKET")) as op:
            for agent in ("", "bot@example.com", "Bot unit@test.invalid"):
                result, data = self.collect(user_agent=agent)
                self.assertEqual(result["reason_code"], "GENUINE_SEC_CONTACT_REQUIRED")
                self.assertIsNone(data)
            for change in (dict(ticker="../NVDA"), dict(ticker="bad ticker"),
                           dict(as_of="2025-13-90")):
                result, data = self.collect(**change)
                self.assertEqual(result["http_requests_attempted"], 0)
                self.assertIsNone(data)
            op.assert_not_called()

    def test_four_exact_urls_and_no_more_requests(self):
        src = payloads()
        requests = []
        def fake(request, *, timeout):
            requests.append((request.full_url, timeout, request.headers["User-agent"]))
            return src[request.full_url]
        with patch.object(t, "_open_once", side_effect=fake), patch.object(
                t.time, "sleep", return_value=None) as sleep:
            report, data = self.collect()
        self.assertEqual(report["status"], "four_sec_responses_in_memory_unverified")
        self.assertEqual(report["http_requests_attempted"], 4)
        self.assertEqual([x[0] for x in requests], list(src))
        self.assertEqual([x[1] for x in requests], [12] * 4)
        self.assertEqual([x[2] for x in requests], [UA] * 4)
        self.assertEqual(sleep.call_count, 3)
        self.assertEqual(report["selected_10k_accession"], "0001045810-25-000020")
        self.assertEqual(report["source_sha256"]["ticker_map"],
                         sha256(mapping()).hexdigest())
        self.assertEqual(data["original_10k"], src[list(src)[3]].raw)
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["point_in_time_verified"])
        self.assertFalse(report["source_rights_verified"])
        self.assertFalse(report["full_a_b_c_ready"])
        self.assertFalse(report["trade_executed"])

    def test_unknown_ticker_fails_after_one_request_and_discards_bytes(self):
        with patch.object(t, "_open_once", return_value=payloads()[t.MAP_URL]) as opened:
            result, data = self.collect(ticker="FAKE")
        self.assertEqual(result["stage"], "ticker_map")
        self.assertEqual(result["http_requests_attempted"], 1)
        self.assertEqual(result["reason_code"], "SOURCE_IDENTITY_OR_DATA_INVALID")
        self.assertIsNone(data)
        self.assertEqual(opened.call_count, 1)

    def test_wrong_submissions_cik_stops_before_companyfacts(self):
        src = payloads()
        wrong = json.loads(submissions())
        wrong["cik"] = 2
        key = t.SEC_API + "/submissions/CIK0001045810.json"
        src[key] = Response(json.dumps(wrong).encode(), key)
        seen = []
        def fake(req, *, timeout):
            seen.append(req.full_url)
            return src[req.full_url]
        with patch.object(t, "_open_once", side_effect=fake), patch.object(t.time, "sleep"):
            result, data = self.collect()
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertIsNone(data)
        self.assertEqual(len(seen), 2)
        self.assertEqual(result["stage"], "submissions")

    def test_malformed_accession_fails_before_facts(self):
        src = payloads()
        wrong = json.loads(submissions())
        # A valid third-party accession is allowed for this issuer.
        # Malformed identifiers must still stop before CompanyFacts.
        wrong["filings"]["recent"]["accessionNumber"][1] = "0000999999-25-NOTDIG"
        url = t.SEC_API + "/submissions/CIK0001045810.json"
        src[url] = Response(json.dumps(wrong).encode(), url)
        with patch.object(t, "_open_once", side_effect=lambda req, **_: src[req.full_url]), patch.object(t.time, "sleep"):
            result, data = self.collect()
        self.assertEqual(result["stage"], "submissions")
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertIsNone(data)

    def test_wrong_companyfacts_cik_stops_before_original(self):
        src = payloads()
        url = t.SEC_API + "/api/xbrl/companyfacts/CIK0001045810.json"
        src[url] = Response(json.dumps({"cik": 7, "facts": {"us-gaap": {}}}).encode(), url)
        seen = []
        def fake(req, **_):
            seen.append(req.full_url)
            return src[req.full_url]
        with patch.object(t, "_open_once", side_effect=fake), patch.object(t.time, "sleep"):
            result, data = self.collect()
        self.assertEqual(result["reason_code"], "COMPANYFACTS_CIK_MISMATCH")
        self.assertEqual(result["http_requests_attempted"], 3)
        self.assertEqual(len(seen), 3)
        self.assertIsNone(data)

    def test_sec_429_never_retries_and_no_secret_in_output(self):
        src = payloads()
        seen = []
        def fake(req, **_):
            seen.append(req.full_url)
            if len(seen) == 2:
                raise urllib.error.HTTPError(req.full_url, 429, "No", {}, None)
            return src[req.full_url]
        with patch.object(t, "_open_once", side_effect=fake), patch.object(t.time, "sleep"):
            result, data = self.collect()
        self.assertEqual(result["reason_code"], "SEC_RATE_LIMITED_429")
        self.assertEqual(result["http_requests_attempted"], 2)
        self.assertIsNone(data)
        self.assertEqual(len(seen), 2)
        self.assertNotIn(UA, json.dumps(result))

    def test_sec_403_no_retry_on_first_request(self):
        with patch.object(t, "_open_once", side_effect=lambda req, **_: (
                (_ for _ in ()).throw(
                    urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)))) as opened:
            result, data = self.collect()
        self.assertEqual(result["reason_code"], "SEC_ACCESS_DENIED_403")
        self.assertEqual(result["http_requests_attempted"], 1)
        self.assertIsNone(data)
        self.assertEqual(opened.call_count, 1)

    def test_redirect_media_and_response_size_fail_closed(self):
        cases = [
            Response(mapping(), "https://other.example/files/company_tickers.json"),
            Response(mapping(), t.MAP_URL, media="text/plain"),
            Response(mapping(), t.MAP_URL, content_length=str(t.MAX_MAP_BYTES + 1)),
            Response(b"x" * (t.MAX_MAP_BYTES + 1), t.MAP_URL)
        ]
        for response in cases:
            with self.subTest(raw=response.raw[:8], media=response.headers.get("Content-Type")):
                with patch.object(t, "_open_once", return_value=response) as opened:
                    report, data = self.collect()
                self.assertEqual(report["http_requests_attempted"], 1)
                self.assertIsNone(data)
                self.assertEqual(opened.call_count, 1)

    def test_url_allowlist_and_unsafe_original_without_http(self):
        self.assertFalse(t._source_url_allowed(
            "https://data.sec.gov.attacker.example/submissions/CIK0001045810.json",
            "submissions"))
        self.assertFalse(t._source_url_allowed(
            "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000020/../token",
            "original_10k"))
        self.assertFalse(t._source_url_allowed(
            t.MAP_URL + "?ignored=1", "ticker_map"))
        src = payloads()
        doc = json.loads(submissions())
        doc["filings"]["recent"]["primaryDocument"][1] = "annual2025.pdf"
        url = t.SEC_API + "/submissions/CIK0001045810.json"
        src[url] = Response(json.dumps(doc).encode(), url)
        seen = []
        def fake(req, **_):
            seen.append(req.full_url)
            return src[req.full_url]
        with patch.object(t, "_open_once", side_effect=fake), patch.object(t.time, "sleep"):
            result, data = self.collect()
        self.assertEqual(result["reason_code"], "ORIGINAL_DOCUMENT_FORMAT_UNSUPPORTED")
        self.assertEqual(result["http_requests_attempted"], 3)
        self.assertEqual(len(seen), 3)
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()
