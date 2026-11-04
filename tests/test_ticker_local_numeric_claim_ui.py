"""P186 real local Streamlit control boundary, offline UI/no hidden HTTP."""
from __future__ import annotations

from dataclasses import dataclass
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_numeric_claim_ui import (
    _bounded_upload, render_local_numeric_claim_ui,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload


@dataclass
class Upload:
    raw: bytes
    @property
    def size(self):
        return len(self.raw)
    def getvalue(self):
        return self.raw


class FakeStreamlit:
    def __init__(self, *, open_panel=False, click=False, review=None,
                 rights=None, draft=None):
        self.open_panel = open_panel
        self.click = click
        self.review = review
        self.rights = rights
        self.draft = draft
        self.disabled = []
        self.successes = []
        self.warnings = []
        self.codes = []
        self.results = []
        self.notes = []

    def subheader(self, title):
        pass
    def caption(self, text):
        pass
    def checkbox(self, label, *, value, key):
        return self.open_panel
    def file_uploader(self, label, *, type, key):
        return {
            "kuodra_p186_review": self.review,
            "kuodra_p186_rights": self.rights,
            "kuodra_p186_draft": self.draft,
        }[key]
    def button(self, label, *, disabled, key):
        self.disabled.append(disabled)
        return self.click
    def warning(self, message):
        self.warnings.append(message)
    def success(self, message):
        self.successes.append(message)
    def code(self, code, *, language):
        self.codes.append(code)
    def json(self, obj):
        self.results.append(obj)
    def info(self, text):
        self.notes.append(text)


class NumericClaimUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f = build_offline_initial_review(**payload())
        assert f["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
        cls.review = Upload(f["review_packet"])
        cls.rights = Upload(f["source_clearance_report"])
        packet = json.loads(cls.review.raw)
        cls.draft = Upload(json.dumps({
            "schema": "kuodra.local-model-numeric-claim.v1",
            "engine": "A", "claim_kind": "OBSERVED_PRICE_RETURN_GAP_PP",
            "gap_pp": packet["explanation"]["findings"][0]["simple_return_gap_pp"],
            "decision": "HUMAN_REVIEW_ONLY",
        }, separators=(",", ":")).encode())

    def render(self, ui):
        with patch("proofinvest.ticker_local_numeric_claim_ui.local_workspace_enabled",
                   return_value=True):
            render_local_numeric_claim_ui(ui)
        return ui

    def test_hidden_or_missing_inputs_never_call_numeric_parser(self):
        with patch(
            "proofinvest.ticker_local_model_numeric_claim.verify_local_model_numeric_claim",
            side_effect=AssertionError("NO_FILE_READ_UNTIL_READY"),
        ):
            hidden = self.render(FakeStreamlit(click=True))
            self.assertEqual(hidden.disabled, [])
            for opts in (
                {}, {"review": self.review},
                {"review": self.review, "rights": self.rights},
                {"draft": self.draft, "rights": self.rights},
            ):
                ui = self.render(FakeStreamlit(open_panel=True, click=True, **opts))
                self.assertTrue(ui.disabled[-1])
                self.assertEqual(ui.codes, ["NUMERIC_UI_THREE_INPUTS_REQUIRED"])
                self.assertEqual(ui.successes, [])

    def test_one_click_actual_local_decimal_result_and_no_external_http(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_REQUEST")):
            ui = self.render(FakeStreamlit(
                open_panel=True, click=True,
                review=self.review, rights=self.rights, draft=self.draft,
            ))
        self.assertEqual(ui.disabled, [False])
        self.assertEqual(len(ui.successes), 1)
        result = ui.results[0]
        self.assertEqual(result["basis"], "PRICE_ONLY_CLOSE_VS_ACTUAL_NASDAQ_100")
        self.assertEqual(result["guard_policy_preview"], "HOLD")
        self.assertEqual(result["simple_return_gap_pp"],
                         json.loads(self.draft.raw)["gap_pp"])
        self.assertFalse(result["source_rights_verified"])
        self.assertFalse(result["trade_executed"])
        self.assertEqual(len(ui.notes), 1)

    def test_tampered_draft_fails_closed_without_success(self):
        wrong = json.loads(self.draft.raw)
        wrong["gap_pp"] = "999.9999"
        ui = self.render(FakeStreamlit(
            open_panel=True, click=True, review=self.review,
            rights=self.rights, draft=Upload(json.dumps(wrong).encode()),
        ))
        self.assertFalse(ui.successes)
        self.assertEqual(ui.codes, ["MODEL_NUMERIC_CLAIM_NOT_SUPPORTED"])
        self.assertFalse(ui.results)

    def test_bad_or_oversized_bytes_and_unsafe_forged_success_are_blocked(self):
        with self.assertRaises(ValueError):
            _bounded_upload(Upload(b"x" * 1025), 1024)
        with self.assertRaises(ValueError):
            _bounded_upload(Upload(b""), 1024)
        with patch(
            "proofinvest.ticker_local_model_numeric_claim.verify_local_model_numeric_claim",
            return_value={
                "status": "LOCAL_MODEL_NUMERIC_MATCH_TO_UNSIGNED_REVIEW_ONLY",
                "local_numeric_claim_recomputed": True,
                "publisher_source_authenticated": True,
                "source_rights_verified": False,
            },
        ):
            ui = self.render(FakeStreamlit(
                open_panel=True, click=True, review=self.review,
                rights=self.rights, draft=self.draft,
            ))
        self.assertFalse(ui.successes)
        self.assertEqual(ui.codes, ["NUMERIC_UI_REJECTED"])


if __name__ == "__main__":
    unittest.main()
