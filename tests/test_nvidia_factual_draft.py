"""Offline tests for genuine NVIDIA issuer-backed numeric draft verification."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from proofinvest.nvidia_factual_draft import verify_nvidia_factual_draft
from proofinvest.nvidia_real_issuer_review import (
    actual_nvidia_issuer_receipt, review_nvidia_actual_release,
)


def valid_proposal():
    reviewed = review_nvidia_actual_release(
        as_of="2026-11-05", receipt=actual_nvidia_issuer_receipt())
    assert reviewed["status"] == "REAL_NVDA_FY2026_2025_ISSUER_GAAP_REVIEW_LIMITED"
    facts = reviewed["evidence"]["metrics"]
    return {
        "schema": "kuodra.nvda-issuer-factual-draft.v1",
        "ticker": "NVDA",
        "source_sha256": reviewed["evidence"]["issuer_source_sha256"],
        "decision": "HUMAN_REVIEW_ONLY",
        "claims": [
            {"metric": "revenue_growth_pct", "value": facts["revenue_growth_pct"]},
            {"metric": "cfo_to_net_income_2026", "value": facts["cfo_to_net_income_2026"]},
            {"metric": "ar_growth_minus_revenue_pp", "value": facts["ar_growth_minus_revenue_pp"]},
            {"metric": "inventory_growth_minus_revenue_pp",
             "value": facts["inventory_growth_minus_revenue_pp"]},
        ],
    }


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


class GenuineIssuerNumericDraftTests(unittest.TestCase):
    def test_all_four_real_issuer_facts_match_with_pinned_sha_and_hold(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("no network")) as network:
            result = verify_nvidia_factual_draft(raw(valid_proposal()))
        network.assert_not_called()
        self.assertEqual(result["status"],
                         "REAL_ISSUER_NUMERIC_FACTS_MATCH_FOR_HUMAN_REVIEW")
        self.assertEqual(result["claim_count"], 4)
        self.assertEqual(result["claims"][0]["value"], "65.47")
        self.assertEqual(result["claims"][1]["value"], "0.8555")
        self.assertEqual(result["claims"][3]["value"], "46.86")
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["source_commercial_ai_rights_verified"])
        self.assertFalse(result["source_authenticated_by_sec"])
        self.assertFalse(result["llm_invoked"])
        self.assertFalse(result["trade_executed"])
        self.assertEqual(result["external_network_requests"], 0)

    def test_all_or_nothing_rejects_mismatches_forecasts_and_policy(self):
        baseline = valid_proposal()
        cases = [
            ("wrong_value", lambda o: o["claims"][0].update(value="65.48")),
            ("rounded_value", lambda o: o["claims"][0].update(value="65.5")),
            ("duplicate_metric", lambda o: o["claims"][1].update(metric="revenue_growth_pct")),
            ("unknown_metric", lambda o: o["claims"][1].update(metric="market_bubble_pct")),
            ("forecast", lambda o: o["claims"][0].update(forecast="BUY")),
            ("approval", lambda o: o.update(decision="APPROVE")),
            ("wrong_issuer", lambda o: o.update(ticker="AMD")),
            ("wrong_source_sha", lambda o: o.update(source_sha256="0" * 64)),
            ("hallucinated_text", lambda o: o.update(explanation="guaranteed growth")),
            ("one_fact_only", lambda o: o.update(claims=o["claims"][:1])),
            ("wrong_unit_number", lambda o: o["claims"][0].update(value=65.47)),
        ]
        for name, alter in cases:
            proposal = deepcopy(baseline)
            alter(proposal)
            with self.subTest(case=name):
                result = verify_nvidia_factual_draft(raw(proposal))
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["trade_executed"])
                self.assertNotIn("claims", result)

    def test_malformed_duplicate_keys_nonfinite_and_long_draft(self):
        for payload in (
            b'{"schema":"x","schema":"y"}',
            b'{"schema":NaN}',
            b'{"schema":',
            b"a" * 4097,
            b"",
        ):
            with self.subTest(payload=payload[:25]):
                self.assertEqual(verify_nvidia_factual_draft(payload)["status"], "BLOCKED")

    def test_revoked_source_review_fails_closed(self):
        with patch(
            "proofinvest.nvidia_factual_draft.review_nvidia_actual_release",
            return_value={"status": "BLOCKED"}
        ):
            result = verify_nvidia_factual_draft(raw(valid_proposal()))
        self.assertEqual(result["status"], "BLOCKED")

    def test_streamlit_ui_can_paste_real_draft_and_reject_hallucination(self):
        from streamlit.testing.v1 import AppTest
        app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        at = AppTest.from_file(str(app)).run(timeout=30)
        at.selectbox[0].set_value(
            "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"
        ).run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        draft = next(x for x in at.text_area if x.key == "p217_nvda_fact_draft")
        draft.set_value(raw(valid_proposal()).decode("utf-8")).run(timeout=30)
        next(x for x in at.button if x.key == "p217_nvda_fact_check").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("초안이 일치합니다" in x.value for x in at.success))
        proposal = valid_proposal()
        proposal["claims"][0]["value"] = "999.99"
        next(x for x in at.text_area if x.key == "p217_nvda_fact_draft").set_value(
            raw(proposal).decode("utf-8")
        ).run(timeout=30)
        next(x for x in at.button if x.key == "p217_nvda_fact_check").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("불일치" in x.value for x in at.warning))
        self.assertFalse(any("초안이 일치합니다" in x.value for x in at.success))


if __name__ == "__main__":
    unittest.main()
