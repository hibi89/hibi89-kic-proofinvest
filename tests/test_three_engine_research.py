"""P46: full local SEC Guard -> independent A/B/C evidence report.

All observations and issuer IDs are synthetic. No provider, trades or source
authentication; only the numeric and byte-pin joins are independently checked.
"""
from __future__ import annotations

from hashlib import sha256
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import AS_OF, SYNTHETIC_CIK
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.market_reality import analyze_market_reality, parse_market_reality_json
from proofinvest.three_engine_research import bind_industry_to_sec, summarize_three_engines
from test_industry_vision import fixture as industry_fixture
from test_market_reality import fixture as market_fixture
from test_market_reality_integration import _make_report


def industry_for_report(report):
    data = industry_fixture()
    data["issuer_cik"] = SYNTHETIC_CIK
    data["as_of"] = AS_OF
    data["industry"] = "SYNTHETIC_SECTOR"
    data["target"]["cik"] = SYNTHETIC_CIK
    data["prior_period_end"] = report["verification"]["prior_period_end"]
    data["current_period_end"] = report["verification"]["current_period_end"]
    data["target"]["prior_revenue_usd"] = report["verification"]["prior_amount"]
    data["target"]["current_revenue_usd"] = report["verification"]["current_amount"]
    sources = {x["id"]: x for x in data["sources"]}
    for sid in ("target-old", "target-now"):
        sources[sid]["sha256"] = report["source"]["companyfacts_sha256"]
    for source in data["sources"]:
        source["published_at"] = "2025-10-15"
    return data


class ThreeEngineReportTests(unittest.TestCase):
    def test_genuine_python_e2e_all_three_cards_and_html(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p46-") as home:
            db = Path(home) / "audit.sqlite"
            with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as net:
                report = _make_report(db)
                market_json = json.dumps(market_fixture(), sort_keys=True).encode()
                industry_json = json.dumps(industry_for_report(report), sort_keys=True).encode()
                report["market_reality"] = analyze_market_reality(
                    parse_market_reality_json(market_json),
                    expected_issuer_cik=SYNTHETIC_CIK, analysis_as_of=AS_OF,
                    uploaded_sha256=sha256(market_json).hexdigest(),
                    sec_review=report,
                )
                report["industry_vision"] = bind_industry_to_sec(report, industry_json)
                report["three_engine_summary"] = summarize_three_engines(report)
                rendered = render_local_sec_html(report).decode("utf-8")
            net.assert_not_called()
            self.assertTrue(GuardAuditStore(db).verify_chain())
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertEqual(report["industry_vision"]["sec_revenue_link"]["growth_pct"],
                             report["verification"]["growth_pct"])
            self.assertEqual(report["industry_vision"]["input_sha256"],
                             sha256(industry_json).hexdigest())
            self.assertEqual(report["three_engine_summary"]["all_three_inputs_present"], True)
            self.assertFalse(report["three_engine_summary"]["combined_risk_score_available"])
            self.assertFalse(report["industry_vision"]["source_authenticated"])
            self.assertFalse(report["industry_vision"]["audit_included"])
            self.assertIn("Engine A", rendered)
            self.assertIn("Engine B", rendered)
            self.assertIn("Engine C", rendered)
            self.assertIn("A·B·C 독립 분석 상태", rendered)
            self.assertIn(sha256(industry_json).hexdigest(), rendered)
            self.assertIn("종합 위험점수, 시장 비전 인증", rendered)

    def test_mismatched_period_amount_or_digest_withheld(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p46-") as home:
            report = _make_report(Path(home) / "audit.sqlite")
            for change in ("period", "amount", "digest", "published", "wrongcik"):
                data = industry_for_report(report)
                if change == "period":
                    data["prior_period_end"] = "2024-10-01"
                if change == "amount":
                    data["target"]["current_revenue_usd"] = "999"
                if change == "digest":
                    data["sources"][1]["sha256"] = "f" * 64
                if change == "published":
                    data["sources"][1]["published_at"] = "2025-10-14"
                if change == "wrongcik":
                    data["issuer_cik"] = "0000000002"
                    data["target"]["cik"] = "0000000002"
                with self.subTest(change=change), self.assertRaises(ValueError):
                    bind_industry_to_sec(report, json.dumps(data).encode())
            self.assertEqual(report["guard"]["decision"], "HOLD")
            self.assertNotIn("industry_vision", report)

    def test_forged_industry_sources_or_vision_flags_fail_html(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p46-") as home:
            report = _make_report(Path(home) / "audit.sqlite")
            report["industry_vision"] = bind_industry_to_sec(
                report, json.dumps(industry_for_report(report)).encode())
            for field, value in (("industry_outlook_verified", True),
                                 ("guard_decision_changed", True),
                                 ("audit_included", True)):
                modified = copy.deepcopy(report)
                modified["industry_vision"][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(
                        ValueError, "HTML_INDUSTRY_SEC_CONTEXT_BLOCKED"):
                    render_local_sec_html(modified)
            modified = copy.deepcopy(report)
            modified["industry_vision"]["target"]["current_revenue_usd"] = "9000"
            with self.assertRaisesRegex(ValueError, "HTML_INDUSTRY_SEC_REVENUE_BLOCKED"):
                render_local_sec_html(modified)
            modified = copy.deepcopy(report)
            modified["industry_vision"]["sources"][1]["sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "HTML_INDUSTRY_ORIGINAL_PIN_BLOCKED"):
                render_local_sec_html(modified)

    def test_status_ledger_missing_optional_never_safe(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p46-") as home:
            report = _make_report(Path(home) / "audit.sqlite")
            ledger = summarize_three_engines(report)
            self.assertEqual(ledger["A_market_reality"], "NO_INPUT")
            self.assertEqual(ledger["C_industry_vision"], "NO_INPUT")
            self.assertFalse(ledger["all_three_inputs_present"])
            report["three_engine_summary"] = ledger
            self.assertIn("NO_INPUT", render_local_sec_html(report).decode("utf-8"))
            mutated = copy.deepcopy(report)
            mutated["three_engine_summary"]["combined_risk_score_available"] = True
            with self.assertRaisesRegex(ValueError, "HTML_THREE_ENGINE_LEDGER_BLOCKED"):
                render_local_sec_html(mutated)


if __name__ == "__main__":
    unittest.main()
