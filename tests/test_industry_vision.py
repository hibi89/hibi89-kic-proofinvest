"""KUODRA Industry Vision — fully offline synthetic, fail-closed regression."""
import copy
import json
import unittest
from unittest.mock import patch

from proofinvest.industry_vision import (
    MAX_UPLOAD_BYTES, analyze_industry_vision, parse_industry_vision_json,
)


def fixture():
    sources = [
        {"id": "target-old", "url": "https://www.sec.gov/Archives/old",
         "published_at": "2025-02-01", "sha256": "a" * 64},
        {"id": "target-now", "url": "https://www.sec.gov/Archives/new",
         "published_at": "2026-02-01", "sha256": "b" * 64},
        {"id": "peer-old", "url": "https://www.sec.gov/Archives/peer-old",
         "published_at": "2025-02-01", "sha256": "c" * 64},
        {"id": "peer-now", "url": "https://www.sec.gov/Archives/peer-new",
         "published_at": "2026-02-01", "sha256": "d" * 64},
        {"id": "sector-old", "url": "https://www.bea.gov/data/industry-old",
         "published_at": "2025-03-01", "sha256": "e" * 64},
        {"id": "sector-now", "url": "https://www.bea.gov/data/industry-new",
         "published_at": "2026-03-01", "sha256": "f" * 64},
    ]
    return {
        "schema": "kuodra.industry-vision.v1",
        "issuer_cik": "0000320193", "as_of": "2026-10-31",
        "industry": "SYNTHETIC_INFORMATION_TECH",
        "prior_period_end": "2024-12-31", "current_period_end": "2025-12-31",
        "target": {"name": "SYNTHETIC_TARGET", "cik": "0000320193",
                   "prior_revenue_usd": "100.00", "current_revenue_usd": "115.00",
                   "prior_source_id": "target-old", "current_source_id": "target-now"},
        "peers": [{"name": "SYNTHETIC_PEER", "cik": "0000000007",
                   "prior_revenue_usd": "100.00", "current_revenue_usd": "130.00",
                   "prior_source_id": "peer-old", "current_source_id": "peer-now"}],
        "industry_series": {"name": "SYNTHETIC_REAL_OUTPUT", "kind": "REAL_GROSS_OUTPUT",
                            "prior_value": "200.00", "current_value": "240.00",
                            "unit": "index_points",
                            "prior_source_id": "sector-old",
                            "current_source_id": "sector-now"},
        "drivers": [{"label": "SYNTHETIC demand factor",
                     "direction": "OPPORTUNITY", "source_ids": ["sector-now"]}],
        "sources": sources,
    }


class IndustryVisionTests(unittest.TestCase):
    def test_real_math_revenue_peers_and_sector_growth(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO NETWORK")) as net:
            report = analyze_industry_vision(fixture(), expected_issuer_cik="0000320193",
                                             analysis_as_of="2026-10-31")
        net.assert_not_called()
        self.assertEqual(report["target"]["growth_pct_reported_input"], "15.00")
        self.assertEqual(report["peers"][0]["growth_pct_reported_input"], "30.00")
        self.assertEqual(report["industry_series"]["growth_pct_reported_input"], "20.00")
        self.assertEqual(report["growth_gap_to_industry_pp"], "-5.00")
        self.assertEqual(report["growth_gap_to_peer_median_pp"], "-15.00")
        self.assertEqual(report["status"], "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["industry_outlook_verified"])
        self.assertFalse(report["ai_generated"])
        self.assertFalse(report["trade_signal"])
        self.assertFalse(report["guard_decision_changed"])

    def test_json_parser_size_nan_and_duplicate(self):
        obj = parse_industry_vision_json(json.dumps(fixture()).encode())
        self.assertEqual(analyze_industry_vision(obj)["status"], "OBSERVED_COMPARISON_UNVERIFIED")
        for b in (b'{"a": 1, "a": 2}', b'{"a": NaN}',
                  b" " * (MAX_UPLOAD_BYTES + 1), b"\xff"):
            with self.subTest(b=b[:10]), self.assertRaises(ValueError):
                parse_industry_vision_json(b)

    def test_industry_and_peer_reports_cannot_precede_period_end(self):
        # Both prior and current series require a release date no earlier
        # than the measurement period. This is chronology, not authentication.
        for source_index in (1, 3, 5):
            data = fixture()
            data["sources"][source_index]["published_at"] = "2025-12-30"
            with self.subTest(index=source_index), self.assertRaisesRegex(
                    ValueError, "SOURCE_PRECEDES_ITS_OBSERVATION_PERIOD_END"):
                analyze_industry_vision(data)
        for source_index in (0, 2, 4):
            data = fixture()
            data["sources"][source_index]["published_at"] = "2024-12-30"
            with self.subTest(index=source_index), self.assertRaisesRegex(
                    ValueError, "SOURCE_PRECEDES_ITS_OBSERVATION_PERIOD_END"):
                analyze_industry_vision(data)

    def test_future_published_and_future_period_block(self):
        a = fixture()
        a["sources"][0]["published_at"] = "2026-11-01"
        with self.assertRaisesRegex(ValueError, "SOURCE_AFTER_RESEARCH_AS_OF"):
            analyze_industry_vision(a)
        a = fixture()
        a["current_period_end"] = "2027-12-31"
        with self.assertRaises(ValueError):
            analyze_industry_vision(a)

    def test_wrong_issuer_or_as_of_no_merge(self):
        with self.assertRaisesRegex(ValueError, "VISION_ISSUER_MISMATCH"):
            analyze_industry_vision(fixture(), expected_issuer_cik="0000000008")
        with self.assertRaisesRegex(ValueError, "VISION_AS_OF_MISMATCH"):
            analyze_industry_vision(fixture(), analysis_as_of="2026-10-30")
        a = fixture()
        a["target"]["cik"] = "0000000008"
        with self.assertRaisesRegex(ValueError, "TARGET_ISSUER_MISMATCH"):
            analyze_industry_vision(a)

    def test_peer_count_differs_from_calculable_growth_sample(self):
        case = fixture()
        report = analyze_industry_vision(case)
        self.assertEqual(report["cohort_evidence"]["peer_count"], 1)
        self.assertEqual(report["peer_growth_observation_count"], 1)
        self.assertEqual(report["peer_growth_sample_scope"],
                         "SPARSE_PEER_GROWTH_UNVERIFIED")
        self.assertEqual(report["peer_median_growth_pct"], "30.00")

        # Peer is listed, but its prior revenue is zero: median is unavailable
        # even while the separate company-versus-industry comparison remains.
        case["peers"][0]["prior_revenue_usd"] = "0"
        no_comparison = analyze_industry_vision(case)
        self.assertEqual(no_comparison["status"], "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertEqual(no_comparison["cohort_evidence"]["peer_count"], 1)
        self.assertEqual(no_comparison["peer_growth_observation_count"], 0)
        self.assertEqual(no_comparison["peer_growth_sample_scope"],
                         "NO_COMPARABLE_PEER_GROWTH")
        self.assertIsNone(no_comparison["peer_median_growth_pct"])
        self.assertIsNone(no_comparison["growth_gap_to_peer_median_pp"])
        self.assertFalse(no_comparison["source_authenticated"])

    def test_three_peers_only_one_usable_does_not_claim_robust_sample(self):
        case = fixture()
        for i in (2, 3):
            case["sources"].extend([
                {
                    "id": f"peer-{i}-old",
                    "url": f"https://www.sec.gov/Archives/peer-{i}-old",
                    "published_at": "2025-02-01", "sha256": str(i) * 64,
                },
                {
                    "id": f"peer-{i}-new",
                    "url": f"https://www.sec.gov/Archives/peer-{i}-new",
                    "published_at": "2026-02-01", "sha256": str(i + 2) * 64,
                },
            ])
            new_peer = dict(case["peers"][0])
            new_peer.update(
                name=f"SYNTHETIC_PEER_{i}", cik=f"{i:010d}",
                prior_source_id=f"peer-{i}-old",
                current_source_id=f"peer-{i}-new",
                prior_revenue_usd="0",
            )
            case["peers"].append(new_peer)
        report = analyze_industry_vision(case)
        self.assertEqual(report["cohort_evidence"]["peer_count"], 3)
        self.assertEqual(report["peer_growth_observation_count"], 1)
        self.assertEqual(report["peer_growth_sample_scope"],
                         "SPARSE_PEER_GROWTH_UNVERIFIED")
        self.assertEqual(report["peer_median_growth_pct"], "30.00")
        self.assertFalse(report["source_authenticated"])

    def test_zero_base_not_invent_growth(self):
        a = fixture()
        a["industry_series"]["prior_value"] = "0"
        result = analyze_industry_vision(a)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["industry_series"]["growth_pct_reported_input"])
        self.assertIsNone(result["growth_gap_to_industry_pp"])

    def test_driver_missing_source_and_duplicate_peer_fail_closed(self):
        a = fixture()
        a["drivers"][0]["source_ids"] = ["not-found"]
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DRIVER_SOURCE"):
            analyze_industry_vision(a)
        a = fixture()
        a["peers"][0]["cik"] = a["target"]["cik"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_COMPANY_CIK"):
            analyze_industry_vision(a)

    def test_peer_and_sector_sources_cannot_impersonate_another_issuer(self):
        for failure in ("target_id", "same_digest", "sector_digest"):
            case = fixture()
            if failure == "target_id":
                case["peers"][0]["prior_source_id"] = "target-old"
            elif failure == "same_digest":
                case["sources"][2]["sha256"] = case["sources"][0]["sha256"]
            else:
                case["sources"][5]["sha256"] = case["sources"][3]["sha256"]
            with self.subTest(failure=failure), self.assertRaisesRegex(
                    ValueError, "COHORT_CROSS_ISSUER_SOURCE_COLLISION"):
                analyze_industry_vision(case)
        report = analyze_industry_vision(fixture())
        self.assertEqual(report["cohort_evidence"]["peer_count"], 1)
        self.assertFalse(report["cohort_evidence"]["source_authenticated"])

    def test_unverifiable_source_url_rejected(self):
        for url in ("http://www.bea.gov", "https://localhost/report",
                    "https://user:pass@www.bea.gov/a",
                    "https://www.bea.gov/?token=secret",
                    "https://www.bea.gov:99999/a"):
            a = fixture()
            a["sources"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                analyze_industry_vision(a)

    def test_unverified_data_cannot_claim_market_share_or_future_returns(self):
        report = analyze_industry_vision(fixture())
        text = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("MARKET_BUBBLE", text)
        self.assertNotIn("APPROVE", text)
        self.assertIn("시장점유율을 계산하지", text)
        self.assertTrue(all(not s["authenticated"] for s in report["sources"]))

    def test_reject_mixed_fiscal_year_or_unknown_industry_kind(self):
        a = fixture()
        a["prior_period_end"] = "2024-06-30"
        with self.assertRaisesRegex(ValueError, "INVALID_ANNUAL_COMPARISON_PERIOD"):
            analyze_industry_vision(a)
        a = fixture()
        a["industry_series"]["kind"] = "MADE_UP_MARKET_CAP"
        with self.assertRaisesRegex(ValueError, "INVALID_INDUSTRY_METRIC"):
            analyze_industry_vision(a)


if __name__ == "__main__":
    unittest.main()
