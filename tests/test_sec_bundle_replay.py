"""One behavioral test per important archive-to-offline-review outcome; no HTTP."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions,
    SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.sec_capture_bundle import (
    save_local_capture_bundle, verify_local_capture_bundle,
)
from proofinvest.sec_bundle_replay import replay_local_capture, _receipt_capture_clock


def fixture():
    raws = {
        "submissions": synthetic_submissions(),
        "companyfacts": json.dumps(synthetic_companyfacts()).encode(),
        "original_filing": SYNTHETIC_HTML,
    }
    stamp = "2025-10-16T12:00:00+00:00"
    receipt = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3,
        "live_sec_http_called": True,
        "issuer_cik": SYNTHETIC_CIK,
        "accession": SYNTHETIC_ACCESSION,
        "observed_utc_day": "2025-10-16",
        "submissions_observed_at_utc": stamp,
        "companyfacts_observed_at_utc": stamp,
        "original_observed_at_utc": stamp,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {key: hashlib.sha256(raw).hexdigest()
                                for key, raw in raws.items()},
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    return receipt, raws


class ReplayTests(unittest.TestCase):
    def make(self, directory: str, change=None):
        receipt, raws = fixture()
        if change:
            receipt.update(change)
        path = Path(directory)/"capture.zip"
        save_local_capture_bundle(path, receipt=receipt, **raws)
        return path

    def run_replay(self, path: Path, **kwargs):
        args = dict(current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE)
        return replay_local_capture(path, **(args | kwargs))

    def test_full_archive_to_accounting_replay_and_safe_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp)
            original = path.read_bytes()
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO NETWORK")) as opener:
                result = self.run_replay(path)
            opener.assert_not_called()
            self.assertEqual(result["status"], "offline_capture_replayed_unverified")
            self.assertEqual(result["offline_financial_review"]["growth_pct"], "100.00")
            self.assertEqual(result["risk"]["status"], "reviewed_unverified")
            self.assertEqual(result["review_summary"]["status"], "human_review_required")
            self.assertEqual(result["review_summary"]["review_priority"], "normal")
            self.assertEqual(result["human_review_triage"]["status"],
                             "offline_evidence_ready_for_human_review")
            self.assertIn("SOURCE_ORIGIN_UNAUTHENTICATED", result["risk"]["reason_codes"])
            self.assertFalse(result["human_review_triage"]["trade_authorized"])
            self.assertEqual(result["offline_financial_review"]["status"], "calculated_unverified")
            self.assertEqual(result["source_span"]["original_sha256"],
                             hashlib.sha256(SYNTHETIC_HTML).hexdigest())
            self.assertEqual(result["source_span"]["ixbrl_context"]["status"], "unavailable")
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(result["source_authenticated"])
            self.assertFalse(result["financial_values_authenticated"])
            self.assertFalse(result["external_http_called"])
            self.assertNotIn("<script>", json.dumps(result))

    def test_conflicting_growth_claim_is_escalated_in_real_replay_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp)
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO NETWORK")) as opener:
                result = self.run_replay(path, claimed_growth_pct="1.00")
            opener.assert_not_called()
            self.assertEqual(result["status"], "offline_capture_replayed_unverified")
            self.assertEqual(result["offline_financial_review"]["status"], "conflict")
            self.assertEqual(result["risk"]["status"], "unavailable")
            self.assertEqual(result["review_summary"]["review_priority"], "high")
            self.assertIn("CLAIMED_GROWTH_CONFLICT", result["risk"]["reason_codes"])
            triage = result["human_review_triage"]
            self.assertEqual(triage["status"], "manual_review_required")
            self.assertEqual(triage["priority"], "high")
            self.assertIn("FINANCIAL_CLAIM_CONFLICT", triage["reason_codes"])
            self.assertFalse(triage["investment_recommendation"])
            self.assertFalse(triage["trade_authorized"])

    def test_one_byte_corruption_blocks_reanalysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp)
            raw = bytearray(path.read_bytes())
            pos = raw.find(SYNTHETIC_HTML)
            self.assertGreater(pos, 0)
            raw[pos+2] ^= 1
            path.write_bytes(raw)
            self.assertEqual(verify_local_capture_bundle(path)["status"], "unavailable")
            self.assertEqual(self.run_replay(path)["reason_code"],
                             "ARCHIVED_BYTES_OR_MANIFEST_INVALID")

    def test_bad_accounting_year_or_missing_passage_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp)
            for patch_args in ({"current_end":"2023-09-30"},
                               {"needle":"NONEXISTENT_LITERAL"}):
                with self.subTest(args=patch_args):
                    result = self.run_replay(path, **patch_args)
                    self.assertEqual(result["status"], "unavailable")
                    self.assertFalse(result["source_authenticated"])

    def test_untrusted_receipt_capture_time_rejected_even_when_hashes_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp, {"companyfacts_observed_at_utc":"2025-10-17T00:00:00+00:00"})
            self.assertEqual(self.run_replay(path)["reason_code"],
                             "UNTRUSTED_OR_INCONSISTENT_ARCHIVED_CLOCK")

    def test_clock_invalid_order_and_naive_are_unacceptable(self):
        rec,_ = fixture()
        self.assertIsNotNone(_receipt_capture_clock(rec))
        rec["companyfacts_observed_at_utc"]="2025-10-16T09:00:00+00:00"
        self.assertIsNone(_receipt_capture_clock(rec))
        rec["companyfacts_observed_at_utc"]="2025-10-16T12:00:00"
        self.assertIsNone(_receipt_capture_clock(rec))

    def test_cli_summary_only_excludes_original_and_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make(tmp)
            proc = subprocess.run(
                [sys.executable, "-m", "proofinvest.sec_bundle_replay", str(path),
                 "--current-end", "2025-09-30", "--prior-end", "2024-09-30",
                 "--needle", PHRASE, "--summary-only"],
                capture_output=True, text=True, check=False, timeout=25,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["schema"], "proofinvest.offline-review-summary.v1")
            self.assertEqual(result["status"], "human_review_required")
            self.assertFalse(result["trade_authorized"])
            self.assertNotIn("source_span", result)
            self.assertNotIn("issuer_cik", result)
            self.assertNotIn("offline_financial_review", result)

    def test_cli_outputs_machine_readable_report_without_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=self.make(tmp)
            proc=subprocess.run(
                [sys.executable,"-m","proofinvest.sec_bundle_replay",str(path),
                 "--current-end","2025-09-30","--prior-end","2024-09-30",
                 "--needle",PHRASE],
                capture_output=True,text=True,check=False,timeout=25,
            )
            self.assertEqual(proc.returncode,0,proc.stderr)
            result=json.loads(proc.stdout)
            self.assertEqual(result["status"],"offline_capture_replayed_unverified")
            self.assertFalse(result["official_contest_submission"])
            self.assertNotIn("<script>",proc.stdout)
            self.assertFalse(proc.stderr)


if __name__=="__main__":
    unittest.main()
