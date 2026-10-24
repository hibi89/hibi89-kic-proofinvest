"""Offline view model and actual Streamlit AppTest smoke checks."""
import copy
import unittest
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


if __name__ == "__main__":
    unittest.main()
