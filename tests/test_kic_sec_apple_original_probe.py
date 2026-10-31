"""SEC probe safety contract without performing any live requests."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from scripts.kic_sec_apple_original_probe import (
    SOURCES, USER_AGENT, bounded_get, ALLOWED_HOSTS,
)


class OriginalProbeContractTests(unittest.TestCase):
    def test_exact_official_urls_and_bounded_request_budget(self):
        self.assertEqual(len(SOURCES), 3)
        self.assertEqual(len({s[1] for s in SOURCES}), 3)
        self.assertIn("github.com/hibi89/hibi89-kic-proofinvest", USER_AGENT)
        self.assertEqual(ALLOWED_HOSTS, {"data.sec.gov", "www.sec.gov"})
        self.assertNotIn("Bearer", USER_AGENT)
        self.assertNotIn("@", USER_AGENT)

    def test_reject_non_sec_host_without_opening_network(self):
        def never(*args, **kwargs):
            raise AssertionError("EXTERNAL_NETWORK_CALLED")
        for url in ("http://data.sec.gov/submissions/a.json",
                    "https://evil.example/secret",
                    "https://data.sec.gov:444/submissions/a.json",
                    "https://data.sec.gov@evil.example/steal"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                bounded_get(url, 100, opener=never)

    def test_bounded_read_and_declared_http_user_agent(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = SOURCES[0][1]
        response.read.return_value = b'{"cik":320193}'
        def fake(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.get_header("User-agent"), USER_AGENT)
            self.assertEqual(timeout, 20)
            return response
        self.assertEqual(bounded_get(SOURCES[0][1], 100, opener=fake),
                         b'{"cik":320193}')
        response.read.return_value = b"X" * 101
        with self.assertRaisesRegex(ValueError, "SIZE_BLOCKED"):
            bounded_get(SOURCES[0][1], 100, opener=fake)


if __name__ == "__main__":
    unittest.main()
