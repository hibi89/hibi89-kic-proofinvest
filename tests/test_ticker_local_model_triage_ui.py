"""P180 Streamlit local-model panel: input constraints and no hidden HTTP."""
from __future__ import annotations

from dataclasses import dataclass
import unittest
from unittest.mock import patch

from proofinvest.ticker_local_model_triage_ui import (
    _uploaded, render_local_model_triage_ui,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload


@dataclass
class _Upload:
    raw: bytes

    @property
    def size(self):
        return len(self.raw)

    def getvalue(self):
        return self.raw


class _FakeStreamlit:
    def __init__(self, *, open_panel=False, consent_local=False,
                 consent_data=False, clicked=False, review=None, rights=None,
                 model="test-ui-model", port="11434"):
        self.open_panel = open_panel
        self.consent_local = consent_local
        self.consent_data = consent_data
        self.clicked = clicked
        self.review = review
        self.rights = rights
        self.model = model
        self.port = port
        self.buttons = []
        self.successes = []
        self.warnings = []
        self.results = []
        self.interpretations = []
        self.codes = []

    def subheader(self, text):
        pass

    def caption(self, text):
        pass

    def checkbox(self, label, *, key, value):
        return {
            "kuodra_p180_panel": self.open_panel,
            "kuodra_p180_consent_local": self.consent_local,
            "kuodra_p180_consent_derived": self.consent_data,
        }[key]

    def file_uploader(self, label, *, type, key):
        return self.review if key == "kuodra_p180_review" else self.rights

    def text_input(self, label, *, value, max_chars, key):
        return self.port if key == "kuodra_p180_port" else self.model

    def button(self, label, *, disabled, key):
        self.buttons.append(disabled)
        return self.clicked

    def success(self, label):
        self.successes.append(label)

    def warning(self, text):
        self.warnings.append(text)

    def code(self, text, *, language):
        self.codes.append(text)

    def json(self, content):
        self.results.append(content)

    def info(self, text):
        self.interpretations.append(text)


class TickerLocalModelTriageUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = build_offline_initial_review(**payload())
        assert fixture["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
        cls.review = _Upload(fixture["review_packet"])
        cls.rights = _Upload(fixture["source_clearance_report"])

    def call(self, fake):
        with patch("proofinvest.ticker_local_model_triage_ui.local_workspace_enabled",
                   return_value=True):
            render_local_model_triage_ui(fake)
        return fake

    def test_default_closed_no_file_read_or_http(self):
        fake = self.call(_FakeStreamlit(clicked=True))
        self.assertFalse(fake.buttons)
        self.assertFalse(fake.successes)

    def test_dual_explicit_consent_and_both_receipts_required(self):
        for settings in (
            {"open_panel": True},
            {"open_panel": True, "review": self.review},
            {"open_panel": True, "review": self.review, "rights": self.rights},
            {"open_panel": True, "review": self.review, "rights": self.rights,
             "consent_local": True},
            {"open_panel": True, "review": self.review, "rights": self.rights,
             "consent_data": True},
        ):
            with self.subTest(settings=settings):
                with patch("proofinvest.ticker_local_model_triage.triage_review",
                           side_effect=AssertionError("NO_HTTP_BEFORE_CONSENT")):
                    fake = self.call(_FakeStreamlit(clicked=True, **settings))
                self.assertTrue(fake.buttons[-1])
                self.assertFalse(fake.successes)

    def test_happy_path_masks_model_text_and_preserves_guard(self):
        receipt = {
            "status": "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN",
            "model_protocol_http_verified": True,
            "source_rights_verified": False,
            "model_inference_authenticated": False,
            "ai_agent_executed": False,
            "trade_executed": False,
            "guard_policy_preview": "HOLD",
            "focus_engine": "B",
            "focus_status": "REVIEWED_UNVERIFIED",
            "safe_existing_interpretation": "검토가 필요하며 결과는 미인증입니다.",
        }
        with patch("proofinvest.ticker_local_model_triage.triage_review",
                   return_value=receipt) as request:
            ui = self.call(_FakeStreamlit(
                open_panel=True, review=self.review, rights=self.rights,
                consent_local=True, consent_data=True, clicked=True))
        self.assertEqual(len(ui.successes), 1)
        self.assertEqual(ui.results[0]["focus_engine"], "B")
        self.assertFalse(ui.results[0]["source_rights_verified"])
        self.assertFalse(ui.results[0]["ai_agent_executed"])
        self.assertEqual(ui.results[0]["guard_policy_preview"], "HOLD")
        self.assertEqual(ui.interpretations, [receipt["safe_existing_interpretation"]])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["model"], "test-ui-model")

    def test_unexpected_rights_or_model_auth_claim_is_not_rendered(self):
        for forged in (
            {"source_rights_verified": True},
            {"model_inference_authenticated": True},
            {"guard_policy_preview": "APPROVE"},
            {"trade_executed": True},
        ):
            base = {
                "status": "LOCAL_MODEL_TRIAGE_PROTOCOL_UNVERIFIED_MODEL_ORIGIN",
                "model_protocol_http_verified": True,
                "source_rights_verified": False,
                "model_inference_authenticated": False,
                "ai_agent_executed": False, "trade_executed": False,
                "guard_policy_preview": "HOLD",
            }
            with self.subTest(forged=forged), patch(
                "proofinvest.ticker_local_model_triage.triage_review",
                return_value={**base, **forged},
            ):
                ui = self.call(_FakeStreamlit(
                    open_panel=True, review=self.review, rights=self.rights,
                    consent_local=True, consent_data=True, clicked=True))
                self.assertFalse(ui.successes)
                self.assertEqual(ui.codes, ["LOCAL_MODEL_TRIAGE_BLOCKED"])

    def test_invalid_port_and_unverified_packet_fail_before_http(self):
        for port in ("", "0", "80", "65536", "host:11434", "abc"):
            with self.subTest(port=port), patch(
                "proofinvest.ticker_local_model_triage.triage_review",
                side_effect=AssertionError("NO_INVALID_PORT_HTTP"),
            ):
                ui = self.call(_FakeStreamlit(
                    open_panel=True, review=self.review, rights=self.rights,
                    consent_local=True, consent_data=True, clicked=True,
                    port=port))
                self.assertEqual(ui.codes, ["LOCAL_MODEL_CONSENT_OR_PORT_INVALID"])
        with patch("proofinvest.ticker_local_model_triage.triage_review",
                   return_value={"status": "BLOCKED",
                                 "reason_code": "REVIEW_PACKET_OR_CLEARANCE_INVALID"}):
            ui = self.call(_FakeStreamlit(
                open_panel=True, review=_Upload(self.review.raw + b" "),
                rights=self.rights, consent_local=True, consent_data=True,
                clicked=True))
        self.assertEqual(ui.codes, ["REVIEW_PACKET_OR_CLEARANCE_INVALID"])
        self.assertFalse(ui.successes)

    def test_uploaded_regular_bytes_and_size_strict(self):
        with self.assertRaises(ValueError):
            _uploaded(_Upload(b"x"*28673), 28672)
        with self.assertRaises(ValueError):
            _uploaded(_Upload(b""), 28672)


if __name__ == "__main__":
    unittest.main()
