"""P30: SEC 10-K acceptance instant prevents historical/look-ahead leakage."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from proofinvest import sec_three_source
from proofinvest.dl_bridge import filing_available_at_observation
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_loose_sec_compatibility import inspect_loose_sec_files
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.sec_companyfacts import TAG
from tests.test_kuodra_offline_preflight import make_zip


def raw_submissions(*, filed="2025-10-16", accepted="2025-10-16T13:00:00Z"):
    data = json.loads(synthetic_submissions())
    data["filings"]["recent"]["filingDate"][0] = filed
    if accepted is None:
        del data["filings"]["recent"]["acceptanceDateTime"]
    else:
        data["filings"]["recent"]["acceptanceDateTime"][0] = accepted
    return json.dumps(data, separators=(",", ":")).encode()


def raw_facts(*, filed="2025-10-16"):
    data = synthetic_companyfacts()
    for row in data["facts"]["us-gaap"][TAG]["units"]["USD"]:
        row["filed"] = filed
    return json.dumps(data, separators=(",", ":")).encode()


class FilingObservationP30Tests(unittest.TestCase):
    def test_aware_future_acceptance_is_not_available_even_for_earlier_filing_day(self):
        index = {"collected_at": COLLECTED_AT, "as_of_cutoff": AS_OF}
        row = {"filed_at": "2025-10-15", "accepted_at": "2025-10-16T13:00:00Z"}
        self.assertFalse(filing_available_at_observation(index, row))

    def test_same_day_aware_acceptance_before_collection_is_available(self):
        index = {"collected_at": COLLECTED_AT, "as_of_cutoff": AS_OF}
        row = {"filed_at": AS_OF, "accepted_at": "2025-10-16T07:30:00-04:00"}
        self.assertTrue(filing_available_at_observation(index, row))
        row["accepted_at"] = "2025-10-16T08:30:00-04:00"
        self.assertFalse(filing_available_at_observation(index, row))

    def test_same_day_missing_or_naive_acceptance_withheld_prior_day_allowed(self):
        index = {"collected_at": COLLECTED_AT, "as_of_cutoff": AS_OF}
        for value in (None, "2025-10-16T11:00:00", "bad-clock"):
            with self.subTest(acceptance=value):
                self.assertFalse(filing_available_at_observation(
                    index, {"filed_at": AS_OF, "accepted_at": value}))
                self.assertTrue(filing_available_at_observation(
                    index, {"filed_at": "2025-10-15", "accepted_at": value}))

    def test_guard_blocks_late_same_day_filing_without_creating_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "audit.sqlite"
            with self.assertRaisesRegex(ValueError, "FILING_NOT_AVAILABLE_AT_OBSERVATION"):
                review_local_sec_with_guard(
                    submissions_json=raw_submissions(),
                    companyfacts_json=raw_facts(),
                    original_filing=SYNTHETIC_HTML,
                    cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
                    as_of=AS_OF, collected_at=COLLECTED_AT,
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE, run_id="p30-no-write", audit_db_path=db,
                )
            self.assertFalse(db.exists())

    def test_readonly_loose_preflight_blocks_late_same_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subs = root / "submissions.json"
            facts = root / "companyfacts.json"
            orig = root / "original.html"
            subs.write_bytes(raw_submissions())
            facts.write_bytes(raw_facts())
            orig.write_bytes(SYNTHETIC_HTML)
            out = inspect_loose_sec_files(
                submissions_path=subs, companyfacts_path=facts, original_path=orig,
                cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
                as_of=AS_OF, collected_at=COLLECTED_AT,
            )
            self.assertEqual(out["reason_code"], "FILING_NOT_AVAILABLE_AT_OBSERVATION")
            self.assertFalse(out["audit_written"])
            self.assertEqual(sorted(root.iterdir()), sorted([subs, facts, orig]))

    def test_saved_zip_preflight_blocks_and_does_not_write_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            z = folder / "late.zip"
            make_zip(z, submissions=raw_submissions(),
                     facts=json.loads(raw_facts()))
            out = inspect_saved_capture_periods(z)
            self.assertEqual(out["reason_code"], "FILING_NOT_AVAILABLE_AT_OBSERVATION")
            self.assertEqual(out["status"], "blocked")
            self.assertEqual(out["period_candidates"], [])
            self.assertEqual(sorted(folder.iterdir()), [z])

    def test_explicit_provider_transport_stops_after_first_get_for_late_filing(self):
        with patch.object(sec_three_source, "_utcnow",
                          return_value=datetime(2025, 10, 16, 12, 0, tzinfo=timezone.utc)):
            with patch.object(sec_three_source, "fetch_submissions",
                              return_value=raw_submissions()) as fetch:
                with patch.object(sec_three_source, "_fetch_companyfacts") as company:
                    with patch.object(sec_three_source, "fetch_original") as original:
                        response = sec_three_source.run_sec_three_source_review(
                            cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
                            current_end="2025-09-30", prior_end="2024-09-30",
                            user_agent="ProofInvest real-contact@real-reviewer.org",
                            allow_network=True, acknowledge_three_requests=True,
                        )
        self.assertEqual(response["stage"], "submissions")
        self.assertEqual(response["http_requests_attempted"], 1)
        fetch.assert_called_once()
        company.assert_not_called()
        original.assert_not_called()

    def test_prior_day_default_receipt_still_guard_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "audit.sqlite"
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_HTTP")) as network:
                out = review_local_sec_with_guard(
                    submissions_json=synthetic_submissions(),
                    companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                    original_filing=SYNTHETIC_HTML,
                    cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
                    as_of=AS_OF, collected_at=COLLECTED_AT,
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE, run_id="p30-valid-hold", audit_db_path=db,
                )
            network.assert_not_called()
            self.assertEqual(out["guard"]["decision"], "HOLD")
            self.assertTrue(out["audit_chain_valid"])
            self.assertTrue(db.exists())


if __name__ == "__main__":
    unittest.main()
