"""P44 issuer-bound price/SEC/Guard report and HTML trust integration, offline."""
from __future__ import annotations

from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.market_reality import analyze_market_reality, parse_market_reality_json
from proofinvest.guard_audit import GuardAuditStore
from test_accounting_integrity import fixture as sec_fixture
from test_market_reality import fixture as market_fixture


def _make_report(db):
    facts = json.dumps(sec_fixture(), sort_keys=True).encode()
    inputs = {
        "submissions_json": synthetic_submissions(),
        "companyfacts_json": facts,
        "original_filing": SYNTHETIC_HTML,
        "cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
        "as_of": AS_OF, "collected_at": COLLECTED_AT,
        "current_end": "2025-09-30", "prior_end": "2024-09-30",
        "needle": PHRASE, "audit_db_path": db, "run_id": "p44-market-a",
        "expected_source_sha256": {
            "submissions": sha256(synthetic_submissions()).hexdigest(),
            "companyfacts": sha256(facts).hexdigest(),
            "original_filing": sha256(SYNTHETIC_HTML).hexdigest(),
        },
    }
    return review_local_sec_with_guard(**inputs)


class MarketRealityIntegrationTests(unittest.TestCase):
    def test_market_joins_guard_sec_context_without_changing_audit(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-market-p44-") as home:
            db = Path(home) / "audit.sqlite"
            with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
                report = _make_report(db)
                payload = json.dumps(market_fixture()).encode()
                m = analyze_market_reality(
                    parse_market_reality_json(payload), sec_review=report,
                    uploaded_sha256=sha256(payload).hexdigest(),
                    expected_issuer_cik=SYNTHETIC_CIK, analysis_as_of=AS_OF,
                )
                report["market_reality"] = m
                html = render_local_sec_html(report).decode("utf-8")
            net.assert_not_called()
            self.assertTrue(GuardAuditStore(db).verify_chain())
            self.assertEqual(report["guard"]["decision"], "HOLD")
            # Filing on 2025-10-15 cannot have been known during the
            # synthetic price window ending 2025-10-02.
            self.assertIsNone(m["sec_revenue_context"])
            self.assertEqual(m["sec_context_temporal_status"],
                             "WITHHELD_FILING_NOT_PRIOR_TO_PRICE_WINDOW")
            self.assertFalse(m["point_in_time_backtest_verified"])
            self.assertFalse(m["audit_included"])
            self.assertFalse(m["market_bubble_proven"])
            self.assertIn("Engine A", html)
            self.assertIn("일별 OLS 절편", html)
            self.assertIn("Guard 감사 체인에 시장 회귀 결과가 포함되지는", html)

    def test_html_market_card_rejects_spoofed_trust_and_sec_growth(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-market-p44-") as home:
            report = _make_report(Path(home) / "audit.sqlite")
            raw = json.dumps(market_fixture()).encode()
            report["market_reality"] = analyze_market_reality(
                parse_market_reality_json(raw), sec_review=report,
                uploaded_sha256=sha256(raw).hexdigest(),
            )
            report["market_reality"]["market_bubble_proven"] = True
            with self.assertRaisesRegex(ValueError, "HTML_MARKET_REALITY_TRUST_BLOCKED"):
                render_local_sec_html(report)
            report["market_reality"]["market_bubble_proven"] = False
            report["market_reality"]["sec_revenue_context"] = {
                "growth_pct_calculated_unverified": "999.99",
                "companyfacts_sha256": report["source"]["companyfacts_sha256"],
                "filing_date": report["issuer"]["filing_date"],
                "current_period_end": report["verification"]["current_period_end"],
                "source_authenticated": False,
            }
            with self.assertRaisesRegex(ValueError, "HTML_MARKET_POINT_IN_TIME_BLOCKED"):
                render_local_sec_html(report)
            report["market_reality"]["sec_revenue_context"] = None
            report["market_reality"]["point_in_time_backtest_verified"] = True
            with self.assertRaisesRegex(ValueError, "HTML_MARKET_REALITY_TRUST_BLOCKED"):
                render_local_sec_html(report)

    def test_report_remains_backward_compatible_without_market_upload(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-market-p44-") as home:
            report = _make_report(Path(home) / "audit.sqlite")
            self.assertNotIn("market_reality", report)
            self.assertIn("Guard", render_local_sec_html(report).decode())


if __name__ == "__main__":
    unittest.main()
