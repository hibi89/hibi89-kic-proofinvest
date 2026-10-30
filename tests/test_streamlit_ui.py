"""Offline view model and actual Streamlit AppTest smoke checks."""
import copy
import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from proofinvest.offline_view import load_synthetic_snapshot


class SyntheticOfflineViewTests(unittest.TestCase):
    def test_bundled_snapshot_is_explicitly_synthetic_and_local(self):
        x = load_synthetic_snapshot()
        self.assertEqual(x["mode"], "OFFLINE_SYNTHETIC_READ_ONLY")
        self.assertEqual(x["source_kind"], "SYNTHETIC_FIXTURE")
        self.assertEqual(x["year"], 2024)
        self.assertFalse(x["authenticated_external_source"])
        self.assertFalse(x["live_api_called"])

    def test_no_external_source_claim_or_real_filing_link(self):
        v = load_synthetic_snapshot()
        self.assertTrue(v["financial_rows"])
        self.assertEqual(v["risk"]["실제 원문 인증"], "아니오")
        self.assertEqual(v["checks"][0]["실제 원문 인증"], "아니오")
        self.assertTrue(all("https://" not in str(row) for row in v["financial_rows"]))

    def test_read_only_determinism_and_unrelated_statement_visibility(self):
        left = load_synthetic_snapshot()
        right = load_synthetic_snapshot()
        self.assertEqual(left, right)
        self.assertTrue(any(row["범위"] == "CFS" for row in left["financial_rows"]))
        self.assertTrue(any(row["범위"] == "OFS" for row in left["financial_rows"]))
        self.assertEqual(left["risk"]["표시 비율"], "266.67")
        self.assertEqual(left["checks"][0]["구조상 상태"], "verified")

    def test_rejects_fake_filing_reference_inside_synthetic_fixture(self):
        from proofinvest import offline_view
        valid = offline_view._FIXTURE.read_text(encoding="utf-8")
        bad = valid.replace('"rcept_no":""', '"rcept_no":"12345678901234"', 1)
        self.assertNotEqual(bad, valid)
        with patch.object(offline_view, "_FIXTURE", Mock(read_text=Mock(return_value=bad))):
            with self.assertRaisesRegex(ValueError, "synthetic"):
                offline_view.load_synthetic_snapshot()

    def test_missing_fixture_fails_closed(self):
        from proofinvest import offline_view
        with patch.object(offline_view, "_FIXTURE", Mock(read_text=Mock(return_value="{}"))):
            with self.assertRaisesRegex(ValueError, "fixture"):
                offline_view.load_synthetic_snapshot()


class StreamlitHeadlessTests(unittest.TestCase):
    def test_app_executes_without_browser_and_displays_synthetic_warning(self):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest

        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        at = AppTest.from_file(str(app)).run(timeout=15)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(at.title)
        self.assertIn("오프라인 합성 데이터", at.title[0].value)
        self.assertTrue(at.warning)
        self.assertIn("SYNTHETIC_FIXTURE", at.warning[0].value)
        self.assertTrue(any(m.label == "외부 출처 인증" and m.value == "미인증" for m in at.metric))

    def test_saved_ui_uses_only_cached_data_and_shows_provenance(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import snapshot_store as store
        from proofinvest import offline_view

        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"HOME": root, "USERPROFILE": root}):
                cache = Path(root) / ".proofinvest-synthetic-cache"
                cache.mkdir()
                store.save_synthetic_snapshot(cache)
                at = AppTest.from_file(str(app)).run(timeout=15)
                with patch.object(offline_view, "load_synthetic_snapshot", side_effect=AssertionError("calculation")):
                    with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("calculation")):
                        at.radio[0].set_value("저장된 결과 재조회 (재계산 없음)").run(timeout=15)
                self.assertFalse(at.exception)
                self.assertTrue(at.success)
                self.assertIn("재계산하지 않음", at.success[0].value)
                self.assertTrue(any("fixtures/synthetic_annual.json" in m.value for m in at.info))
                self.assertTrue(any(m.label == "부채/자본 비율" and m.value == "266.67" for m in at.metric))
                self.assertTrue(any(m.label == "외부 출처 인증" and m.value == "미인증" for m in at.metric))

    def test_saved_ui_missing_record_fails_closed(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import snapshot_store as store

        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"HOME": root, "USERPROFILE": root}):
                at = AppTest.from_file(str(app)).run(timeout=15)
                with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("fallback")):
                    at.radio[0].set_value("저장된 결과 재조회 (재계산 없음)").run(timeout=15)
                self.assertFalse(at.exception)
                self.assertTrue(at.error)
                self.assertIn("자동 재계산", at.error[0].value)
                self.assertFalse(any(m.label == "부채/자본 비율" for m in at.metric))
                self.assertFalse(at.success)

    def test_saved_ui_corrupt_record_hides_risk_metrics(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import snapshot_store as store

        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"HOME": root, "USERPROFILE": root}):
                cache = Path(root) / ".proofinvest-synthetic-cache"
                cache.mkdir()
                store.save_synthetic_snapshot(cache)
                f = cache / "synthetic_snapshot_v1.json"
                content = json.loads(f.read_text(encoding="utf-8"))
                content["payload"]["risk"]["표시 비율"] = "999.99"
                f.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
                at = AppTest.from_file(str(app)).run(timeout=15)
                with patch.object(store, "load_synthetic_snapshot", side_effect=AssertionError("fallback")):
                    at.radio[0].set_value("저장된 결과 재조회 (재계산 없음)").run(timeout=15)
                self.assertFalse(at.exception)
                self.assertTrue(at.error)
                self.assertFalse(any(m.label == "부채/자본 비율" for m in at.metric))


if __name__ == "__main__":
    unittest.main()
