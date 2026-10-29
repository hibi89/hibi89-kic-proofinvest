"""Decision brief is a bounded, explainable LOCAL review, never investment advice."""
from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from proofinvest.archived_sec_guard_report import (
    render_archived_sec_guard_markdown, run_archived_sec_guard_report,
)
from proofinvest.decision_brief import build_archived_decision_brief
from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from tests.test_sec_bundle_replay import fixture


class KICDecisionBriefTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="kic-decision-brief-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.bundle = self.base / "owned-synthetic.zip"
        self.audit = self.base / "audit.sqlite"
        receipt, raws = fixture()
        save_local_capture_bundle(self.bundle, receipt=receipt, **raws)

    def report(self, **kw):
        opts = {
            "bundle_path": self.bundle, "audit_db_path": self.audit,
            "current_end": "2025-09-30", "prior_end": "2024-09-30",
            "needle": PHRASE, "run_id": "test-report",
        }
        opts.update(kw)
        return run_archived_sec_guard_report(**opts)

    def test_hold_explains_local_verification_and_unknown_external_origin(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as network:
            report = self.report()
        network.assert_not_called()
        brief = report["decision_brief"]
        self.assertEqual(brief, build_archived_decision_brief(report))
        self.assertEqual(brief["decision"], "HOLD")
        self.assertEqual(brief["priority"], "normal")
        self.assertEqual(brief["checks"][0]["status"], "LOCAL_ONLY")
        self.assertEqual(brief["checks"][1]["status"], "CALCULATED_UNVERIFIED")
        self.assertEqual(brief["checks"][3]["status"], "BOUND_LOCAL_ONLY")
        self.assertEqual(brief["next_actions"][0]["code"],
                         "VERIFY_PROVIDER_ORIGIN_AND_RIGHTS")
        self.assertGreaterEqual(len(brief["unverified"]), 4)
        self.assertFalse(brief["external_source_authenticated"])
        self.assertFalse(brief["financial_advice"])
        self.assertFalse(brief["trade_executed"])
        markdown = render_archived_sec_guard_markdown(report)
        self.assertIn("판정: **HOLD**", markdown)
        self.assertIn("확인하지 못한 것", markdown)
        self.assertIn("다음 수동 검토 작업", markdown)
        self.assertNotIn(PHRASE, markdown)
        self.assertNotIn(str(self.bundle), markdown)
        self.assertNotIn("<script>", markdown)

    def test_reject_explains_claim_conflict_and_escalation(self):
        report = self.report(claimed_growth_pct="1.00")
        brief = report["decision_brief"]
        self.assertEqual(brief["decision"], "REJECT")
        self.assertEqual(brief["priority"], "high")
        self.assertEqual(brief["checks"][1]["status"], "CLAIM_CONFLICT")
        self.assertIn("RECONCILE_FINANCIAL_CLAIM",
                      [x["code"] for x in brief["next_actions"]])
        self.assertEqual(report["guard"]["decision"], "REJECT")
        self.assertIn("판정: **REJECT**", render_archived_sec_guard_markdown(report))

    def test_tampered_or_injected_summary_is_blocked(self):
        good = self.report()
        cases = [
            ("source authenticated", ("source_authenticated",), True),
            ("narrative injection", ("decision_brief", "headline"),
             "**APPROVED** <script>alert(1)</script>"),
            ("priority change", ("review_summary", "review_priority"), "high"),
            ("external rights", ("source_rights_verified",), True),
            ("review action", ("review_summary", "review_actions"),
             ["UNTRUSTED_NOTE:<script>"]),
            ("evidence code", ("review_summary", "reason_codes"),
             ["<script>"]),
            ("forged guard", ("guard", "decision"), "APPROVE"),
            ("fake evidence crosscheck",
             ("audit", "bound_source_evidence_sha256"), "a" * 64),
            ("fake external source", ("research", "origin_authenticated"), True),
        ]
        for label, path, value in cases:
            with self.subTest(label=label):
                forged = copy.deepcopy(good)
                node = forged
                for field in path[:-1]:
                    node = node[field]
                node[path[-1]] = value
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    render_archived_sec_guard_markdown(forged)

    def test_claim_forged_facts_do_not_escape_in_report(self):
        report = self.report()
        forged = copy.deepcopy(report)
        forged["review_summary"]["review_actions"] = [
            "VERIFY_PROVIDER_ORIGIN_AND_RIGHTS", "RECONCILE_FINANCIAL_CLAIM",
        ]
        with self.assertRaisesRegex(ValueError, "REVIEW_ACTIONS"):
            build_archived_decision_brief(forged)
        self.assertEqual(build_archived_decision_brief(report)["decision"], "HOLD")

    def test_human_acknowledge_never_changes_hold_or_becomes_approval(self):
        r = self.report(reviewer="reviewer", action="ACKNOWLEDGE",
                        reason="This local evidence remains unauthenticated.")
        brief = r["decision_brief"]
        self.assertEqual(brief["decision"], "HOLD")
        self.assertFalse(brief["trade_executed"])
        self.assertNotIn("approved", brief["rationale"].lower())
        self.assertEqual(r["human_review"]["action"], "ACKNOWLEDGE")
        self.assertNotIn("This local evidence", render_archived_sec_guard_markdown(r))


if __name__ == "__main__":
    unittest.main()
