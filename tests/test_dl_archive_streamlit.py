"""Source-card UI test: synthetic-only, no HTML execution or live SEC."""
from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from proofinvest.kic_dl_original_demo import replay_original
from streamlit_app import _valid_dl_archive_receipt, _render_dl_archive_case


class DlArchiveUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = replay_original()

    def test_genuine_synthetic_replay_accepts_strict_presentation_gate(self):
        self.assertTrue(_valid_dl_archive_receipt(self.receipt))
        self.assertEqual(self.receipt["issuer_cik"], "0000000001")
        self.assertEqual(self.receipt["accession"], "0000000001-25-000001")
        self.assertFalse(self.receipt["authenticated_external_source"])

    def test_trust_flags_must_have_exact_bool_type(self):
        for name in ("synthetic_only", "original_bytes_match",
                     "original_span_metadata_linked",
                     "authenticated_external_source",
                     "real_sec_network_called", "real_filing_retrieved",
                     "official_submission_made", "numeric_facts_authenticated"):
            with self.subTest(name=name):
                changed = dict(self.receipt, **{name: 1 if self.receipt[name] else 0})
                self.assertFalse(_valid_dl_archive_receipt(changed))
        self.assertFalse(_valid_dl_archive_receipt(None))

    def test_forged_identity_links_and_digest_are_rejected(self):
        for name, value in (
            ("issuer_cik", "0000000002"),
            ("accession", "0000000001-25-000009"),
            ("source_uri", "https://unsafe.example/a.htm"),
            ("original_filing_sha256", "xyz"),
            ("submissions_sha256", self.receipt["original_filing_sha256"]),
            ("kic_original_crosslink", "authenticated_source"),
        ):
            with self.subTest(name=name):
                self.assertFalse(_valid_dl_archive_receipt(dict(self.receipt, **{name: value})))

    def test_malformed_positions_and_unescaped_html_are_rejected(self):
        for name, value in (
            ("source_byte_start", True), ("source_byte_start", -1),
            ("source_byte_end", 999999),
            ("source_byte_end", self.receipt["source_byte_start"] + 1),
            ("escaped_context", "<script>alert(1)</script>"),
            ("escaped_context", "TEST_LITERAL_SOURCE_SPAN" * 300),
        ):
            with self.subTest(name=name):
                self.assertFalse(_valid_dl_archive_receipt(dict(self.receipt, **{name: value})))

    def test_card_only_uses_code_to_show_escaped_html(self):
        st = Mock()
        with patch("proofinvest.kic_dl_original_demo.replay_original",
                   return_value=copy.deepcopy(self.receipt)):
            _render_dl_archive_case(st)
        st.code.assert_called_once_with(self.receipt["escaped_context"], language="text")
        st.markdown.assert_not_called()
        st.error.assert_not_called()
        self.assertIn("&lt;script&gt;", st.code.call_args.args[0])

    def test_bad_receipt_never_shows_source_snippet_or_dataframe(self):
        st = Mock()
        poisoned = dict(self.receipt, authenticated_external_source=True)
        with patch("proofinvest.kic_dl_original_demo.replay_original",
                   return_value=poisoned):
            _render_dl_archive_case(st)
        st.error.assert_called_once()
        st.code.assert_not_called()
        st.dataframe.assert_not_called()

    def test_streamlit_app_automated_archive_mode_without_browser(self):
        from streamlit.testing.v1 import AppTest

        path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        at = AppTest.from_file(str(path)).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        choice = "DL 공시 원문 근거 추적 — 합성 오프라인"
        self.assertIn(choice, at.selectbox[0].options)
        at.selectbox[0].set_value(choice).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertIn("DL 원문 근거 추적", at.title[0].value)
        self.assertTrue(any("SYNTHETIC_ONLY" in item.value for item in at.warning))
        self.assertFalse(at.error)
        self.assertFalse(at.metric)
        self.assertFalse(at.button)

    def test_good_archive_mode_download_buttons_are_strictly_synthetic(self):
        from unittest.mock import Mock
        st = Mock()
        with patch("proofinvest.kic_dl_original_demo.replay_original",
                   return_value=copy.deepcopy(self.receipt)):
            _render_dl_archive_case(st)
        self.assertEqual(st.download_button.call_count, 2)
        first, second = st.download_button.call_args_list
        self.assertIn("SYNTHETIC_UNVERIFIED", first.kwargs["file_name"])
        self.assertIn("SYNTHETIC_UNVERIFIED", second.kwargs["file_name"])
        self.assertEqual(first.kwargs["mime"], "application/json")
        self.assertEqual(second.kwargs["mime"], "text/markdown")
        import json
        blob = json.loads(first.kwargs["data"])
        self.assertEqual(blob["source"]["archived_original_sha256"],
                         self.receipt["original_filing_sha256"])
        self.assertTrue(all(value is False for value in blob["authenticity"].values()))
        self.assertIn("Not a real SEC report", second.kwargs["data"])
        self.assertNotIn("<script>", second.kwargs["data"])
        st.error.assert_not_called()

    def test_bad_report_blocks_all_download_buttons(self):
        from unittest.mock import Mock
        st = Mock()
        with patch("proofinvest.kic_dl_original_demo.replay_original",
                   return_value=copy.deepcopy(self.receipt)):
            with patch("proofinvest.evidence_report.build_synthetic_evidence_report",
                       side_effect=ValueError("injected")):
                _render_dl_archive_case(st)
        st.error.assert_called_once()
        st.download_button.assert_not_called()

    def test_mismatched_report_identity_blocks_download(self):
        from unittest.mock import Mock
        from proofinvest.evidence_report import build_synthetic_evidence_report
        altered = build_synthetic_evidence_report()
        altered["issuer"]["cik"] = "0000000002"
        st = Mock()
        with patch("proofinvest.kic_dl_original_demo.replay_original",
                   return_value=copy.deepcopy(self.receipt)):
            with patch("proofinvest.evidence_report.build_synthetic_evidence_report",
                       return_value=altered):
                _render_dl_archive_case(st)
        st.error.assert_called_once()
        st.download_button.assert_not_called()


if __name__ == "__main__":
    unittest.main()
