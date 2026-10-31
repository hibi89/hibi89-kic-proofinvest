"""P47 real offline CSV upload bytes -> normalized SEC-bound report, no provider."""
from __future__ import annotations

from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import AS_OF, SYNTHETIC_CIK
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.market_price_csv import market_price_csv_to_json
from proofinvest.market_reality import analyze_market_reality, parse_market_reality_json
from test_market_price_csv import csv_from_fixture
from test_market_reality_integration import _make_report


class MarketPriceCsvIntegrationTests(unittest.TestCase):
    def test_actual_csv_bytes_bound_through_guard_to_html(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-price-p47-") as tmp:
            audit_path = Path(tmp) / "audit.sqlite"
            csv_bytes = csv_from_fixture()
            with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
                report = _make_report(audit_path)
                normalized = market_price_csv_to_json(
                    csv_bytes, issuer_cik=SYNTHETIC_CIK, as_of=AS_OF,
                    symbol="SYNTH", benchmark="NASDAQ_100",
                    return_basis="PRICE_ONLY_CLOSE",
                    source_url="https://example.org/paired-prices",
                    published_at="2025-10-15",
                )
                card = analyze_market_reality(
                    parse_market_reality_json(normalized),
                    expected_issuer_cik=SYNTHETIC_CIK,
                    analysis_as_of=AS_OF,
                    sec_review=report,
                    uploaded_sha256=sha256(normalized).hexdigest(),
                )
                report["market_reality"] = card
                html = render_local_sec_html(report).decode("utf-8")
            net.assert_not_called()
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertTrue(GuardAuditStore(audit_path).verify_chain())
            self.assertEqual(card["source"]["stock"]["sha256_reported"],
                             sha256(csv_bytes).hexdigest())
            self.assertEqual(card["source"]["benchmark"]["sha256_reported"],
                             sha256(csv_bytes).hexdigest())
            self.assertEqual(card["source"]["upload_sha256"],
                             sha256(normalized).hexdigest())
            self.assertEqual(card["sec_revenue_context"]["companyfacts_sha256"],
                             report["source"]["companyfacts_sha256"])
            self.assertIn("Engine A", html)
            self.assertIn(sha256(normalized).hexdigest(), html)
            self.assertIn(sha256(csv_bytes).hexdigest(), html)
            self.assertFalse(card["source_authenticated"])
            self.assertFalse(card["trade_signal"])
            self.assertFalse(card["guard_policy_modified"])


if __name__ == "__main__":
    unittest.main()
