"""P107 issuer IR local dashboard contracts and Streamlit registration."""
import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest import issuer_ir_local_ui as ui


class FakeSt:
    def __init__(self, address="127.0.0.1", choice=None):
        self.address = address
        self.choice = choice
        self.events = []
    def get_option(self, name):
        assert name == "server.address"
        return self.address
    def __getattr__(self, name):
        if name in ("title", "warning", "error", "info", "caption", "subheader",
                    "markdown", "dataframe", "metric", "download_button"):
            def record(*args, **kwargs):
                self.events.append((name, args, kwargs))
            return record
        raise AttributeError(name)
    def selectbox(self, label, values, **kwargs):
        self.events.append(("selectbox", (label, values), kwargs))
        return self.choice if self.choice is not None else values[0]
    def columns(self, n):
        return [self for _ in range(n)]


class IrLocalDashboardTests(unittest.TestCase):
    def test_contract_approved_historical_arithmetic_is_not_full_source_auth(self):
        r = ui.build_manual_ir_report()
        self.assertEqual(r["verification"]["state"], "verified")
        self.assertEqual(r["metrics"]["revenue_yoy_pct"], "114.20")
        self.assertEqual(r["metrics"]["fy2025_cash_conversion_pct"], "87.94")
        self.assertEqual(r["engines"]["A"][:11], "UNAVAILABLE")
        self.assertEqual(r["engines"]["C"][:11], "UNAVAILABLE")
        self.assertEqual(r["guard"]["decision"], "HOLD")
        self.assertFalse(r["source"]["origin_authenticated"])
        self.assertFalse(r["execution"]["full_abc_completed"])

    def test_conflict_and_missing_claim_keep_hold(self):
        for claim, state in (("140", "conflict"), ("", "unavailable")):
            with self.subTest(claim=claim):
                r = ui.build_manual_ir_report(claim)
                self.assertEqual(r["verification"]["state"], state)
                self.assertEqual(r["guard"]["decision"], "HOLD")

    def test_tampered_receipt_never_renders_positive_report(self):
        original = ui.replay()
        for field, value in (("source_authenticated", True), ("sec_accessed", True),
                             ("external_network_requests", 1),
                             ("guard_decision", "APPROVE"),
                             ("source_url", "https://example.org"),
                             ("evidence_sha256", "corrupt")):
            with self.subTest(field=field):
                wrong = copy.deepcopy(original)
                wrong[field] = value
                with patch.object(ui, "replay", return_value=wrong):
                    with self.assertRaises(ValueError):
                        ui.build_manual_ir_report()

    def test_no_public_or_unauthorized_local_mode(self):
        for addr, flag in (("0.0.0.0", "1"), ("127.0.0.1", "0")):
            with self.subTest(addr=addr, flag=flag), patch.dict(
                    os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": flag}):
                st = FakeSt(addr)
                ui.render_nvda_ir_local(st)
                self.assertEqual([name for name, _, _ in st.events], ["error"])

    def test_local_report_download_bounded_and_explicitly_unverified(self):
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            st = FakeSt()
            ui.render_nvda_ir_local(st)
        downloads = [(a, kwargs) for typ, a, kwargs in st.events if typ == "download_button"]
        self.assertEqual(len(downloads), 1)
        self.assertIn("UNAUTHENTICATED.json", downloads[0][1]["file_name"])
        self.assertIn('"full_abc_completed": false', downloads[0][1]["data"])
        self.assertIn('"network_requests": 0', downloads[0][1]["data"])
        self.assertFalse(any(typ == "error" for typ, _, _ in st.events))

    def test_conflict_ui_no_approval(self):
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            st = FakeSt(choice="140% — 근거 수치와 충돌")
            ui.render_nvda_ir_local(st)
        self.assertTrue(any(typ == "error" and "수치 충돌" in a[0]
                            for typ, a, _ in st.events))
        self.assertTrue(any(typ == "metric" and a[1] == "HOLD"
                            for typ, a, _ in st.events))

    def test_missing_evidence_fails_closed_without_report(self):
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}), patch.object(
                ui, "replay", side_effect=OSError("missing")):
            st = FakeSt()
            ui.render_nvda_ir_local(st)
        self.assertTrue(any(typ == "error" for typ, _, _ in st.events))
        self.assertFalse(any(typ == "download_button" for typ, _, _ in st.events))


class StreamlitIssuerHistorySmoke(unittest.TestCase):
    def test_source_wired_to_local_only_mode_and_default_stays_synthetic(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import kuodra_local_workspace_ui as flags
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with patch.object(flags, "local_workspace_enabled", return_value=True), patch.object(
                ui, "local_workspace_enabled", return_value=True):
            at = AppTest.from_file(str(app)).run(timeout=20)
            self.assertFalse(at.exception)
            label = "KUODRA · NVIDIA 과거 IR 실수치 검산 (로컬 전용)"
            self.assertIn(label, at.selectbox[0].options)
            self.assertEqual(at.selectbox[0].value, "합성 데이터 시연")
            at.selectbox[0].set_value(label).run(timeout=20)
            self.assertFalse(at.exception, [str(e.message) for e in at.exception])
            self.assertTrue(any("NVIDIA 과거 IR" in t.value for t in at.title))
            self.assertTrue(any(m.label == "FY2025 매출 증가율 (수동 검산)"
                                and m.value == "114.20%" for m in at.metric))
            self.assertTrue(any(m.label == "Guard 결정 (실거래 없음)"
                                and m.value == "HOLD" for m in at.metric))


if __name__ == "__main__":
    unittest.main()
