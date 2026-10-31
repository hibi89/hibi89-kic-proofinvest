"""P59 optional localhost UI for real owner-held original HTML; synthetic specimens.

UI test validates that no raw source, API, Guard writes or source-origin
claims are introduced by the supplementary Apple comparison control.
"""
from __future__ import annotations

from hashlib import sha256
import os
import unittest
from unittest.mock import patch

from proofinvest.kuodra_local_workspace_ui import (
    render_local_apple_10k_original_check,
)
from tests.test_apple_local_html_crosscheck import sample_html


class Upload:
    def __init__(self, content: bytes):
        self.content = content
        self.size = len(content)
        self.read_count = 0

    def getvalue(self):
        self.read_count += 1
        return self.content


class UI:
    def __init__(self, *, clicked=True, address="127.0.0.1"):
        self.clicked = clicked
        self.address = address
        self.buttons = []
        self.statuses = []
        self.errors = []
        self.json_reports = []
        self.captions = []

    def get_option(self, name):
        if name != "server.address":
            raise KeyError(name)
        return self.address

    def subheader(self, text):
        self.statuses.append(("subheader", text))

    def caption(self, text):
        self.captions.append(text)

    def button(self, text, *, key, disabled):
        self.buttons.append((text, key, disabled))
        return self.clicked and not disabled

    def error(self, text):
        self.errors.append(text)

    def success(self, text):
        self.statuses.append(("success", text))

    def json(self, payload):
        self.json_reports.append(payload)


_ARGS = {
    "cik": "0000320193",
    "accession": "0000320193-25-000079",
    "as_of": "2025-10-31",
    "current_end": "2025-09-27",
    "prior_end": "2024-09-28",
}


class AppleHTMLLocalUITests(unittest.TestCase):
    def run_ui(self, st, upload, args=None):
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            return render_local_apple_10k_original_check(
                st, upload=upload, **(_ARGS if args is None else args),
            )

    def test_synthetic_html_clicked_executes_existing_real_engine_b_checks(self):
        raw = sample_html()
        uploaded = Upload(raw)
        st = UI()
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_HTTP")) as remote:
            self.run_ui(st, uploaded)
        remote.assert_not_called()
        self.assertEqual(uploaded.read_count, 1)
        self.assertEqual(st.errors, [])
        self.assertEqual(len(st.json_reports), 1)
        report = st.json_reports[0]
        self.assertEqual(report["matched_numeric_cells"], 24)
        self.assertEqual(report["original_local_html_sha256"], sha256(raw).hexdigest())
        self.assertEqual(report["original_local_html_size"], len(raw))
        self.assertEqual(report["statements_matched"], ["operations", "balance", "cash"])
        self.assertFalse(report["sec_original_file_authenticated"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["full_sec_guard_a_b_c_real_data_verified"])
        self.assertFalse(report["audit_written"])
        self.assertEqual(report["network_requests"], 0)
        self.assertNotIn("content", report)
        self.assertNotIn("original_html", report)
        self.assertNotIn(raw.decode("utf-8")[:80], str(report))
        self.assertIn("미인증", st.statuses[-1][1])

    def test_no_button_or_upload_read_for_another_issuer_or_accession(self):
        for change in ("cik", "accession"):
            args = dict(_ARGS)
            args[change] = "0000000001"
            st, upload = UI(), Upload(sample_html())
            self.run_ui(st, upload, args)
            with self.subTest(change=change):
                self.assertEqual(st.buttons, [])
                self.assertEqual(upload.read_count, 0)
                self.assertEqual(st.json_reports, [])

    def test_click_not_requested_does_not_read_original(self):
        st, upload = UI(clicked=False), Upload(sample_html())
        self.run_ui(st, upload)
        self.assertEqual(upload.read_count, 0)
        self.assertEqual(st.json_reports, [])
        self.assertFalse(st.buttons[0][2])

    def test_wrong_asof_or_period_is_disabled(self):
        for change in ("as_of", "current_end", "prior_end"):
            args = dict(_ARGS)
            args[change] = "2026-11-01"
            st, upload = UI(), Upload(sample_html())
            self.run_ui(st, upload, args)
            with self.subTest(change=change):
                self.assertTrue(st.buttons[0][2])
                self.assertEqual(upload.read_count, 0)
                self.assertEqual(st.json_reports, [])

    def test_no_upload_and_oversize_are_disabled(self):
        st = UI()
        self.run_ui(st, None)
        self.assertTrue(st.buttons[0][2])
        upload = Upload(sample_html())
        upload.size = 25_000_001
        st = UI()
        self.run_ui(st, upload)
        self.assertTrue(st.buttons[0][2])
        self.assertEqual(upload.read_count, 0)

    def test_no_nonloopback_or_without_explicit_env(self):
        for address in ("0.0.0.0", "192.168.0.10", "::"):
            st, upload = UI(address=address), Upload(sample_html())
            self.run_ui(st, upload)
            with self.subTest(address=address):
                self.assertTrue(st.buttons[0][2])
                self.assertEqual(upload.read_count, 0)
        st, upload = UI(), Upload(sample_html())
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "0"}):
            render_local_apple_10k_original_check(st, upload=upload, **_ARGS)
        self.assertTrue(st.buttons[0][2])
        self.assertEqual(upload.read_count, 0)

    def test_bytes_size_mismatch_and_float_metadata_block(self):
        for variant in ("size_mismatch", "float", "fake_raw"):
            st, upload = UI(), Upload(sample_html())
            if variant == "size_mismatch":
                upload.size -= 1
            elif variant == "float":
                upload.size = float(upload.size)
            else:
                upload.content = "HTML NOT BYTES"
            self.run_ui(st, upload)
            with self.subTest(variant=variant):
                if variant == "float":
                    self.assertTrue(st.buttons[0][2])
                    self.assertEqual(upload.read_count, 0)
                else:
                    self.assertEqual(upload.read_count, 1)
                    self.assertEqual(len(st.errors), 1)
                self.assertEqual(st.json_reports, [])

    def test_mismatched_original_html_cannot_print_success(self):
        wrong = sample_html().replace(b"416,161", b"416,162")
        st, upload = UI(), Upload(wrong)
        self.run_ui(st, upload)
        self.assertEqual(len(st.errors), 1)
        self.assertEqual(st.json_reports, [])
        self.assertFalse(any(tag == "success" for tag, _ in st.statuses))
        self.assertEqual(upload.read_count, 1)

    def test_authentication_forgeries_in_verifier_result_rejected(self):
        for field in ("sec_original_file_authenticated",
                      "full_sec_guard_a_b_c_real_data_verified",
                      "original_bytes_retained"):
            with self.subTest(field=field):
                mocked = {
                    "matched_numeric_cells": 24,
                    "original_bytes_retained": False,
                    "sec_original_file_authenticated": False,
                    "full_sec_guard_a_b_c_real_data_verified": False,
                }
                mocked[field] = True
                st, upload = UI(), Upload(sample_html())
                with patch(
                    "proofinvest.apple_local_html_crosscheck.verify_local_apple_10k_html",
                    return_value=mocked,
                ):
                    self.run_ui(st, upload)
                self.assertEqual(st.json_reports, [])
                self.assertEqual(len(st.errors), 1)


if __name__ == "__main__":
    unittest.main()
