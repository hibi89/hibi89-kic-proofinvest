"""P5 strictly bounded untrusted proposal -> saved SEC -> Guard/SQLite."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.kic_dl_demo import SYNTHETIC_ACCESSION, SYNTHETIC_CIK, synthetic_companyfacts, synthetic_submissions
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_operator_replay import main, run_offline_proposal_replay
from proofinvest.sec_capture_bundle import save_local_capture_bundle


def capture_fixture(path: Path) -> None:
    raw = {
        "submissions": synthetic_submissions(),
        "companyfacts": json.dumps(synthetic_companyfacts()).encode(),
        "original_filing": SYNTHETIC_HTML,
    }
    rec = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3, "live_sec_http_called": True,
        "issuer_cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
        "observed_utc_day": "2025-10-16",
        "submissions_observed_at_utc": "2025-10-16T12:00:00+00:00",
        "companyfacts_observed_at_utc": "2025-10-16T12:00:01+00:00",
        "original_observed_at_utc": "2025-10-16T12:00:02+00:00",
        "capture_bytes_persisted": False,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    save_local_capture_bundle(path, receipt=rec, **raw)


class OperatorProposalReplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.zip = self.root / "source.zip"
        self.db = self.root / "audit.sqlite"
        capture_fixture(self.zip)
        self.req = {
            "issuer_cik": SYNTHETIC_CIK,
            "accession": SYNTHETIC_ACCESSION,
            "as_of": "2025-10-16", "requested_intent": "GROWTH_CHECK",
            "capture_zip": str(self.zip), "audit_db": str(self.db),
            "current_end": "2025-09-30", "prior_end": "2024-09-30",
            "needle": PHRASE, "run_id": "p5-001", "claimed_growth_pct": "100.00",
        }
        self.proposal = '{"action":"RUN","intent":"GROWTH_CHECK"}'

    def run_gated(self, req=None, proposal=None, consent=True):
        return run_offline_proposal_replay(
            self.req if req is None else req,
            self.proposal if proposal is None else proposal,
            acknowledge_local_audit_persistence=consent,
        )

    def test_live_shaped_zip_replay_local_guard_no_network(self):
        original = self.zip.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("UNAPPROVED_NETWORK")) as net:
            result = self.run_gated()
        net.assert_not_called()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertEqual(result["verification"]["growth_pct"], "100.00")
        self.assertEqual(result["local_tool_attempts"], 1)
        self.assertEqual(result["max_local_tool_attempts"], 1)
        self.assertTrue(result["audit_written"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertEqual(self.zip.read_bytes(), original)
        for key in ("source_authenticated", "source_rights_verified",
                    "live_model_called", "live_sec_called", "trade_executed",
                    "ai_agent_executed"):
            self.assertIs(result[key], False)

    def test_conflict_is_reject_and_replay_is_idempotent(self):
        self.req["claimed_growth_pct"] = "300.00"
        a = self.run_gated()
        b = self.run_gated()
        self.assertEqual(a["guard"]["decision"], "REJECT")
        self.assertEqual(b["guard"]["decision"], "REJECT")
        self.assertFalse(a["audit"]["replayed"])
        self.assertTrue(b["audit"]["replayed"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_model_mismatch_does_not_execute(self):
        for proposal in (
            '{"action":"RUN","intent":"SOURCE_REVIEW"}',
            '{"action":"RUN","intent":"RISK_CHECK"}',
        ):
            with self.subTest(proposal=proposal):
                result = self.run_gated(proposal=proposal)
                self.assertEqual(result["reason_code"], "MODEL_INTENT_MISMATCH_OR_UNSUPPORTED")
                self.assertEqual(result["local_tool_attempts"], 0)
                self.assertFalse(self.db.exists())

    def test_model_injected_parameters_blocked_before_write(self):
        for proposal in (
            '{"action":"RUN","intent":"GROWTH_CHECK","db":"other.db"}',
            '{"action":"RUN","intent":"run_shell"}',
            '{"action":"RUN","intent":"GROWTH_CHECK","network":true}',
            '{"action":"RUN","action":"ASK","intent":"GROWTH_CHECK"}',
            '{"action":"EXECUTE","intent":"GROWTH_CHECK"}',
            "{not-json}",
            "{" + "a" * 2200 + "}",
        ):
            with self.subTest(proposal=proposal[:60]):
                result = self.run_gated(proposal=proposal)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["local_tool_attempts"], 0)
                self.assertFalse(self.db.exists())

    def test_ask_clarification_zero_tools(self):
        result = self.run_gated(proposal='{"action":"ASK","intent":null}')
        self.assertEqual(result["status"], "needs_clarification")
        self.assertFalse(result["model_proposal_accepted"])
        self.assertEqual(result["local_tool_attempts"], 0)
        self.assertFalse(self.db.exists())

    def test_consent_required_for_any_local_write(self):
        result = self.run_gated(consent=False)
        self.assertEqual(result["reason_code"], "EXPLICIT_LOCAL_AUDIT_CONSENT_REQUIRED")
        self.assertEqual(result["local_tool_attempts"], 0)
        self.assertFalse(self.db.exists())

    def test_issuer_accession_and_as_of_bound_before_sqlite(self):
        for change in (
            {"issuer_cik": "0000000002", "accession": "0000000002-25-000001"},
            {"accession": "0000000001-25-999999"},
            {"as_of": "2025-10-17"},
        ):
            with self.subTest(change=change):
                request = dict(self.req, **change)
                result = self.run_gated(req=request)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["local_tool_attempts"], 1)
                self.assertFalse(self.db.exists())

    def test_invalid_operator_request_fails_without_tool(self):
        for req in (
            dict(self.req, requested_intent="RISK_CHECK"),
            dict(self.req, current_end="2026-01-01"),
            dict(self.req, needle="x"),
            dict(self.req, run_id="../../secret"),
            dict(self.req, claimed_growth_pct=12.5),
            dict(self.req, network_allowed=True),
        ):
            with self.subTest(request=req):
                result = self.run_gated(req=req)
                self.assertEqual(result["reason_code"], "INVALID_OPERATOR_REQUEST")
                self.assertEqual(result["local_tool_attempts"], 0)
                self.assertFalse(self.db.exists())

    def test_local_zip_tampering_fails_without_audit(self):
        broken = bytearray(self.zip.read_bytes())
        i = broken.find(SYNTHETIC_HTML)
        self.assertGreaterEqual(i, 0)
        broken[i] ^= 1
        self.zip.write_bytes(broken)
        result = self.run_gated()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason_code"], "OFFLINE_REPLAY_FAILED_CHECK_AUDIT_STATE")
        self.assertFalse(self.db.exists())

    def test_error_does_not_falsely_certify_audit_absent(self):
        with patch("proofinvest.kuodra_operator_replay.replay_saved_capture",
                   side_effect=ValueError("PRIVATE SOURCE CONTENT")):
            result = self.run_gated()
        self.assertIsNone(result["audit_written"])
        self.assertNotIn("PRIVATE SOURCE CONTENT", json.dumps(result))
        self.assertEqual(result["local_tool_attempts"], 1)

    def test_cli_requires_persistence_consent_and_runs_locally(self):
        rq = self.root / "request.json"
        pr = self.root / "proposal.json"
        rq.write_text(json.dumps(self.req), encoding="utf-8")
        pr.write_text(self.proposal, encoding="utf-8")
        args = ["--operator-request-json", str(rq), "--proposal-json", str(pr)]
        with redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(main(args), 2)
        self.assertEqual(json.loads(captured.getvalue())["local_tool_attempts"], 0)
        self.assertFalse(self.db.exists())
        with redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(main(args + ["--acknowledge-local-audit-persistence"]), 0)
        self.assertEqual(json.loads(captured.getvalue())["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_cli_rejects_duplicate_operator_json_without_write(self):
        rq = self.root / "duplicate.json"
        pr = self.root / "proposal.json"
        rq.write_text('{"as_of":"2025-10-16","as_of":"2026-01-01"}', encoding="utf-8")
        pr.write_text(self.proposal, encoding="utf-8")
        args = ["--operator-request-json", str(rq), "--proposal-json", str(pr),
                "--acknowledge-local-audit-persistence"]
        with redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(main(args), 2)
        self.assertEqual(json.loads(captured.getvalue())["status"], "blocked")
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
