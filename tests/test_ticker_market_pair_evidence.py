"""P143 live local seven-stage and paid-market receipt integration, offline."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
import os
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_workflow import run_local_ticker_workflow
from proofinvest.market_provider_alpha_vantage import parse_daily_close_bytes
from proofinvest.market_provider_alpha_vantage_index import parse_index_daily_bytes
from proofinvest.market_pair_engine_a import fetch_and_analyze_market_pair
from proofinvest.ticker_market_pair_evidence import (
    build_linked_market_evidence, verify_linked_market_evidence,
    linked_evidence_json_bytes,
)
from tests.test_ticker_market_industry_bridge import scenario

_KEY = "SYNTHETICKEY12345"
_GATES = {
    "KUODRA_ENABLE_ALPHA_VANTAGE_DAILY": "1",
    "KUODRA_ENABLE_ALPHA_VANTAGE_INDEX": "1",
    "KUODRA_ALPHA_VANTAGE_INDEX_PREMIUM_APPROVED": "1",
    "KUODRA_ALPHA_VANTAGE_RIGHTS_APPROVED": "1",
}


def _body(symbol, start=100):
    series = {}
    current = date(2025, 11, 3)
    n = 0
    for offset in range(130):
        day = current + timedelta(days=offset)
        if day.weekday() < 5:
            series[day.isoformat()] = {"4. close": str(start + offset + offset % 4)}
            n += 1
            if n == 65:
                break
    return json.dumps({"Meta Data": {"2. Symbol": symbol},
                       "Time Series (Daily)": series}).encode()


def _prepared():
    _, raw, market, industry = scenario()
    m, c = json.dumps(market).encode(), json.dumps(industry).encode()
    workflow = run_local_ticker_workflow(
        ticker="NVDA", as_of="2026-02-01", sources=raw,
        market_json=m, industry_json=c)
    stock = parse_daily_close_bytes(_body("NVDA"), ticker="NVDA", as_of="2026-02-01")
    index = parse_index_daily_bytes(_body("NDX", 10000),
                                   benchmark="NASDAQ_100", as_of="2026-02-01")
    return workflow, raw, m, c, stock, index


def _build(prepared):
    w, raw, market, industry, stock, index = prepared
    return build_linked_market_evidence(
        workflow=w, sources=raw, market_json=market, industry_json=industry,
        stock=stock, index=index)


def _verify(report, prepared):
    w, raw, market, industry, stock, index = prepared
    return verify_linked_market_evidence(
        report, workflow=w, sources=raw, market_json=market,
        industry_json=industry, stock=stock, index=index)


class LinkedEvidenceTests(unittest.TestCase):
    def test_real_local_pipeline_and_real_decimal_engine_a_b_c_guard(self):
        prepared = _prepared()
        w = prepared[0]
        self.assertEqual(w["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        out = _build(prepared)
        self.assertEqual(out["status"], "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED", out)
        self.assertEqual(out["issuer"]["cik"], "0001045810")
        self.assertEqual(out["engine_c"]["status"], "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertEqual(out["premium_engine_a"]["benchmark"], "NASDAQ_100")
        self.assertEqual(out["premium_engine_a"]["matched_observation_count"], 65)
        self.assertIsNotNone(out["premium_engine_a"]["beta"])
        self.assertEqual(out["guard_policy_preview"], "HOLD")
        self.assertEqual(_verify(out, prepared)["status"], "PASS")
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["source_rights_verified"])
        self.assertFalse(out["full_a_b_c_ready"])
        self.assertFalse(out["trade_executed"])

    def test_report_is_sanitized_without_source_rows_or_keys(self):
        prepared = _prepared()
        raw = linked_evidence_json_bytes(_build(prepared))
        self.assertLess(len(raw), 16384)
        self.assertNotIn(b"close_observations", raw)
        self.assertNotIn(b"Time Series (Daily)", raw)
        self.assertNotIn(b"apikey", raw)
        self.assertNotIn(_KEY.encode(), raw)
        self.assertNotIn(b"<html", raw.lower())

    def test_tamper_in_any_local_source_fails_independent_replay(self):
        prepared = list(_prepared())
        prepared[1] = dict(prepared[1], companyfacts=b"{}")
        self.assertEqual(_build(prepared)["status"], "BLOCKED")

    def test_market_ticker_or_index_symbol_mismatch_blocks(self):
        for role, field, value in (
            (4, "ticker", "AAPL"), (5, "index_symbol", "QQQ"),
            (4, "as_of", "2026-01-31"),
        ):
            prepared = list(_prepared())
            prepared[role] = dict(prepared[role], **{field: value})
            self.assertEqual(_build(prepared)["status"], "BLOCKED", (role, field))

    def test_guard_reject_or_altered_report_cannot_pass(self):
        prepared = list(_prepared())
        prepared[0] = deepcopy(prepared[0])
        prepared[0]["original"]["guard_preview"]["decision"] = "REJECT"
        self.assertEqual(_build(prepared)["status"], "BLOCKED")
        prepared = _prepared()
        report = _build(prepared)
        forged = deepcopy(report)
        forged["premium_engine_a"]["beta"] = "999"
        self.assertEqual(_verify(forged, prepared)["status"], "FAIL")
        forged.pop("evidence_sha256")
        self.assertEqual(_verify(forged, prepared)["status"], "FAIL")

    def test_reshashed_forgery_still_fails_recomputed_market_math(self):
        from hashlib import sha256
        report = _build(_prepared())
        report["premium_engine_a"]["security_return_pct"] = "9999"
        payload = {k: v for k, v in report.items() if k != "evidence_sha256"}
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False) + "\n").encode()
        report["evidence_sha256"] = sha256(encoded).hexdigest()
        self.assertEqual(_verify(report, _prepared())["status"], "FAIL")

    def test_approved_fake_transport_callback_captures_only_in_memory(self):
        prepared = _prepared()
        w, raws, m, c, stock, index = prepared
        seen = []
        def record_pair(observed_stock, observed_index):
            result = build_linked_market_evidence(
                workflow=w, sources=raws, stock=observed_stock,
                index=observed_index, market_json=m, industry_json=c)
            seen.append(result)
        with patch.dict(os.environ, _GATES):
            result = fetch_and_analyze_market_pair(
                ticker="NVDA", issuer_cik="0001045810",
                filing_date=w["revenue"]["filing_date"], as_of="2026-02-01",
                api_key=_KEY, explicit_click=True,
                provider_rights_approved=True, premium_entitlement_approved=True,
                stock_transport=lambda _: _body("NVDA"),
                index_transport=lambda _: _body("NDX", 10000),
                validated_pair_callback=record_pair,
            )
        self.assertEqual(result["status"], "ENGINE_A_PRICE_INDEX_DESCRIPTIVE_UNVERIFIED", result)
        self.assertEqual(result["network_requests"], 2)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["status"], "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED")
        self.assertNotIn(_KEY, repr(seen))

    def test_real_ui_button_exports_linked_json_after_local_replay(self):
        from proofinvest import ticker_research_ui as ui
        from proofinvest import ticker_sec_transport as sec_transport
        from proofinvest.market_pair_engine_a import analyze_price_index_pair
        from tests.test_ticker_research_ui import FakeSt, Uploaded

        prepared = _prepared()
        _, raw, market, industry, stock, index = prepared
        uploads = {
            "kuodra_p100_ticker_map": Uploaded(raw["ticker_map"]),
            "kuodra_p100_submissions": Uploaded(raw["submissions"]),
            "kuodra_p116_companyfacts": Uploaded(raw["companyfacts"]),
            "kuodra_p116_original": Uploaded(raw["original_10k"]),
            "kuodra_p104_market_json": Uploaded(market),
            "kuodra_p104_industry_json": Uploaded(industry),
        }
        label = "로컬 공시 재검산 + 승인된 주가·실제 NDX 지수 조회 (최대 2회)"
        st = FakeSt(
            clicked=label,
            values={"kuodra_p100_ticker": "NVDA",
                    "kuodra_p100_as_of": "2026-02-01"},
            checks={"kuodra_p141_pair_ack": True},
            uploads=uploads,
        )
        def vendor(**kwargs):
            self.assertEqual(kwargs["ticker"], "NVDA")
            kwargs["validated_pair_callback"](stock, index)
            output = analyze_price_index_pair(
                stock=stock, index=index, ticker=kwargs["ticker"],
                issuer_cik=kwargs["issuer_cik"],
                filing_date=kwargs["filing_date"],
                as_of=kwargs["as_of"])
            output["network_requests"] = 2
            return output
        with (
            patch.dict(os.environ, {**_GATES,
                                    "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
                                    "KUODRA_ALPHA_VANTAGE_API_KEY": _KEY}, clear=True),
            patch.object(sec_transport, "_open_once",
                         side_effect=AssertionError("REAL_SEC_FORBIDDEN")) as net,
            patch("proofinvest.market_pair_engine_a.fetch_and_analyze_market_pair",
                  side_effect=vendor) as vendor_mock,
        ):
            ui.render_single_ticker_search(st)
        net.assert_not_called()
        vendor_mock.assert_called_once()
        exports = [value for kind, value in st.messages
                   if kind == "download" and
                   value["label"] == "통합 검산 근거 JSON (로컬 전용 · 미인증)"]
        self.assertEqual(len(exports), 1, st.messages)
        payload = json.loads(exports[0]["data"])
        self.assertEqual(payload["status"],
                         "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED")
        self.assertEqual(payload["guard_policy_preview"], "HOLD")
        self.assertEqual(payload["engine_c"]["status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertFalse(payload["source_authenticated"])
        self.assertFalse(payload["external_sharing_allowed"])
        self.assertNotIn(_KEY, repr(st.messages))
        self.assertNotIn("close_observations", repr(payload))

    def test_no_callback_without_explicit_approval(self):
        seen = []
        with patch.dict(os.environ, {}, clear=True):
            result = fetch_and_analyze_market_pair(
                ticker="NVDA", issuer_cik="0001045810", filing_date="2025-10-15",
                as_of="2026-02-01", api_key=_KEY,
                validated_pair_callback=lambda *_: seen.append(1),
                stock_transport=lambda _: self.fail("UNAUTHORIZED_NETWORK"),
                index_transport=lambda _: self.fail("UNAUTHORIZED_NETWORK"),
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(seen, [])

    def test_wrong_raw_market_receipt_rejected_after_report_creation(self):
        prepared = _prepared()
        report = _build(prepared)
        changed = list(prepared)
        changed[5] = deepcopy(changed[5])
        changed[5]["close_observations"][20]["close"] = "50000"
        self.assertEqual(_verify(report, changed)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
