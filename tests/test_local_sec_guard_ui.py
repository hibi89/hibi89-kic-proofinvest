"""Actual SEC->Guard temporary SQLite replay and Streamlit AppTest."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.local_sec_guard_ui import run_synthetic_guard_case, export_synthetic_guard_json


class LocalSecGuardUiTests(unittest.TestCase):
    def test_actual_three_scenarios_without_any_http(self):
        expected = {
            "matched": ("calculated_unverified", "HOLD"),
            "conflict": ("conflict", "REJECT"),
            "script": ("calculated_unverified", "HOLD"),
        }
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as network:
            for case, (status, decision) in expected.items():
                with self.subTest(case=case):
                    r = run_synthetic_guard_case(case)
                    self.assertEqual(r["verification"]["status"], status)
                    self.assertEqual(r["guard"]["decision"], decision)
                    self.assertTrue(r["audit_chain_valid"])
                    self.assertTrue(all(v is False for v in r["limits"].values()))
            network.assert_not_called()

    def test_unknown_case_fails_without_running_review(self):
        with patch("proofinvest.local_sec_guard_ui.review_local_sec_with_guard",
                   side_effect=AssertionError("SHOULD_NOT_RUN")) as action:
            with self.assertRaisesRegex(ValueError, "INVALID_SYNTHETIC_CASE"):
                run_synthetic_guard_case("unapproved")
        action.assert_not_called()

    def test_export_is_explicitly_synthetic_and_never_authenticated(self):
        import json
        report = run_synthetic_guard_case("matched")
        receipt = json.loads(export_synthetic_guard_json(report))
        self.assertEqual(receipt["evidence_class"], "SYNTHETIC_ONLY_UNVERIFIED")
        self.assertFalse(receipt["external_source_authenticated"])
        self.assertTrue(receipt["not_investment_advice"])
        self.assertEqual(receipt["report"]["guard"]["decision"], "HOLD")

    def test_export_rejects_forged_production_and_approval_flags(self):
        from copy import deepcopy
        report = run_synthetic_guard_case("matched")
        candidates = [
            {"limits": {**report["limits"], "external_source_authenticated": True}},
            {"limits": {**report["limits"], "extra_certified": True}},
            {"mode": "PRODUCTION_VERIFIED"},
            {"issuer": {**report["issuer"], "cik": "0000320193"}},
            {"guard": {**report["guard"], "decision": "APPROVE"}},
            {"audit_chain_valid": False},
            {"human_review": {"action": "AUTHORIZE_SIMULATION"}},
        ]
        for item in candidates:
            with self.subTest(item=item):
                modified = deepcopy(report)
                modified.update(item)
                with self.assertRaisesRegex(ValueError, "SYNTHETIC_EXPORT_BLOCKED"):
                    export_synthetic_guard_json(modified)

    def test_export_matches_original_fixture_hashes_and_rejects_changes(self):
        from copy import deepcopy
        import hashlib
        from proofinvest.kic_dl_demo import synthetic_submissions
        r = run_synthetic_guard_case("matched")
        self.assertEqual(
            r["source"]["submissions_sha256"],
            hashlib.sha256(synthetic_submissions()).hexdigest(),
        )
        for patch in (
            {"source": {**r["source"], "submissions_sha256": "0" * 64}},
            {"source": {**r["source"], "archived_original_sha256": "f" * 64}},
            {"source": {**r["source"], "companyfacts_sha256": "0" * 64}},
            {"verification": {**r["verification"], "current_amount": "300"}},
            {"verification": {**r["verification"], "growth_pct": "101.00"}},
            {"verification": {**r["verification"], "status": "conflict"}},
            {"guard": {**r["guard"], "source_authenticated": True}},
            {"risk": {**r["risk"], "trade_authorized": True}},
        ):
            with self.subTest(patch=patch):
                forged = deepcopy(r)
                forged.update(patch)
                with self.assertRaisesRegex(ValueError, "SYNTHETIC_EXPORT_BLOCKED"):
                    export_synthetic_guard_json(forged)

    def test_export_works_for_all_three_synthetic_cases(self):
        import json
        for case in ("matched", "conflict", "script"):
            with self.subTest(case=case):
                r = run_synthetic_guard_case(case)
                result = json.loads(export_synthetic_guard_json(r))
                self.assertEqual(result["evidence_class"], "SYNTHETIC_ONLY_UNVERIFIED")
                self.assertEqual(result["report"]["guard"]["decision"],
                                 "REJECT" if case == "conflict" else "HOLD")

    def test_streamlit_new_mode_requires_click(self):
        from streamlit.testing.v1 import AppTest
        file = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(file)).run(timeout=20)
        app.selectbox[0].set_value("SEC→Guard 감사 연결 — 합성 오프라인").run(timeout=20)
        self.assertFalse(app.exception, [str(e.message) for e in app.exception])
        self.assertTrue(any("SYNTHETIC ONLY" in w.value for w in app.warning))
        self.assertFalse(any(m.label == "Guard 판정" for m in app.metric))

    def test_streamlit_click_executes_guard(self):
        from streamlit.testing.v1 import AppTest
        file = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(file)).run(timeout=20)
        app.selectbox[0].set_value("SEC→Guard 감사 연결 — 합성 오프라인").run(timeout=20)
        app.button[0].click().run(timeout=30)
        self.assertFalse(app.exception, [str(e.message) for e in app.exception])
        self.assertTrue(any(m.label == "Guard 판정" and m.value == "HOLD"
                            for m in app.metric))


if __name__ == "__main__":
    unittest.main()
