"""End-to-end saved ZIP -> real local Guard SQLite, zero HTTP tests."""
from __future__ import annotations

import hashlib
import io
from contextlib import redirect_stdout
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions, SYNTHETIC_CIK, SYNTHETIC_ACCESSION
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_capture_replay import main, replay_saved_capture
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.guard_audit import GuardAuditStore


def synthetic_receipt():
    raw = dict(
        submissions=synthetic_submissions(),
        companyfacts=json.dumps(synthetic_companyfacts()).encode("utf-8"),
        original_filing=SYNTHETIC_HTML,
    )
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
    return rec, raw


class KuodraCaptureReplayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "audit.sqlite"
        self.zip = self.root / "evidence.zip"
        rec, raw = synthetic_receipt()
        save_local_capture_bundle(self.zip, receipt=rec, **raw)
        self.kwargs = dict(
            bundle_path=self.zip, audit_db=self.db,
            run_id="first-001",
            current_end="2025-09-30", prior_end="2024-09-30",
            needle=PHRASE, claimed_growth_pct="100.00",
            acknowledge_local_audit_persistence=True,
        )

    def test_actual_zip_to_guard_sqlite_holds_zero_network(self):
        initial = self.zip.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_NETWORK")) as client:
            res = replay_saved_capture(**self.kwargs)
        client.assert_not_called()
        self.assertEqual(res["status"], "OFFLINE_CAPTURE_REVIEW_RECORDED")
        self.assertEqual(res["verification"]["growth_pct"], "100.00")
        self.assertEqual(res["guard"]["decision"], "HOLD")
        self.assertTrue(res["audit_chain_valid"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertEqual(self.zip.read_bytes(), initial)
        self.assertFalse(res["source_authenticated"])

    def test_conflict_reject_and_idempotent_replay(self):
        options = self.kwargs | {"claimed_growth_pct": "300.00"}
        first = replay_saved_capture(**options)
        again = replay_saved_capture(**options)
        self.assertEqual(first["guard"]["decision"], "REJECT")
        self.assertFalse(first["audit"]["replayed"])
        self.assertTrue(again["audit"]["replayed"])

    def test_denied_consent_has_no_sqlite_side_effects(self):
        with self.assertRaisesRegex(ValueError, "CONSENT"):
            replay_saved_capture(**(self.kwargs | {
                "acknowledge_local_audit_persistence": False
            }))
        self.assertFalse(self.db.exists())

    def test_tamper_fails_before_sqlite_write(self):
        altered = bytearray(self.zip.read_bytes())
        at = altered.find(SYNTHETIC_HTML)
        self.assertGreaterEqual(at, 0)
        altered[at + 2] ^= 1
        self.zip.write_bytes(altered)
        with self.assertRaisesRegex(ValueError, "INTEGRITY"):
            replay_saved_capture(**self.kwargs)
        self.assertFalse(self.db.exists())

    def test_malformed_clock_fails_closed(self):
        invalid = self.root / "bad_clock.zip"
        receipt, raw = synthetic_receipt()
        receipt["companyfacts_observed_at_utc"] = "2025-10-17T12:00:01+00:00"
        save_local_capture_bundle(invalid, receipt=receipt, **raw)
        with self.assertRaisesRegex(ValueError, "CHRONOLOGY"):
            replay_saved_capture(**(self.kwargs | {"bundle_path": invalid}))
        self.assertFalse(self.db.exists())

    def _macro(self):
        start = SYNTHETIC_HTML.index(PHRASE.encode("utf-8"))
        return {
            "exposures": [{
                "series_id": "US_CPI_YOY", "start_byte": start,
                "end_byte_exclusive": start + len(PHRASE.encode("utf-8")),
                "literal": PHRASE,
                "rationale": "Only a synthetic exposure for contract testing.",
            }],
            "observations": [{
                "series_id": "US_CPI_YOY", "unit": "percent_yoy",
                "benchmark": "United States CPI-U all items YoY",
                "value": "2.50", "period_end": "2025-09-30",
                "released_at": "2025-10-15T10:00:00Z",
                "vintage_at": "2025-10-15T10:00:01Z",
                "collected_at": "2025-10-15T10:00:02Z",
                "source_url": "https://example.org/synthetic-cpi",
                "rights_basis_url": "https://example.org/synthetic-terms",
                "rights_note": "Synthetic local-use attestation only; unverified.",
                "rights_review": "LOCAL_ANALYSIS_PERMITTED_ATTESTED",
                "payload_sha256": hashlib.sha256(b"synthetic CPI").hexdigest(),
            }],
        }

    def test_saved_sec_zip_macro_context_to_guard_without_policy_change(self):
        original = self.zip.read_bytes()
        result = replay_saved_capture(**(self.kwargs | {
            "macro_context": self._macro()
        }))
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertEqual(result["macro_context"]["cards"][0]["value"], "2.50")
        self.assertFalse(result["macro_context"]["guard_policy_modified"])
        self.assertFalse(result["macro_context"]["source_authenticated"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertEqual(self.zip.read_bytes(), original)

    def test_macro_contract_rejects_before_sqlite_creation(self):
        macro = self._macro()
        macro["exposures"][0]["literal"] = "not an exact original"
        macro["observations"] = "untrusted string not a list"
        with self.assertRaisesRegex(ValueError, "MACRO_CONTEXT_INVALID_INPUT"):
            replay_saved_capture(**(self.kwargs | {"macro_context": macro}))
        self.assertFalse(self.db.exists())

    def test_integrity_bound_macro_raw_to_sqlite_guard(self):
        macro = self._macro()
        row = macro["observations"][0]
        raw = json.dumps({
            k: v for k, v in row.items() if k != "payload_sha256"
        }).encode("utf-8")
        row["payload_sha256"] = hashlib.sha256(raw).hexdigest()
        result = replay_saved_capture(**(self.kwargs | {
            "macro_context": macro,
            "macro_raw_observations": {"US_CPI_YOY": raw},
        }))
        self.assertEqual(result["macro_context"]["raw_observation_count_verified"], 1)
        self.assertTrue(result["macro_context"]["cards"][0]["raw_observation_sha256_verified"])
        self.assertEqual(result["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())
        self.assertFalse(result["source_authenticated"])

    def test_tampered_macro_raw_fails_before_sqlite_side_effect(self):
        macro = self._macro()
        with self.assertRaisesRegex(ValueError, "MACRO_RAW_SHA256_MISMATCH"):
            replay_saved_capture(**(self.kwargs | {
                "macro_context": macro,
                "macro_raw_observations": {"US_CPI_YOY": b'{"value":"tampered"}'},
            }))
        self.assertFalse(self.db.exists())

    def test_macro_raw_requires_context_before_audit(self):
        with self.assertRaisesRegex(ValueError, "MACRO_RAW_REQUIRES_CONTEXT"):
            replay_saved_capture(**(self.kwargs | {
                "macro_raw_observations": {"SP500": b"{}"},
            }))
        self.assertFalse(self.db.exists())

    def _cli_raw_fixture(self):
        macro = self._macro()
        observation = macro["observations"][0]
        raw = json.dumps({
            k: v for k, v in observation.items() if k != "payload_sha256"
        }, ensure_ascii=False).encode("utf-8")
        observation["payload_sha256"] = hashlib.sha256(raw).hexdigest()
        raw_path = self.root / "cpi-observation.json"
        raw_path.write_bytes(raw)
        macro_path = self.root / "macro-context.json"
        macro_path.write_text(json.dumps(macro), encoding="utf-8")
        command = [
            "--capture-zip", str(self.zip),
            "--audit-db", str(self.db),
            "--run-id", "cli-integrity-001",
            "--current-end", "2025-09-30",
            "--prior-end", "2024-09-30",
            "--needle", PHRASE,
            "--claimed-growth-pct", "100.00",
            "--macro-context-json", str(macro_path),
            "--macro-raw", f"US_CPI_YOY={raw_path}",
            "--acknowledge-local-audit-persistence",
        ]
        return raw_path, command

    def test_actual_cli_reads_raw_json_and_writes_guard_once(self):
        _, command = self._cli_raw_fixture()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(command), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["macro_context"]["raw_observation_count_verified"], 1)
        self.assertTrue(report["macro_context"]["cards"][0]["raw_observation_sha256_verified"])
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_actual_cli_rejects_tampered_raw_before_audit(self):
        raw_path, command = self._cli_raw_fixture()
        raw_path.write_bytes(raw_path.read_bytes() + b" ")
        with self.assertRaises(SystemExit) as err:
            main(command)
        self.assertEqual(err.exception.code, 2)
        self.assertFalse(self.db.exists())

    def test_collision_with_input_prevents_write(self):
        with self.assertRaisesRegex(ValueError, "COLLISION"):
            replay_saved_capture(**(self.kwargs | {"audit_db": self.zip}))
        self.assertTrue(self.zip.is_file())


if __name__ == "__main__":
    unittest.main()
