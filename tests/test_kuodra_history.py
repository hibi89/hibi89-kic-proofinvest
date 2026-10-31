"""Offline history continuation -> actual existing SEC packet / Guard SQLite."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_ACCESSION, SYNTHETIC_CIK,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_history import index_pinned_history
from proofinvest.local_sec_guard_report import review_local_sec_with_guard

PAGE = f"CIK{SYNTHETIC_CIK}-submissions-001.json"


def data():
    base = json.loads(synthetic_submissions())
    old = {key: values[:1] for key, values in base["filings"]["recent"].items()}
    old["accessionNumber"][0] = "0000000001-25-000003"
    old["form"][0] = "8-K"
    base["filings"]["recent"] = old
    base["filings"]["files"] = [{
        "name": PAGE, "filingFrom": "2025-10-15",
        "filingTo": "2025-10-15", "filingCount": 1,
    }]
    history = {
        "accessionNumber": [SYNTHETIC_ACCESSION],
        "form": ["10-K"],
        "filingDate": ["2025-10-15"],
        "primaryDocument": ["synthetic10k.htm"],
        "acceptanceDateTime": ["2025-10-15T12:00:00Z"],
    }
    return (
        json.dumps(base).encode("utf-8"),
        json.dumps(history).encode("utf-8"),
    )


class KuodraHistoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "audit.sqlite"

    def kwargs(self):
        base, history = data()
        return dict(
            submissions_json=base, companyfacts_json=json.dumps(
                synthetic_companyfacts()).encode("utf-8"),
            original_filing=SYNTHETIC_HTML, cik=SYNTHETIC_CIK,
            accession=SYNTHETIC_ACCESSION, as_of=AS_OF,
            collected_at=COLLECTED_AT, current_end="2025-09-30",
            prior_end="2024-09-30", needle=PHRASE,
            claimed_growth_pct="100.00",
            history_page_json=history, history_page_name=PAGE,
            audit_db_path=self.db, run_id="history-001",
        )

    def test_historical_10k_to_decimal_guard_sqlite_real_pipeline(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NETWORK_UNAUTHORIZED")) as get:
            res = review_local_sec_with_guard(**self.kwargs())
        get.assert_not_called()
        self.assertEqual(res["guard"]["decision"], "HOLD")
        self.assertEqual(res["verification"]["growth_pct"], "100.00")
        self.assertEqual(res["source"]["source_index_kind"], "PINNED_HISTORY")
        self.assertEqual(res["source"]["history_page_sha256"],
                         hashlib.sha256(self.kwargs()["history_page_json"]).hexdigest())
        self.assertTrue(res["audit_chain_valid"])
        self.assertFalse(res["limits"]["external_source_authenticated"])

    def test_direct_python_pins_cannot_claim_unpinned_history_page(self):
        params = self.kwargs()
        expected = {
            "submissions": hashlib.sha256(params["submissions_json"]).hexdigest(),
            "companyfacts": hashlib.sha256(params["companyfacts_json"]).hexdigest(),
            "original_filing": hashlib.sha256(params["original_filing"]).hexdigest(),
        }
        # Three approved byte hashes do not cover the fourth history page,
        # even when the supplied history itself is currently well formed.
        params["expected_source_sha256"] = expected
        with patch("proofinvest.local_sec_guard_report.build_local_sec_review_packet",
                   side_effect=AssertionError("MUST_PRECHECK_FIRST")) as build:
            with self.assertRaisesRegex(ValueError, "HISTORY_PAGE_NOT_PINNED"):
                review_local_sec_with_guard(**params)
        build.assert_not_called()
        self.assertFalse(self.db.exists())

    def test_historical_page_swap_cannot_bypass_three_pins(self):
        params = self.kwargs()
        params["expected_source_sha256"] = {
            "submissions": hashlib.sha256(params["submissions_json"]).hexdigest(),
            "companyfacts": hashlib.sha256(params["companyfacts_json"]).hexdigest(),
            "original_filing": hashlib.sha256(params["original_filing"]).hexdigest(),
        }
        # Valid-looking replacement historical evidence, but not included
        # in the operator-reviewed three hashes.
        other = json.loads(params["history_page_json"])
        other["acceptanceDateTime"] = ["2025-10-15T13:00:00Z"]
        params["history_page_json"] = json.dumps(other).encode()
        with self.assertRaisesRegex(ValueError, "HISTORY_PAGE_NOT_PINNED"):
            review_local_sec_with_guard(**params)
        self.assertFalse(self.db.exists())

    def test_partial_history_parameters_with_pins_also_fail_before_sqlite(self):
        params = self.kwargs()
        params["expected_source_sha256"] = {
            "submissions": hashlib.sha256(params["submissions_json"]).hexdigest(),
            "companyfacts": hashlib.sha256(params["companyfacts_json"]).hexdigest(),
            "original_filing": hashlib.sha256(params["original_filing"]).hexdigest(),
        }
        params["history_page_json"] = None
        with self.assertRaisesRegex(ValueError, "HISTORY_PAGE_NOT_PINNED"):
            review_local_sec_with_guard(**params)
        self.assertFalse(self.db.exists())

    def test_conflict_rejected_and_audited(self):
        params = self.kwargs()
        params["claimed_growth_pct"] = "300.00"
        res = review_local_sec_with_guard(**params)
        self.assertEqual(res["verification"]["status"], "conflict")
        self.assertEqual(res["guard"]["decision"], "REJECT")

    def test_wrong_history_manifest_name_rejected_before_persistence(self):
        params = self.kwargs()
        params["history_page_name"] = "CIK0000000001-submissions-999.json"
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**params)
        self.assertFalse(self.db.exists())

    def test_history_payload_tamper_count_rejected(self):
        params = self.kwargs()
        hist = json.loads(params["history_page_json"])
        hist["accessionNumber"].append("0000000001-25-000004")
        params["history_page_json"] = json.dumps(hist).encode()
        with self.assertRaises(ValueError):
            review_local_sec_with_guard(**params)
        self.assertFalse(self.db.exists())

    def test_future_acceptance_excluded(self):
        params = self.kwargs()
        hist = json.loads(params["history_page_json"])
        hist["acceptanceDateTime"] = ["2025-10-16T13:00:00Z"]
        params["history_page_json"] = json.dumps(hist).encode()
        with self.assertRaisesRegex(ValueError, "FILING_UNAVAILABLE"):
            review_local_sec_with_guard(**params)
        self.assertFalse(self.db.exists())

    def test_naive_same_day_acceptance_excluded(self):
        base, history = data()
        obj = json.loads(history)
        obj["acceptanceDateTime"] = ["2025-10-15T12:00:00"]
        index = index_pinned_history(
            base_raw=base, history_raw=json.dumps(obj).encode(),
            page_name=PAGE, cik=SYNTHETIC_CIK,
            as_of="2025-10-15", collected_at="2025-10-15T18:00:00Z",
        )
        # A naive timestamp at the same-day cutoff is not allowed.
        self.assertEqual(index["indexed_count"], 0)

    def test_recent_path_unaffected(self):
        params = self.kwargs()
        params["submissions_json"] = synthetic_submissions()
        params.pop("history_page_name")
        params.pop("history_page_json")
        res = review_local_sec_with_guard(**params)
        self.assertEqual(res["source"]["source_index_kind"], "RECENT")
        self.assertIsNone(res["source"]["history_page_sha256"])
        self.assertEqual(res["guard"]["decision"], "HOLD")


if __name__ == "__main__":
    unittest.main()
