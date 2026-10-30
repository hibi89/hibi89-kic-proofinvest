"""P7 three intent selections through one offline saved SEC Guard audit."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import SYNTHETIC_CIK, SYNTHETIC_ACCESSION, synthetic_companyfacts, synthetic_submissions
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.kuodra_capture_replay import replay_saved_capture
from proofinvest.guard_audit import GuardAuditStore

_END = "2025-09-30"
_ASOF = "2025-10-16"


def _companyfacts(*, balanced=True):
    obj = synthetic_companyfacts()
    if balanced:
        for tag, val in (("Assets", 300), ("Liabilities", 200), ("StockholdersEquity", 100)):
            obj["facts"]["us-gaap"][tag] = {"units": {"USD": [{
                "accn": SYNTHETIC_ACCESSION, "form": "10-K",
                "end": _END, "filed": "2025-10-15", "val": val,
            }]}}
    return json.dumps(obj, separators=(",", ":")).encode()


def _save(path, *, companyfacts=None, original=None):
    raws = {
        "submissions": synthetic_submissions(),
        "companyfacts": companyfacts if companyfacts is not None else _companyfacts(),
        "original_filing": original if original is not None else SYNTHETIC_HTML,
    }
    receipt = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3, "live_sec_http_called": True,
        "issuer_cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {key: hashlib.sha256(raw).hexdigest()
                                for key, raw in raws.items()},
        "observed_utc_day": _ASOF,
        "submissions_observed_at_utc": _ASOF + "T12:00:00Z",
        "companyfacts_observed_at_utc": _ASOF + "T12:00:01Z",
        "original_observed_at_utc": _ASOF + "T12:00:02Z",
        "capture_bytes_persisted": False,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    save_local_capture_bundle(path, receipt=receipt, **raws)


class KuodraThreeIntentReplayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kuodra-3intent-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.zip = self.root / "capture.zip"
        self.db = self.root / "audit.sqlite"
        _save(self.zip)
        self.request = {
            "issuer_cik": SYNTHETIC_CIK,
            "accession": SYNTHETIC_ACCESSION,
            "as_of": _ASOF, "requested_intent": "GROWTH_CHECK",
            "capture_zip": str(self.zip), "audit_db": str(self.db),
            "run_id": "p7-001", "current_end": _END,
            "prior_end": "2024-09-30", "needle": PHRASE,
        }

    def _exec(self, intent, *, request=None, proposal=None, consent=True):
        rq = (self.request if request is None else request) | {"requested_intent": intent}
        proposed = proposal if proposal is not None else {"action": "RUN", "intent": intent}
        return run_offline_proposal_replay(
            rq, proposed, acknowledge_local_audit_persistence=consent,
        )

    def test_three_intents_execute_one_local_guard_with_distinct_results(self):
        for intent, reason in (
            ("GROWTH_CHECK", "OFFLINE_GUARD_AUDIT_RECORDED"),
            ("SOURCE_REVIEW", "LOCAL_SOURCE_SPAN_REVIEW_UNVERIFIED"),
            ("RISK_CHECK", "LOCAL_BALANCE_RISK_REVIEW_UNVERIFIED"),
        ):
            with self.subTest(intent=intent):
                self.request["run_id"] = "p7-" + intent.lower().replace("_", "-")
                original = self.zip.read_bytes()
                with patch("urllib.request.build_opener",
                           side_effect=AssertionError("UNAPPROVED_EXTERNAL_REQUEST")) as net:
                    out = self._exec(intent)
                net.assert_not_called()
                self.assertEqual(out["status"], "completed")
                self.assertEqual(out["reason_code"], reason)
                self.assertEqual(out["selected_intent"], intent)
                self.assertEqual(out["local_tool_attempts"], 1)
                self.assertEqual(out["max_local_tool_attempts"], 1)
                self.assertEqual(out["guard"]["decision"], "HOLD")
                self.assertTrue(out["audit_written"])
                self.assertTrue(GuardAuditStore(self.db).verify_chain())
                self.assertEqual(original, self.zip.read_bytes())
                self.assertFalse(out["source_authenticated"])
                self.assertFalse(out["source_rights_verified"])
                self.assertFalse(out["ai_agent_executed"])
                self.assertFalse(out["live_model_called"])
                self.assertFalse(out["live_sec_called"])
                self.assertFalse(out["trade_executed"])
                self.assertTrue(out["source_review"]["exact_raw_byte_span_verified"])
                self.assertEqual(out["balance_sheet"]["status"], "reviewed_unverified")
                self.assertEqual(out["balance_sheet"]["liabilities_to_equity_pct"], "200.00")

    def test_risk_intent_reconciled_nci_runs_same_guard_audit(self):
        path = self.root / "nci-balance.zip"
        data = json.loads(_companyfacts())
        us = data["facts"]["us-gaap"]
        us["Assets"]["units"]["USD"][0]["val"] = 320
        parent = us["StockholdersEquity"]["units"]["USD"][0]
        us["MinorityInterest"] = {"units": {"USD": [
            {**parent, "val": 20}
        ]}}
        us["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = {
            "units": {"USD": [{**parent, "val": 120}]}
        }
        _save(path, companyfacts=json.dumps(data).encode())
        request = self.request | {"capture_zip": str(path), "run_id": "p8-nci-001"}
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as network:
            out = self._exec("RISK_CHECK", request=request)
        network.assert_not_called()
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["balance_sheet"]["equity_denominator_usd"], "120")
        self.assertEqual(out["balance_sheet"]["liabilities_to_equity_pct"], "166.67")
        self.assertEqual(out["balance_sheet"]["noncontrolling_interest_usd"], "20")
        self.assertEqual(out["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["trade_executed"])

    def test_risk_intent_no_balance_abstains_before_sqlite(self):
        path = self.root / "missing-risk.zip"
        _save(path, companyfacts=_companyfacts(balanced=False))
        req = self.request | {"capture_zip": str(path)}
        out = self._exec("RISK_CHECK", request=req)
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(out["local_tool_attempts"], 1)
        self.assertFalse(out["audit_written"] is False)
        self.assertFalse(self.db.exists())

    def test_risk_nonreconciled_abstains_before_sqlite(self):
        path = self.root / "bad-risk.zip"
        data = json.loads(_companyfacts())
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["val"] = 299
        _save(path, companyfacts=json.dumps(data).encode())
        out = self._exec("RISK_CHECK", request=self.request | {"capture_zip": str(path)})
        self.assertEqual(out["status"], "blocked")
        self.assertFalse(self.db.exists())

    def test_source_review_requires_visible_html_text_span_before_audit(self):
        path = self.root / "script-only.zip"
        _save(path, original=(b"<html><body>No text anchor</body>"
                              b"<script>" + PHRASE.encode() + b"</script></html>"))
        out = self._exec("SOURCE_REVIEW",
                         request=self.request | {"capture_zip": str(path)})
        self.assertEqual(out["status"], "blocked")
        self.assertFalse(self.db.exists())

    def test_growth_legacy_can_hold_without_reconciled_balance(self):
        path = self.root / "no-balance.zip"
        _save(path, companyfacts=_companyfacts(balanced=False))
        out = self._exec("GROWTH_CHECK",
                         request=self.request | {"capture_zip": str(path)})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["guard"]["decision"], "HOLD")
        self.assertEqual(out["balance_sheet"]["status"], "unavailable")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_proposal_and_operator_intent_mismatch_has_zero_tools(self):
        out = self._exec("RISK_CHECK", proposal={"action": "RUN", "intent": "SOURCE_REVIEW"})
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(out["local_tool_attempts"], 0)
        self.assertFalse(self.db.exists())

    def test_source_risk_intents_reject_injected_growth_claim_before_tool(self):
        for intent in ("SOURCE_REVIEW", "RISK_CHECK"):
            with self.subTest(intent=intent):
                rq = self.request | {"claimed_growth_pct": "300"}
                out = self._exec(intent, request=rq)
                self.assertEqual(out["reason_code"], "INVALID_OPERATOR_REQUEST")
                self.assertEqual(out["local_tool_attempts"], 0)
                self.assertFalse(self.db.exists())

    def test_all_intents_require_explicit_persistence_approval(self):
        for intent in ("GROWTH_CHECK", "SOURCE_REVIEW", "RISK_CHECK"):
            with self.subTest(intent=intent):
                out = self._exec(intent, consent=False)
                self.assertEqual(out["local_tool_attempts"], 0)
                self.assertEqual(out["reason_code"], "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
                self.assertFalse(self.db.exists())

    def test_ask_is_zero_tool_for_risk_and_source(self):
        for intent in ("SOURCE_REVIEW", "RISK_CHECK"):
            with self.subTest(intent=intent):
                out = self._exec(intent, proposal={"action": "ASK", "intent": None})
                self.assertEqual(out["status"], "needs_clarification")
                self.assertEqual(out["local_tool_attempts"], 0)
                self.assertFalse(self.db.exists())

    def test_source_review_is_hash_only_not_original_text_or_authentication(self):
        out = self._exec("SOURCE_REVIEW")
        self.assertEqual(out["source_review"]["archived_original_sha256"],
                         hashlib.sha256(SYNTHETIC_HTML).hexdigest())
        self.assertNotIn(PHRASE, json.dumps(out))
        self.assertFalse(out["source_review"]["source_authenticated"])
        self.assertFalse(out["source_review"]["source_rights_verified"])

    def test_operator_risk_input_explicitly_holds_not_trades(self):
        out = self._exec("RISK_CHECK")
        self.assertEqual(out["balance_sheet"]["exploratory_ratio_200pct_signal"], True)
        self.assertIn("RISK_UNAVAILABLE", out["guard"]["reason_codes"])
        self.assertFalse(out["trade_executed"])

    def test_replay_direct_intent_argument_unknown_fails_before_database(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SEC_REVIEW_INTENT"):
            replay_saved_capture(
                bundle_path=self.zip, audit_db=self.db, run_id="bad-intent",
                current_end=_END, prior_end="2024-09-30", needle=PHRASE,
                acknowledge_local_audit_persistence=True,
                required_review_intent="RUN_SHELL",
            )
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
