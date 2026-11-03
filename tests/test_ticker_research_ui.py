"""P100 local-only ticker UI; mocked actions, zero real SEC traffic."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import ticker_research_ui as ui
from proofinvest import ticker_sec_transport as transport
from tests.test_ticker_research_intake import mapping, submissions

UA = "KUODRA test qa-team@unitfixtures.dev"


class Uploaded:
    def __init__(self, raw):
        self.raw, self.size = raw, len(raw)
    def getvalue(self):
        return self.raw


class FakeSt:
    def __init__(self, addr="127.0.0.1", *, clicked=None, values=None,
                 checks=None, uploads=None):
        self.addr = addr
        self.clicked = clicked
        self.values = values or {}
        self.checks = checks or {}
        self.uploads = uploads or {}
        self.messages = []
        self.buttons = []
    def get_option(self, key):
        assert key == "server.address"
        return self.addr
    def title(self, val): self.messages.append(("title", val))
    def caption(self, val): self.messages.append(("caption", val))
    def subheader(self, val): self.messages.append(("subheader", val))
    def warning(self, val): self.messages.append(("warning", val))
    def error(self, val): self.messages.append(("error", val))
    def success(self, val): self.messages.append(("success", val))
    def info(self, val): self.messages.append(("info", val))
    def code(self, val, **_): self.messages.append(("code", val))
    def json(self, val): self.messages.append(("json", val))
    def text_input(self, label, **kwargs):
        return self.values.get(kwargs["key"], kwargs.get("value", ""))
    def checkbox(self, label, **kwargs):
        return self.checks.get(kwargs["key"], kwargs.get("value", False))
    def file_uploader(self, label, **kwargs):
        return self.uploads.get(kwargs["key"])
    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs.get("disabled", False)))
        return label == self.clicked and not kwargs.get("disabled", False)
    def metric(self, label, value, **kwargs):
        self.messages.append(("metric", (label, value)))
    def download_button(self, label, *, data, file_name, mime, **kwargs):
        self.messages.append(("download", {
            "label": label, "data": data,
            "file_name": file_name, "mime": mime,
        }))
        return False


class TickerUiTests(unittest.TestCase):
    def test_disabled_on_public_bind_and_no_local_owner_switch(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KUODRA_ENABLE_LOCAL_SOURCE_UI", None)
            self.assertFalse(ui.ticker_search_enabled(FakeSt()))
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            for addr in ("0.0.0.0", "::", "192.0.2.23", ""):
                self.assertFalse(ui.ticker_search_enabled(FakeSt(addr)))
                st = FakeSt(addr)
                ui.render_single_ticker_search(st)
                self.assertFalse(st.buttons)
            self.assertTrue(ui.ticker_search_enabled(FakeSt()))

    def test_p126_existing_ticker_page_runs_real_apple_manual_case_only_on_click(self):
        st = FakeSt(
            clicked="Apple FY2025 원문·발표 수동기록 재검산 (네트워크 없음)",
            values={"kuodra_p100_ticker": "AAPL",
                    "kuodra_p100_as_of": "2025-11-01"},
        )
        with (
            patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
            patch.object(transport, "collect_ticker_sec_sources",
                         side_effect=AssertionError("SEC HTTP FORBIDDEN")) as remote,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("NO VENDOR NETWORK")),
        ):
            ui.render_single_ticker_search(st)
        remote.assert_not_called()
        shown = [val for kind, val in st.messages
                 if kind == "json" and isinstance(val, dict)
                 and val.get("status") == "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED"]
        self.assertEqual(len(shown), 1)
        result = shown[0]
        self.assertEqual(result["sales_growth_pct"], "6.43")
        self.assertEqual(result["sales_2025_usd_millions"], "416161")
        self.assertEqual(result["guard_preview"]["decision"], "HOLD")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["current_live_market_data"])
        self.assertFalse(result["ai_agent_executed"])
        self.assertFalse(result["trade_executed"])
        self.assertTrue(any(k == "metric" and v[1] == "6.43%"
                            for k, v in st.messages))
        self.assertFalse(any(k == "download" for k, _ in st.messages))
        self.assertFalse(any(k == "error" for k, _ in st.messages))

    def test_p126_before_filing_or_wrong_issuer_cannot_run_case(self):
        for ticker, as_of in (("AAPL", "2025-10-30"),
                              ("NVDA", "2025-11-01")):
            st = FakeSt(
                clicked="Apple FY2025 원문·발표 수동기록 재검산 (네트워크 없음)",
                values={"kuodra_p100_ticker": ticker,
                        "kuodra_p100_as_of": as_of},
            )
            with patch.dict(os.environ, {
                "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            }), patch("proofinvest.ticker_apple_historical.review_apple_fy2025_historical",
                      side_effect=AssertionError("NOT AUTHORIZED TO RUN")) as replay:
                ui.render_single_ticker_search(st)
            replay.assert_not_called()
            self.assertFalse(any(
                k == "json" and isinstance(v, dict)
                and v.get("status") == "HISTORICAL_MANUAL_NUMBERS_CROSSCHECKED"
                for k, v in st.messages))
            if ticker == "AAPL":
                buttons = [blocked for label, blocked in st.buttons
                           if label.startswith("Apple FY2025 원문")]
                self.assertEqual(buttons, [True])
            else:
                self.assertFalse(any(label.startswith("Apple FY2025 원문")
                                     for label, blocked in st.buttons))

    def test_p125_owner_can_review_public_supplier_terms_without_network(self):
        st = FakeSt(clicked="시장 데이터 이용권한 사전 점검 (네트워크 없음)")
        with (
            patch.dict(os.environ, {
                "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
                "KUODRA_ENABLE_SEC_FETCH_UI": "1",
            }),
            patch.object(transport, "collect_ticker_sec_sources",
                         side_effect=AssertionError("SEC API FORBIDDEN")) as fetch,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("VENDOR NETWORK FORBIDDEN")),
        ):
            ui.render_single_ticker_search(st)
        fetch.assert_not_called()
        reports = [v for k, v in st.messages if k == "json"
                   and isinstance(v, dict)
                   and v.get("schema") == "kuodra.p125-market-and-sec-license-gaps.v1"]
        self.assertEqual(len(reports), 1)
        r = reports[0]
        self.assertEqual(r["status"], "BLOCKED_NO_LICENSED_LIVE_E2E_YET")
        self.assertEqual(r["sec_access"], "P105_SEC_ACCESS_DENIED_403_NO_RETRY")
        self.assertFalse(r["sec_http_attempted"])
        self.assertFalse(r["ndx_data_authorized"])
        self.assertFalse(r["ai_processing_authorized"])
        self.assertEqual([p["provider"] for p in r["providers"]],
                         ["massive", "twelve_data", "fred", "nasdaq_gids"])
        self.assertEqual(r["providers"][2]["license_blocker_codes"][0],
                         "FRED_API_AI_SYSTEM_USE_RESTRICTIONS_APPLY")
        self.assertTrue(all(p["guard_decision"] == "HOLD"
                            and p["request_execution_authorized"] is False
                            and p["network_requests_executed"] == 0
                            for p in r["providers"]))
        self.assertFalse(any(k == "download" for k, _ in st.messages))

    def test_default_approved_ui_not_callable_without_extra_live_gate(self):
        st = FakeSt(clicked="SEC 원문 4종 자동 수집 실행",
                    checks={"kuodra_p100_approve_four": True},
                    values={"kuodra_p100_sec_contact": UA})
        with patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "0",
        }), patch.object(transport, "collect_ticker_sec_sources",
                         side_effect=AssertionError("UNAPPROVED_HTTP")) as fetch:
            ui.render_single_ticker_search(st)
        fetch.assert_not_called()
        self.assertEqual(st.buttons[0], ("SEC 원문 4종 자동 수집 실행", True))
        self.assertTrue(any(kind == "warning" for kind, _ in st.messages))

    def test_live_environment_alone_or_ack_alone_not_enough(self):
        for checked, agent in ((False, UA), (True, "")):
            st = FakeSt(clicked="SEC 원문 4종 자동 수집 실행",
                        checks={"kuodra_p100_approve_four": checked},
                        values={"kuodra_p100_sec_contact": agent})
            with self.subTest(checked=checked), patch.dict(os.environ, {
                "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
                "KUODRA_ENABLE_SEC_FETCH_UI": "1",
            }), patch.object(transport, "collect_ticker_sec_sources",
                             side_effect=AssertionError("UNAPPROVED_HTTP")) as fetch:
                ui.render_single_ticker_search(st)
                fetch.assert_not_called()
                self.assertTrue(st.buttons[0][1])

    def test_p105_hold_disables_live_button_despite_owner_ui_switches(self):
        st = FakeSt(clicked="SEC 원문 4종 자동 수집 실행",
                    checks={"kuodra_p100_approve_four": True},
                    values={"kuodra_p100_sec_contact": UA,
                            "kuodra_p100_as_of": "2025-10-16"})
        with patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "1",
        }), patch.object(transport, "collect_ticker_sec_sources",
                         side_effect=AssertionError("FORBIDDEN_HTTP")) as fetch:
            ui.render_single_ticker_search(st)
        fetch.assert_not_called()
        self.assertTrue(st.buttons[0][1])
        self.assertTrue(any(kind == "warning" and "403" in val
                            for kind, val in st.messages))
        self.assertNotIn(UA, repr(st.messages))

    def test_enabled_genuine_contact_single_click_and_no_raw_retention(self):
        st = FakeSt(clicked="SEC 원문 4종 자동 수집 실행",
                    checks={"kuodra_p100_approve_four": True},
                    values={"kuodra_p100_sec_contact": UA,
                            "kuodra_p100_as_of": "2025-10-16"})
        result = {
            "status": "four_sec_responses_in_memory_unverified",
            "ticker": "NVDA", "cik": "0001045810",
            "selected_10k_accession": "0001045810-25-000020",
            "requested_as_of": "2025-10-16",
            "source_authenticated": False, "source_rights_verified": False,
            "full_a_b_c_ready": False, "trade_executed": False,
            "ai_interpretation_ready": False,
            "http_requests_attempted": 4, "live_sec_http_called": True,
            "raw_companyfacts_financial_values_verified": False,
            "source_urls": {"ticker_map": "https://www.sec.gov/files/company_tickers.json"},
            "source_sha256": {"ticker_map": "0" * 64},
            "source_bytes": {"ticker_map": 20},
        }
        raws = {"ticker_map": b"PRIVATE_BYTES"}
        with patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "1",
        }), patch.object(ui, "P105_SEC_403_HOLD", False), patch.object(
                transport, "collect_ticker_sec_sources",
                return_value=(result, raws)) as fetch:
            ui.render_single_ticker_search(st)
        fetch.assert_called_once_with(
            ticker="NVDA", as_of="2025-10-16", user_agent=UA,
            allow_network=True, acknowledge_four_requests=True,
        )
        self.assertEqual(raws, {})
        self.assertTrue(any(kind == "success" for kind, _ in st.messages))
        self.assertNotIn(UA, repr(st.messages))
        self.assertNotIn("PRIVATE_BYTES", repr(st.messages))

    def test_invalid_ticker_and_future_date_never_trigger_network(self):
        for vals in ({"kuodra_p100_ticker": "bad ticker"},
                     {"kuodra_p100_as_of": "2100-01-01"}):
            st = FakeSt(clicked="SEC 원문 4종 자동 수집 실행",
                        values={"kuodra_p100_sec_contact": UA, **vals},
                        checks={"kuodra_p100_approve_four": True})
            with patch.dict(os.environ, {
                "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
                "KUODRA_ENABLE_SEC_FETCH_UI": "1",
            }), patch.object(transport, "collect_ticker_sec_sources",
                            side_effect=AssertionError("UNAPPROVED_HTTP")) as fetch:
                ui.render_single_ticker_search(st)
                fetch.assert_not_called()
                self.assertTrue(st.buttons[0][1])

    def test_offline_local_plan_and_mismatch_blocks_without_network(self):
        st = FakeSt(clicked="로컬 원본으로 출처 계획 확인",
                    values={"kuodra_p100_as_of": "2025-10-16"},
                    uploads={"kuodra_p100_ticker_map": Uploaded(mapping()),
                             "kuodra_p100_submissions": Uploaded(submissions())})
        with patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "0",
        }), patch.object(transport, "collect_ticker_sec_sources",
                        side_effect=AssertionError("UNAPPROVED_HTTP")) as fetch:
            ui.render_single_ticker_search(st)
        fetch.assert_not_called()
        self.assertTrue(any(kind == "success" for kind, _ in st.messages))
        self.assertTrue(any(kind == "json" and isinstance(v, dict)
                            and v.get("selected_10k") == "0001045810-25-000020"
                            for kind, v in st.messages))
        offline_buttons = [disabled for label, disabled in st.buttons
                           if label == "로컬 원본으로 출처 계획 확인"]
        self.assertEqual(offline_buttons, [False])

    def test_tampered_source_or_wrong_size_fails_closed(self):
        st = FakeSt(clicked="로컬 원본으로 출처 계획 확인",
                    values={"kuodra_p100_as_of": "2025-10-16"},
                    uploads={"kuodra_p100_ticker_map": Uploaded(b"{}"),
                             "kuodra_p100_submissions": Uploaded(submissions())})
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            ui.render_single_ticker_search(st)
        self.assertFalse(any(kind == "success" for kind, _ in st.messages))
        self.assertTrue(any(kind == "warning" for kind, _ in st.messages))
        wrong = Uploaded(mapping())
        wrong.size += 1
        with self.assertRaises(ValueError):
            ui._read_uploaded(wrong, ui.MAX_MAP_BYTES)

    def test_p116_offline_four_source_ui_reuses_guard_without_sec_http(self):
        from tests.test_ticker_sec_financial_bridge import valid_case
        from tests.test_ticker_sec_original_guard_preview import valid_xhtml
        _live_receipt, sources = valid_case()  # Existing mocked transport only.
        st = FakeSt(
            clicked="로컬 원본으로 출처 계획 확인",
            values={"kuodra_p100_as_of": "2025-10-16"},
            uploads={
                "kuodra_p100_ticker_map": Uploaded(sources["ticker_map"]),
                "kuodra_p100_submissions": Uploaded(sources["submissions"]),
                "kuodra_p116_companyfacts": Uploaded(sources["companyfacts"]),
                "kuodra_p116_original": Uploaded(valid_xhtml()),
            },
        )
        with patch.dict(os.environ, {
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "1",
        }), patch.object(transport, "_open_once",
                         side_effect=AssertionError("NO SEC RETRY")) as http:
            ui.render_single_ticker_search(st)
        http.assert_not_called()
        previews = [v for k, v in st.messages
                    if k == "json" and isinstance(v, dict)
                    and v.get("source_mode") == "LOCAL_USER_FILES_NOT_SEC_AUTHENTICATED"]
        self.assertEqual(len(previews), 1)
        result = previews[0]
        self.assertEqual(result["financial_status"], "REVENUE_CALCULATED_UNVERIFIED")
        self.assertEqual(result["growth_pct_unverified"], "100.00")
        self.assertEqual(result["guard_policy_preview"]["decision"], "HOLD")
        self.assertEqual(result["http_requests_attempted"], 0)
        workflow = [v for kind, v in st.messages if kind == "json"
                    and isinstance(v, dict)
                    and v.get("mode") == "DETERMINISTIC_LOCAL_TOOLS_NOT_LLM_AGENT"]
        self.assertEqual(len(workflow), 1)
        self.assertEqual(workflow[0]["tool_calls_executed"], 7)
        self.assertEqual(workflow[0]["tool_budget"], 7)
        self.assertEqual(len(workflow[0]["tool_trace"]), 7)
        self.assertEqual(workflow[0]["status"], "READY_FOR_HUMAN_REVIEW_UNVERIFIED")
        self.assertFalse(workflow[0]["ai_agent_executed"])
        self.assertFalse(workflow[0]["official_contest_submission"])
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["trade_executed"])
        self.assertTrue(st.buttons[0][1])  # Live button stays P105-blocked.
        reports = [v for k, v in st.messages if k == "download"]
        self.assertEqual(len(reports), 1)
        from proofinvest.ticker_local_report import report_json_bytes
        report = __import__("json").loads(reports[0]["data"])
        self.assertEqual(report["verification"]["growth_pct"], "100.00")
        self.assertEqual(report["guard_policy_preview"], "HOLD")
        self.assertEqual(report["engine_b"]["status"], "UNAVAILABLE")
        self.assertTrue(any(kind == "subheader" and "Engine B" in val
                            for kind, val in st.messages))
        self.assertEqual(report["source_rights_ledger"]["status"],
                         "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED")
        self.assertFalse(report["source_rights_ledger"]["external_sharing_allowed"])
        self.assertEqual(len(report["source_rights_ledger"]["sources"]), 6)
        self.assertTrue(any(
            kind == "subheader" and "이용권리 사전 점검" in value
            for kind, value in st.messages
        ))
        self.assertEqual(report["limits"]["external_http_requests"], 0)
        self.assertFalse(report["limits"]["source_authenticated"])
        self.assertEqual(len(report["source_sha256"]["companyfacts"]), 64)

    def test_p123_reviewer_ack_requires_explicit_click_and_replays_original(self):
        from tests.test_ticker_sec_financial_bridge import valid_case
        from tests.test_ticker_sec_original_guard_preview import valid_xhtml
        from proofinvest.ticker_local_report import report_json_bytes
        import json
        _, sources = valid_case()
        uploads = {
            "kuodra_p100_ticker_map": Uploaded(sources["ticker_map"]),
            "kuodra_p100_submissions": Uploaded(sources["submissions"]),
            "kuodra_p116_companyfacts": Uploaded(sources["companyfacts"]),
            "kuodra_p116_original": Uploaded(valid_xhtml()),
        }
        values = {
            "kuodra_p100_as_of": "2025-10-16",
            "kuodra_p123_alias": "Reviewer_123",
            "kuodra_p123_note": "원본 미인증과 HOLD 상태를 확인하고 검토 기록을 남김",
        }
        blocked = FakeSt(
            clicked="6단계 재검증 후 로컬 확인 기록 생성",
            uploads=uploads, values=values,
        )
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            ui.render_single_ticker_search(blocked)
        self.assertTrue(any(label.startswith("6단계 재검증 후") and disabled
                            for label, disabled in blocked.buttons))
        self.assertFalse(any(
            kind == "download" and "로컬 사람 검토" in v["label"]
            for kind, v in blocked.messages if kind == "download"))
        st = FakeSt(
            clicked="6단계 재검증 후 로컬 확인 기록 생성",
            uploads=uploads, values=values,
            checks={"kuodra_p123_ack": True},
        )
        with (
            patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}),
            patch.object(transport, "_open_once",
                         side_effect=AssertionError("NO LIVE SEC")) as http,
        ):
            ui.render_single_ticker_search(st)
        http.assert_not_called()
        downloads = [v for kind, v in st.messages if kind == "download"]
        self.assertEqual(len(downloads), 2)
        by_name = {v["file_name"]: v for v in downloads}
        evidence = json.loads(
            by_name["kuodra-local-four-source-UNVERIFIED.json"]["data"])
        human = json.loads(
            by_name["kuodra-local-review-ACK-UNVERIFIED.json"]["data"])
        self.assertEqual(human["report_sha256"], evidence["report_sha256"])
        self.assertEqual(human["status"], "ACKNOWLEDGED_UNVERIFIED_LOCAL_ONLY")
        self.assertEqual(human["guard_policy_preview_unchanged"], "HOLD")
        self.assertEqual(human["reviewer_alias_unverified"], "Reviewer_123")
        self.assertFalse(human["human_approved"])
        self.assertFalse(human["audit_written"])
        self.assertFalse(human["source_rights_verified"])
        self.assertEqual(human["external_http_requests"], 0)
        self.assertIn("kuodra-local-review-ACK-UNVERIFIED.json", by_name)

    def test_p116_partial_upload_never_claims_financial_verification(self):
        st = FakeSt(clicked="로컬 원본으로 출처 계획 확인",
                    values={"kuodra_p100_as_of": "2025-10-16"},
                    uploads={"kuodra_p100_ticker_map": Uploaded(mapping()),
                             "kuodra_p100_submissions": Uploaded(submissions()),
                             "kuodra_p116_companyfacts": Uploaded(b"{}")})
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}), \
                patch.object(transport, "_open_once",
                             side_effect=AssertionError("NO SEC HTTP")) as net:
            ui.render_single_ticker_search(st)
        net.assert_not_called()
        self.assertFalse(any(k == "json" and isinstance(v, dict)
                             and "growth_pct_unverified" in v for k, v in st.messages))
        self.assertTrue(any(k == "warning" and "4종" not in v
                            for k, v in st.messages))

    def test_unverified_contract_hides_authentication_claim(self):
        st = FakeSt()
        ui._display_receipt(st, {"status": "four_sec_responses_in_memory_unverified",
                                  "source_authenticated": True,
                                  "source_rights_verified": False,
                                  "full_a_b_c_ready": False,
                                  "trade_executed": False}, online=True)
        self.assertFalse(any(k == "success" for k, _ in st.messages))
        self.assertTrue(any(k == "error" for k, _ in st.messages))


if __name__ == "__main__":
    unittest.main()
