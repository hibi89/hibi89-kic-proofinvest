"""KIC temporal baseline Streamlit mode: strict synthetic-only evaluation."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from proofinvest.temporal_baseline import evaluate_historical_baseline, synthetic_temporal_rows
from proofinvest.temporal_baseline_ui import _safe_baseline

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
MODE = "AutoML 시간순 검증 — 합성 기준 모델"


class KicTemporalBaselineUITests(unittest.TestCase):
    def screen(self):
        at = AppTest.from_file(str(APP)).run(timeout=20)
        self.assertIn(MODE, at.selectbox[0].options)
        at.selectbox[0].set_value(MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        return at

    def test_no_eager_model_training_or_evaluation(self):
        with patch("proofinvest.temporal_baseline_ui.evaluate_historical_baseline",
                   side_effect=AssertionError("must wait for click")):
            at = self.screen()
        self.assertTrue(any("SYNTHETIC_BASELINE_ONLY" in w.value
                            for w in at.warning))
        self.assertTrue(any(m.label == "실제 데이터 ML 학습"
                            and m.value == "NO_TRAIN" for m in at.metric))
        self.assertFalse(any(m.label == "미래 구간 MAE" for m in at.metric))
        self.assertFalse(at.error)

    def test_explicit_click_runs_40_period_historical_holdout(self):
        at = self.screen()
        at.button(key="kic_temporal_baseline_run").click().run(timeout=30)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("합성 기간 시간순 분리" in s.value for s in at.success))
        self.assertTrue(any(m.label == "학습 기간 관측치" and m.value == "32"
                            for m in at.metric))
        self.assertTrue(any(m.label == "테스트 기간 관측치" and m.value == "8"
                            for m in at.metric))
        self.assertTrue(any(m.label == "지연 공개로 제외된 학습치" and m.value == "0"
                            for m in at.metric))
        self.assertTrue(any(m.label == "실제 데이터 ML 학습"
                            and m.value == "NO_TRAIN" for m in at.metric))
        self.assertFalse(at.error)

    def test_fail_closed_blocks_report(self):
        at = self.screen()
        with patch("proofinvest.temporal_baseline_ui.evaluate_historical_baseline",
                   return_value={"status": "BASELINE_ONLY", "model_trained": True}):
            at.button(key="kic_temporal_baseline_run").click().run(timeout=30)
        self.assertFalse(at.exception)
        self.assertTrue(any("기준모델 결과를 표시하지 않습니다" in e.value for e in at.error))
        self.assertFalse(at.success)

    def test_malicious_report_flags_do_not_pass(self):
        x = evaluate_historical_baseline(
            synthetic_temporal_rows(), evaluation_as_of="2025-01-01T00:00:00Z")
        self.assertTrue(_safe_baseline(x))
        for key in ("model_trained", "trade_executed", "live_api_called",
                    "external_source_authenticated", "guard_input_eligible",
                    "investment_recommendation"):
            with self.subTest(key=key):
                self.assertFalse(_safe_baseline({**x, key: True}))
        self.assertFalse(_safe_baseline({**x, "train_end": "9999-01-01T00:00:00Z"}))
        self.assertFalse(_safe_baseline({**x, "metrics": {"heldout_mae": "NaN"}}))


if __name__ == "__main__":
    unittest.main()
