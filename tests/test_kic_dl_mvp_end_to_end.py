"""Real in-process synthetic DL core -> SQLite -> SEC numeric -> KIC bridge."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from datetime import date
from disclosure_lightning.core import index_submissions, save_index
from proofinvest.dl_bridge import assess_dl_sec_handoff
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    replay, synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.sec_companyfacts import verify_sec_annual_revenue


class KicDlActualIntegrationTests(unittest.TestCase):
    def test_one_command_real_python_modules_offline_complete(self):
        with patch("disclosure_lightning.core.urllib.request.build_opener",
                   side_effect=AssertionError("UNAUTHORIZED HTTP")) as external:
            receipt = replay()
            external.assert_not_called()
        self.assertEqual(receipt["status"], "offline_mvp_pass")
        self.assertEqual(receipt["dl_indexed"], 2)
        self.assertEqual(receipt["sqlite_inserted_first"], 2)
        self.assertEqual(receipt["sqlite_inserted_repeat"], 0)
        self.assertEqual(receipt["sqlite_listed_filings"], 2)
        self.assertEqual(receipt["synthetic_growth_pct"], "100.00")
        self.assertEqual(receipt["kic_link_status"], "linked_metadata_only")
        for field in ("real_issuer_verified", "live_sec_requested",
                      "full_filing_content_retrieved", "agent_executed",
                      "official_hackathon_submitted", "kic_external_authentication"):
            self.assertFalse(receipt[field], field)
        self.assertIsNone(receipt["original_filing_sha256"])

    def test_actual_module_entrypoint_prints_json_receipt(self):
        proc = subprocess.run([sys.executable, "-m", "proofinvest.kic_dl_demo"],
                              capture_output=True, text=True, check=False, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "offline_mvp_pass")

    def test_future_collection_is_rejected_at_dl_before_bridge(self):
        with self.assertRaisesRegex(ValueError, "COLLECTION_AFTER_AS_OF"):
            index_submissions(synthetic_submissions(), cik=SYNTHETIC_CIK,
                              as_of=AS_OF, forms=frozenset({"10-K"}),
                              collected_at="2025-10-16T23:30:00-12:00")

    def test_verifier_mismatch_blocked_on_actual_dl_record(self):
        indexed = index_submissions(synthetic_submissions(), cik=SYNTHETIC_CIK,
                                    as_of=AS_OF, forms=frozenset({"10-K"}),
                                    collected_at=COLLECTED_AT)
        correct = verify_sec_annual_revenue(synthetic_companyfacts(),
                                            cik=SYNTHETIC_CIK,
                                            accession=SYNTHETIC_ACCESSION,
                                            current_end="2025-09-30",
                                            prior_end="2024-09-30", as_of=AS_OF)
        self.assertEqual(assess_dl_sec_handoff(indexed, correct)["status"],
                         "linked_metadata_only")
        changed = dict(correct, filing_date="2025-10-16")
        self.assertEqual(assess_dl_sec_handoff(indexed, changed)["status"], "unavailable")
        changed = dict(correct, accession="0000000001-25-000002")
        self.assertEqual(assess_dl_sec_handoff(indexed, changed)["status"], "unavailable")

    def test_amendment_metadata_is_not_same_filing_or_authenticated(self):
        indexed = index_submissions(synthetic_submissions(), cik=SYNTHETIC_CIK,
                                    as_of=AS_OF,
                                    forms=frozenset({"10-K", "10-K/A"}),
                                    collected_at=COLLECTED_AT)
        forms = [entry["form"] for entry in indexed["filings"]]
        self.assertEqual(forms, ["10-K", "10-K/A"])
        self.assertTrue(all(entry["raw_sha256"] is None for entry in indexed["filings"]))
        self.assertTrue(all(entry["amends_accession"] is None for entry in indexed["filings"]))
