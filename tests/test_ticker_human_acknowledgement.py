"""P123 local review requires fresh exact source replay and explicit human click."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_human_acknowledgement import (
    acknowledge_local_ticker_report, acknowledgement_json_bytes,
)
from tests.test_ticker_local_report_replay import report_case, _reseal


def acknowledged(report=None, sources=None, **updates):
    if report is None:
        report, sources = report_case()
    kw = {
        "reviewer_alias": "QA_Operator",
        "review_note": "원본 미인증 및 승인 불가 상태를 읽고 확인함",
        "explicit_acknowledgement": True,
    }
    kw.update(updates)
    return acknowledge_local_ticker_report(report, sources=sources, **kw)


class LocalHumanAcknowledgementTests(unittest.TestCase):
    def test_explicit_human_ack_bound_to_exact_report_without_audit_or_http(self):
        report, sources = report_case()
        before = deepcopy(sources)
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("SEC HTTP FORBIDDEN")) as http:
            receipt = acknowledged(report, sources)
        http.assert_not_called()
        self.assertEqual(receipt["status"], "ACKNOWLEDGED_UNVERIFIED_LOCAL_ONLY")
        self.assertEqual(receipt["action"], "ACKNOWLEDGE_FOR_LOCAL_REVIEW")
        self.assertEqual(receipt["report_sha256"], report["report_sha256"])
        self.assertEqual(receipt["source_sha256"], report["source_sha256"])
        self.assertEqual(receipt["guard_policy_preview_unchanged"], "HOLD")
        self.assertTrue(receipt["report_replay_verified"])
        for key in ("publisher_origin_authenticated",
                    "reviewer_identity_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "contest_submission_allowed",
                    "human_approved", "guard_executed", "audit_written",
                    "trade_executed", "ai_agent_executed"):
            self.assertIs(receipt[key], False, key)
        self.assertEqual(receipt["external_http_requests"], 0)
        self.assertEqual(receipt["reviewer_alias_unverified"], "QA_Operator")
        self.assertEqual(sources, before)
        encoded = acknowledgement_json_bytes(receipt)
        self.assertEqual(json.loads(encoded), receipt)
        payload = dict(receipt)
        actual_digest = payload.pop("receipt_sha256")
        canonical = (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False) + "\n").encode()
        self.assertEqual(actual_digest, sha256(canonical).hexdigest())
        self.assertNotIn("<html", encoded.decode())

    def test_missing_or_invalid_consent_and_reviewer_are_blocked(self):
        for modification in (
            {"explicit_acknowledgement": False},
            {"explicit_acknowledgement": 1},
            {"reviewer_alias": ""},
            {"reviewer_alias": "a"},
            {"reviewer_alias": "somebody@domain.com"},
            {"reviewer_alias": "QA Operator"},
            {"reviewer_alias": "A" * 41},
            {"review_note": "too short"},
            {"review_note": "text\nnewlines are not accepted"},
            {"review_note": "x" * 241},
        ):
            with self.subTest(modification=modification), self.assertRaises(ValueError):
                acknowledged(**modification)

    def test_rehashed_forged_guard_or_external_rights_cannot_be_acknowledged(self):
        report, src = report_case()
        for field, val in (
            ("guard_policy_preview", "REJECT"),
            ("source_authenticated", True),
            ("official_contest_submission", True),
        ):
            fake = deepcopy(report)
            if field == "source_authenticated":
                fake["limits"][field] = val
            elif field == "official_contest_submission":
                fake["limits"][field] = val
            else:
                fake[field] = val
            _reseal(fake)
            with self.subTest(field=field), self.assertRaises(ValueError):
                acknowledged(fake, src)
        rights_forged = deepcopy(report)
        rights_forged["source_rights_ledger"]["external_sharing_allowed"] = True
        _reseal(rights_forged)
        with self.assertRaises(ValueError):
            acknowledged(rights_forged, src)

    def test_replayed_bytes_must_match_and_review_receipt_is_deterministic(self):
        report, src = report_case()
        first = acknowledged(report, src)
        second = acknowledged(report, src)
        self.assertEqual(first, second)
        for role in src:
            changed = dict(src)
            changed[role] += b" "
            with self.subTest(role=role), self.assertRaises(ValueError):
                acknowledged(report, changed)
        self.assertNotEqual(
            acknowledged(report, src, review_note="다른 조건을 확인하고 검토 보류를 기록함")[
                "receipt_sha256"], first["receipt_sha256"])

    def test_missing_optional_a_c_originals_cannot_claim_successful_replay(self):
        from tests.test_ticker_market_industry_bridge import scenario
        _, src, m, c = scenario()
        market = json.dumps(m).encode()
        industry = json.dumps(c).encode()
        report, src = report_case(
            market=market, industry=industry, raws=src, as_of="2026-02-01")
        kwargs = dict(market_json=market, industry_json=industry)
        positive = acknowledged(report, src, **kwargs)
        self.assertEqual(positive["status"], "ACKNOWLEDGED_UNVERIFIED_LOCAL_ONLY")
        for alteration in ({"market_json": None},
                           {"industry_json": None},
                           {"market_json": market + b" "}):
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                acknowledged(report, src, **dict(kwargs, **alteration))


if __name__ == "__main__":
    unittest.main()
