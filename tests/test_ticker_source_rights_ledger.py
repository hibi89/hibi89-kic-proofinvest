"""P119 rights ledger is a local evidence-gap inventory, never a license."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_local_report import verify_local_report
from proofinvest.ticker_source_rights_ledger import build_local_rights_ledger
from tests.test_ticker_local_report_replay import report_case, _reseal
from tests.test_ticker_market_industry_bridge import scenario


class LocalSourceRightsLedgerTests(unittest.TestCase):
    def test_six_source_roles_and_immutable_blocked_use_contract(self):
        receipt, raw = report_case()
        ledger = receipt["source_rights_ledger"]
        self.assertEqual(ledger["schema"], "kuodra.local-source-rights-ledger.v1")
        self.assertEqual(ledger["status"], "EXTERNAL_USE_BLOCKED_RIGHTS_NOT_VERIFIED")
        self.assertEqual([x["role"] for x in ledger["sources"]], [
            "ticker_map", "submissions", "companyfacts", "original_10k",
            "market_json", "industry_json",
        ])
        self.assertEqual([x["raw_sha256"] for x in ledger["sources"][:4]],
                         [sha256(raw[k]).hexdigest() for k in
                          ("ticker_map", "submissions", "companyfacts", "original_10k")])
        self.assertEqual([x["raw_sha256"] for x in ledger["sources"][4:]],
                         [None, None])
        self.assertTrue(all(x["publisher_origin_authenticated"] is False
                            and x["source_use_rights_verified"] is False
                            and x["external_display_rights_verified"] is False
                            and x["redistribution_rights_verified"] is False
                            for x in ledger["sources"]))
        for k in ("contest_public_submission_allowed",
                  "external_sharing_allowed", "commercial_reuse_allowed",
                  "license_or_reuse_permission_verified",
                  "publisher_origin_authenticated", "paid_services_activated"):
            self.assertFalse(ledger[k], k)
        self.assertEqual(ledger["network_requests"], 0)
        self.assertEqual(verify_local_report(receipt, sources=raw)["status"], "PASS")

    def test_alleged_market_and_industry_inputs_still_do_not_grant_rights(self):
        _, raw, market, industry = scenario()
        mbytes = json.dumps(market).encode()
        cbytes = json.dumps(industry).encode()
        report, raw = report_case(market=mbytes, industry=cbytes,
                                 as_of="2026-02-01", raws=raw)
        ledger = report["source_rights_ledger"]
        self.assertEqual([s["raw_sha256"] for s in ledger["sources"][4:]],
                         [sha256(mbytes).hexdigest(),
                          sha256(cbytes).hexdigest()])
        self.assertTrue(all(s["input_status"] == "ACCEPTED_FOR_UNVERIFIED_COMPUTATION"
                            for s in ledger["sources"][4:]))
        self.assertFalse(ledger["external_sharing_allowed"])
        self.assertFalse(ledger["contest_public_submission_allowed"])
        self.assertEqual(verify_local_report(
            report, sources=raw, market_json=mbytes, industry_json=cbytes)["status"],
            "PASS")

    def test_reshashed_rights_approval_or_shuffled_source_digests_is_detected(self):
        report, sources = report_case()
        for path, value in (
            (("source_rights_ledger", "contest_public_submission_allowed"), True),
            (("source_rights_ledger", "status"), "APPROVED"),
            (("source_rights_ledger", "external_sharing_allowed"), True),
            (("source_rights_ledger", "sources"), []),
        ):
            with self.subTest(path=path):
                forged = deepcopy(report)
                forged[path[0]][path[1]] = value
                forged = _reseal(forged)
                result = verify_local_report(forged, sources=sources)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["reason_code"],
                                 "REPORT_SEMANTIC_REPLAY_MISMATCH")

    def test_mismatched_trust_and_source_role_data_rejected(self):
        report, _ = report_case()
        # Direct builder (before report) must not accept a fake entitlement or
        # a wrong SHA that could be presented as known source evidence.
        from proofinvest.ticker_local_sources import prepare_local_ticker_sources
        from proofinvest.ticker_market_industry_bridge import evaluate_ticker_a_c
        from tests.test_ticker_sec_financial_bridge import valid_case
        from tests.test_ticker_sec_original_guard_preview import valid_xhtml
        _, original = valid_case()
        original = dict(original, original_10k=valid_xhtml())
        receipt = prepare_local_ticker_sources(
            ticker="NVDA", as_of="2025-10-16", sources=original)
        supplementary = evaluate_ticker_a_c(receipt, original)
        for key, value in (("source_authenticated", True),
                           ("source_rights_verified", True),
                           ("network_requests", 1)):
            with self.subTest(key=key):
                corrupted = dict(receipt, **{key: value})
                with self.assertRaises(ValueError):
                    build_local_rights_ledger(corrupted, supplementary)
        for altered in (
            {"companyfacts": "0" * 64},
            dict(receipt["source_sha256"], companyfacts="A" * 64),
        ):
            with self.assertRaises(ValueError):
                build_local_rights_ledger(
                    dict(receipt, source_sha256=altered), supplementary)
        self.assertFalse(report["source_rights_ledger"]["external_sharing_allowed"])

    def test_no_external_call_even_on_successful_report_replay(self):
        report, sources = report_case()
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("FORBIDDEN_SEC_NETWORK")) as network:
            out = verify_local_report(report, sources=sources)
        self.assertEqual(out["status"], "PASS")
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
