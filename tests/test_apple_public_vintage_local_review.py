"""P189 public catalog vintage must gate local review before seven-tool replay."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from proofinvest.apple_public_vintage_local_review import (
    review_apple_public_vintage_local_sources as review,
)


def sources(accession="0000320193-26-000026", fiscal_end="2026-09-26",
            filing_day="2026-11-03"):
    return {
        "ticker_map": json.dumps({
            "0": {"ticker": "AAPL", "cik_str": 320193,
                  "title": "Apple Inc."}}).encode(),
        "submissions": json.dumps({"cik": 320193, "filings": {"recent": {
            "form": ["10-K"], "accessionNumber": [accession],
            "filingDate": [filing_day], "reportDate": [fiscal_end],
            "primaryDocument": ["aapl-20260926.htm"],
        }}}).encode(),
        "companyfacts": b"{}",
        "original_10k": b"<html>NOT_AUTHENTICATED_FIXTURE</html>",
    }


def reviewed():
    return {
        "status": "READY_FOR_HUMAN_REVIEW_UNVERIFIED",
        "tool_calls_executed": 7,
        "tool_trace": [{"accepted": True, "network_requests": 0}
                       for _ in range(7)],
        "receipt": {
            "selected_10k_accession": "0000320193-26-000026",
            "selected_10k_filing_date": "2026-11-03",
            "requested_as_of": "2026-11-05",
            "source_authenticated": False,
            "source_rights_verified": False,
        },
        "report": {
            "guard_policy_preview": "HOLD",
            "source_rights_ledger": {"external_sharing_allowed": False},
        },
        "source_authenticated": False,
        "source_rights_verified": False,
        "ai_agent_executed": False,
        "guard_executed": False,
        "trade_executed": False,
    }


class ApplePublicVintageLocalReviewTests(unittest.TestCase):
    def test_matching_public_metadata_calls_seven_tool_workflow_once(self):
        with patch("proofinvest.apple_public_vintage_local_review.run_local_ticker_workflow",
                   return_value=reviewed()) as run:
            result = review(as_of="2026-11-05", sources=sources())
        run.assert_called_once()
        self.assertEqual(result["status"],
                         "LOCAL_HUMAN_REVIEW_PUBLIC_VINTAGE_MATCHED_UNAUTHENTICATED")
        self.assertEqual(result["filing"]["accession"], "0000320193-26-000026")
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_rights_verified"])
        self.assertEqual(result["external_network_requests"], 0)

    def test_stale_2025_filing_is_blocked_before_pipeline(self):
        old = sources(accession="0000320193-25-000079",
                      fiscal_end="2025-09-27", filing_day="2025-10-31")
        with patch("proofinvest.apple_public_vintage_local_review.run_local_ticker_workflow") as run:
            result = review(as_of="2026-11-05", sources=old)
        run.assert_not_called()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["report"])

    def test_wrong_period_wrong_filing_future_and_invalid_inputs_fail_closed(self):
        cases = [
            ("2026-11-05", sources(fiscal_end="2025-09-27")),
            ("2026-11-05", sources(accession="0000320193-26-000025")),
            ("2026-11-03", sources()),
            ("2026-11-06", sources()),
            ("2026-11-05", sources() | {"original_10k": b""}),
            ("2026-11-05", sources() | {"extraneous": b"x"}),
            ("2026-11-05", None),
        ]
        with patch("proofinvest.apple_public_vintage_local_review.run_local_ticker_workflow") as run:
            for as_of, raw in cases:
                with self.subTest(as_of=as_of, source=raw):
                    out = review(as_of=as_of, sources=raw)
                    self.assertEqual(out["status"], "BLOCKED")
                    self.assertFalse(out["trade_executed"])
                    self.assertIsNone(out["report"])
        run.assert_not_called()

    def test_real_local_pipeline_rejects_fake_originals_not_false_success(self):
        out = review(as_of="2026-11-05", sources=sources())
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason_code"],
                         "SEVEN_STAGE_OFFLINE_REPLAY_OR_TRUST_CONTRACT_BLOCKED")
        self.assertIsNone(out["report"])

    def test_malicious_workflow_claims_must_never_escape(self):
        for changed in (
            {"source_authenticated": True},
            {"source_rights_verified": True},
            {"trade_executed": True},
            {"tool_calls_executed": 6},
            {"report": {"guard_policy_preview": "APPROVE",
                        "source_rights_ledger": {"external_sharing_allowed": False}}},
            {"receipt": dict(reviewed()["receipt"], selected_10k_accession="FAKE")},
        ):
            fake = dict(reviewed(), **changed)
            with patch("proofinvest.apple_public_vintage_local_review.run_local_ticker_workflow",
                       return_value=fake):
                out = review(as_of="2026-11-05", sources=sources())
            self.assertEqual(out["status"], "BLOCKED")
            self.assertIsNone(out["report"])


if __name__ == "__main__":
    unittest.main()
