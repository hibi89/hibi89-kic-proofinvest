"""P102 original iXBRL and Guard rules, mocked SEC transport only."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest import ticker_sec_transport as transport
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ixbrl_revenue_review import xhtml


def prepared(original: bytes | None = None):
    receipt, raw = valid_case()
    if original is not None:
        raw = dict(raw, original_10k=original)
        receipt = deepcopy(receipt)
        receipt["source_sha256"]["original_10k"] = sha256(original).hexdigest()
        receipt["source_bytes"]["original_10k"] = len(original)
    return receipt, raw


def valid_xhtml():
    return xhtml().replace(b"0000000001</xbrli:identifier>",
                           b"0001045810</xbrli:identifier>")


class OriginalGuardPreviewTests(unittest.TestCase):
    def test_same_cik_and_period_inline_context_matches_but_guard_holds(self):
        receipt, raw = prepared(valid_xhtml())
        revenue = inspect_collected_annual_revenue(receipt, raw)
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("UNAPPROVED_HTTP")) as request:
            actual = inspect_original_guard_preview(
                receipt, raw, expected_revenue=revenue)
        request.assert_not_called()
        self.assertEqual(actual["status"], "ORIGINAL_CONTEXT_MATCH_UNVERIFIED", actual)
        self.assertEqual(actual["ixbrl_status"], "local_ixbrl_revenue_context_match_unverified")
        self.assertEqual(actual["guard_preview"]["decision"], "HOLD")
        self.assertIn("RISK_UNAVAILABLE", actual["guard_preview"]["reason_codes"])
        self.assertEqual(actual["original_10k_sha256"], sha256(raw["original_10k"]).hexdigest())
        for flag in ("source_authenticated", "financial_facts_authenticated",
                     "source_rights_verified", "original_to_accession_authenticated",
                     "xbrl_taxonomy_validated", "engine_b_full_ready",
                     "guard_executed", "audit_written", "trade_executed",
                     "ai_interpretation_ready"):
            self.assertIs(actual[flag], False, flag)

    def test_plain_html_no_false_original_match_and_guard_hold(self):
        receipt, raw = prepared()
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "ORIGINAL_EVIDENCE_UNAVAILABLE")
        self.assertEqual(out["guard_preview"]["decision"], "HOLD")
        self.assertFalse(out["original_to_accession_authenticated"])

    def test_tampered_raw_or_sha_has_no_guard_preview(self):
        receipt, raw = prepared(valid_xhtml())
        for name in ("ticker_map", "submissions", "companyfacts", "original_10k"):
            altered = raw | {name: raw[name] + b" "}
            with self.subTest(name=name):
                out = inspect_original_guard_preview(receipt, altered)
                self.assertEqual(out["status"], "UNAVAILABLE")
                self.assertIsNone(out["guard_preview"])

    def test_cross_issuer_xbrl_context_is_not_a_match(self):
        receipt, raw = prepared(xhtml())
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "ORIGINAL_EVIDENCE_UNAVAILABLE")
        self.assertEqual(out["guard_preview"]["decision"], "HOLD")

    def test_conflicting_dei_issuer_claim_rejects_preview(self):
        original = valid_xhtml().replace(b"</body>",
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">0000320193</ix:nonNumeric>'
            b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric></body>')
        receipt, raw = prepared(original)
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "ORIGINAL_SELF_CLAIM_CONFLICT", out)
        self.assertEqual(out["guard_preview"]["decision"], "REJECT")
        self.assertFalse(out["guard_executed"])

    def test_matching_dei_self_claim_still_not_authenticated(self):
        original = valid_xhtml().replace(b"</body>",
            b'<ix:nonNumeric name="dei:EntityCentralIndexKey">0001045810</ix:nonNumeric>'
            b'<ix:nonNumeric name="dei:DocumentType">10-K</ix:nonNumeric></body>')
        receipt, raw = prepared(original)
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "ORIGINAL_CONTEXT_MATCH_UNVERIFIED")
        self.assertEqual(out["dei_status"], "self_claims_consistent_unverified")
        self.assertFalse(out["source_authenticated"])

    def test_forged_prior_revenue_or_issuer_preview_mismatch_refused(self):
        receipt, raw = prepared(valid_xhtml())
        rev = inspect_collected_annual_revenue(receipt, raw)
        for altered in (rev | {"prior_usd": "999"},
                        rev | {"issuer_cik": "0000000003"},
                        rev | {"guard_executed": True}):
            out = inspect_original_guard_preview(
                receipt, raw, expected_revenue=altered)
            self.assertEqual(out["status"], "UNAVAILABLE")
            self.assertIsNone(out["guard_preview"])

    def test_conflicting_ixbrl_amount_unavailable_not_safe(self):
        original = valid_xhtml().replace(
            b'>2</ix:nonFraction>', b'>3</ix:nonFraction>')
        receipt, raw = prepared(original)
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "ORIGINAL_EVIDENCE_UNAVAILABLE", out)
        self.assertEqual(out["guard_preview"]["decision"], "HOLD")
        self.assertFalse(out["financial_facts_authenticated"])

    def test_transport_unavailable_no_preview(self):
        receipt, raw = prepared(valid_xhtml())
        receipt = deepcopy(receipt)
        receipt["status"] = "unavailable"
        out = inspect_original_guard_preview(receipt, raw)
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertIsNone(out["guard_preview"])


if __name__ == "__main__":
    unittest.main()
