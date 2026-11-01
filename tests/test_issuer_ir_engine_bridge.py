"""P108 issuer IR historical B + optional A/C, no SEC/provider network."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest import issuer_ir_engine_bridge as bridge
from proofinvest.issuer_ir_replay import ISSUER_URL, replay
from tests.test_industry_vision import fixture as vision_fixture
from tests.test_market_price_csv import csv_from_fixture


def industry_packet():
    packet = vision_fixture()
    packet["issuer_cik"] = bridge.CIK
    packet["as_of"] = "2025-10-16"
    packet["prior_period_end"] = bridge.PRIOR_END
    packet["current_period_end"] = bridge.CURRENT_END
    packet["target"].update({
        "name": "NVIDIA Corporation", "cik": bridge.CIK,
        "prior_revenue_usd": "60922000000",
        "current_revenue_usd": "130497000000",
    })
    evidence_sha = replay()["evidence_sha256"]
    for src in packet["sources"]:
        src["published_at"] = bridge.IR_RELEASE
        if src["id"].startswith("target-"):
            src["sha256"] = evidence_sha
            src["url"] = ISSUER_URL
    return packet


def valid_market_kwargs():
    return {
        "price_csv": csv_from_fixture(),
        "price_source_url": "https://example.org/operator-supplied-archive",
        "price_published_at": "2025-10-15",
    }


class HistoricalIrThreeEngineBridgeTests(unittest.TestCase):
    def test_historical_only_is_one_real_issuer_b_partial_and_hold(self):
        r = bridge.analyze_historical_ir_engines()
        self.assertEqual(r["status"], "HISTORICAL_PARTIAL_UNAUTHENTICATED")
        self.assertEqual(r["engine_b"]["status"], "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY")
        self.assertEqual(r["engine_b"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(r["engine_b"]["cash_conversion_pct"], "87.94")
        self.assertEqual(r["engine_a"]["status"], "UNAVAILABLE")
        self.assertEqual(r["engine_c"]["status"], "UNAVAILABLE")
        self.assertEqual(r["guard"]["decision"], "HOLD")
        self.assertFalse(r["full_abc_authenticated"])
        self.assertFalse(r["sec_accessed"])
        self.assertEqual(r["network_requests"], 0)
        self.assertFalse(r["trade_executed"])

    def test_local_csv_market_a_real_regression_reused_without_sec(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as network:
            r = bridge.analyze_historical_ir_engines(**valid_market_kwargs())
        network.assert_not_called()
        self.assertEqual(r["engine_a"]["status"], "REPORTED_UNVERIFIED", r)
        self.assertEqual(r["engine_a"]["observations"], 45)
        self.assertEqual(r["engine_a"]["input_sha256"],
                         sha256(csv_from_fixture()).hexdigest())
        self.assertAlmostEqual(float(r["engine_a"]["beta"]), 1.5, places=3)
        self.assertEqual(r["engine_b"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(r["guard"]["decision"], "HOLD")
        self.assertFalse(r["engine_a"]["price_vintage_authenticated"])

    def test_full_optional_a_b_c_are_descriptive_and_all_unverified(self):
        c = json.dumps(industry_packet()).encode()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")):
            r = bridge.analyze_historical_ir_engines(
                **valid_market_kwargs(), industry_json=c)
        self.assertEqual(r["engine_a"]["status"], "REPORTED_UNVERIFIED", r)
        self.assertEqual(r["engine_c"]["status"],
                         "OBSERVED_COMPARISON_UNVERIFIED", r)
        self.assertEqual(r["engine_c"]["peer_count"], 1)
        self.assertEqual(r["engine_c"]["input_sha256"], sha256(c).hexdigest())
        self.assertFalse(r["full_abc_authenticated"])
        self.assertEqual(r["guard"]["decision"], "HOLD")

    def test_wrong_fiscal_period_ir_hash_ticker_amount_and_date_block_c(self):
        for key in ("fiscal", "sha", "ticker", "revenue", "published", "url", "name"):
            with self.subTest(key=key):
                pkt = industry_packet()
                if key == "fiscal":
                    pkt["current_period_end"] = "2025-01-25"
                if key == "sha":
                    pkt["sources"][0]["sha256"] = "a" * 64
                if key == "ticker":
                    pkt["issuer_cik"] = "0000320193"
                    pkt["target"]["cik"] = "0000320193"
                if key == "revenue":
                    pkt["target"]["current_revenue_usd"] = "130497000001"
                if key == "published":
                    pkt["sources"][1]["published_at"] = "2025-03-01"
                if key == "url":
                    pkt["sources"][1]["url"] = "https://example.org/pretend-ir"
                if key == "name":
                    pkt["target"]["name"] = "DIFFERENT COMPANY"
                r = bridge.analyze_historical_ir_engines(
                    industry_json=json.dumps(pkt).encode())
                self.assertEqual(r["engine_c"]["status"], "UNAVAILABLE", (key, r))
                self.assertEqual(r["engine_b"]["status"],
                                 "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY")

    def test_reject_market_before_ir_release_and_malformed_csv(self):
        # Reuse valid 2025-08 price rows, but force a pre-publication session.
        early = csv_from_fixture().replace(b"2025-08-01", b"2025-02-26", 1)
        for args in (
                {"price_csv": early, "price_source_url": "https://example.org/price",
                 "price_published_at": "2025-10-15"},
                {"price_csv": b"malformed", "price_source_url": "https://example.org/price",
                 "price_published_at": "2025-10-15"},
                {"price_csv": csv_from_fixture()},
                {"price_csv": csv_from_fixture(),
                 "price_source_url": "file:///not-allowed",
                 "price_published_at": "2025-10-15"}):
            with self.subTest(args=list(args)):
                r = bridge.analyze_historical_ir_engines(**args)
                self.assertEqual(r["engine_a"]["status"], "UNAVAILABLE")
                self.assertEqual(r["guard"]["decision"], "HOLD")

    def test_missing_ir_and_tamper_never_promote_other_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "issuer.json"
            p.write_bytes(b"not-json")
            r = bridge.analyze_historical_ir_engines(
                evidence_path=p, **valid_market_kwargs(),
                industry_json=json.dumps(industry_packet()).encode())
            self.assertEqual(r["status"], "UNAVAILABLE")
            for key in ("engine_a", "engine_b", "engine_c"):
                self.assertEqual(r[key]["status"], "UNAVAILABLE", key)

    def test_invalid_asof_conflict_and_missing_claim_never_approve(self):
        for when in ("2025-02-25", "2100-01-01", "2025-02-30"):
            r = bridge.analyze_historical_ir_engines(as_of=when,
                                                      **valid_market_kwargs())
            self.assertEqual(r["status"], "UNAVAILABLE")
            self.assertEqual(r["engine_b"]["status"], "UNAVAILABLE")
        for claim, outcome in (("140", "conflict"), ("", "unavailable")):
            r = bridge.analyze_historical_ir_engines(claim_pct=claim)
            self.assertEqual(r["engine_b"]["claim_status"], outcome)
            self.assertEqual(r["guard"]["decision"], "HOLD")

    def test_nonfinite_duplicate_oversize_industry_is_unavailable_not_exception(self):
        for raw in (b'{"x":NaN}', b'{"x":1,"x":2}', b"x" * 70000):
            r = bridge.analyze_historical_ir_engines(industry_json=raw)
            self.assertEqual(r["engine_c"]["status"], "UNAVAILABLE")
            self.assertEqual(r["engine_b"]["status"],
                             "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY")

    def test_cli_no_input_and_symlink_fail_closed(self):
        cmd = [sys.executable, "-B", "-m", "proofinvest.issuer_ir_engine_bridge"]
        p = subprocess.run(cmd, text=True, capture_output=True, check=True)
        j = json.loads(p.stdout)
        self.assertEqual(j["engine_b"]["status"],
                         "PARTIAL_HISTORICAL_MANUAL_NUMERIC_ONLY")
        self.assertFalse(j["sec_accessed"])
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "missing.csv"
            p = subprocess.run(cmd + ["--market-csv", str(absent)],
                               text=True, capture_output=True)
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)["status"], "UNAVAILABLE")

    def test_cli_supplied_local_paired_csv_calculates_a(self):
        cmd = [sys.executable, "-B", "-m", "proofinvest.issuer_ir_engine_bridge"]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "stock-benchmark.csv"
            source.write_bytes(csv_from_fixture())
            p = subprocess.run(cmd + ["--market-csv", str(source),
                "--market-source-url", "https://example.org/operator-archive",
                "--market-published-at", "2025-10-15"],
                text=True, capture_output=True, check=True)
        r = json.loads(p.stdout)
        self.assertEqual(r["engine_a"]["status"], "REPORTED_UNVERIFIED", r)
        self.assertEqual(r["engine_b"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(r["guard"]["decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
