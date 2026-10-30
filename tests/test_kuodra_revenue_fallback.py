"""P9 fail-closed SEC total revenue alternative tag selection, offline."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.sec_companyfacts import TAG, verify_sec_annual_revenue
from proofinvest.kic_dl_demo import SYNTHETIC_CIK, SYNTHETIC_ACCESSION, synthetic_companyfacts, synthetic_submissions
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.kuodra_capture_replay import replay_saved_capture
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.guard_audit import GuardAuditStore

KW = dict(cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
          current_end="2025-09-30", prior_end="2024-09-30", as_of="2025-10-16")


def facts(*, concepts=("Revenues",)):
    base = synthetic_companyfacts()
    us = base["facts"]["us-gaap"]
    revenue = us.pop(TAG)
    for concept in concepts:
        us[concept] = copy.deepcopy(revenue)
    return base


def verify(record, **options):
    return verify_sec_annual_revenue(record, **(KW | options))


def receipt(raws):
    cik, acc, day = SYNTHETIC_CIK, SYNTHETIC_ACCESSION, "2025-10-16"
    return {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3, "live_sec_http_called": True,
        "issuer_cik": cik, "accession": acc,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{cik}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in raws.items()},
        "observed_utc_day": day,
        "submissions_observed_at_utc": day + "T12:00:00Z",
        "companyfacts_observed_at_utc": day + "T12:00:01Z",
        "original_observed_at_utc": day + "T12:00:02Z",
        "capture_bytes_persisted": False,
        "source_authenticated": False, "financial_facts_authenticated": False,
        "source_rights_verified": False, "official_contest_submission": False,
    }


class RevenueConceptTests(unittest.TestCase):
    def test_revenues_only_calculates_without_cross_tag_composition(self):
        r = verify(facts())
        self.assertEqual(r["status"], "calculated_unverified")
        self.assertEqual(r["growth_pct"], "100.00")
        self.assertEqual(r["revenue_concept"], "Revenues")
        self.assertFalse(r["authenticated_external_source"])

    def test_sales_revenue_net_only(self):
        r = verify(facts(concepts=("SalesRevenueNet",)))
        self.assertEqual(r["status"], "calculated_unverified")
        self.assertEqual(r["revenue_concept"], "SalesRevenueNet")

    def test_primary_still_preferred_when_all_same(self):
        record = facts(concepts=(TAG, "Revenues", "SalesRevenueNet"))
        r = verify(record)
        self.assertEqual(r["status"], "calculated_unverified")
        self.assertEqual(r["revenue_concept"], TAG)

    def test_consistent_two_fallback_tags_choose_precedence(self):
        r = verify(facts(concepts=("SalesRevenueNet", "Revenues")))
        self.assertEqual(r["revenue_concept"], "Revenues")

    def test_conflicting_two_tags_fail_without_number(self):
        data = facts(concepts=("Revenues", "SalesRevenueNet"))
        data["facts"]["us-gaap"]["SalesRevenueNet"]["units"]["USD"][0]["val"] = 300
        r = verify(data)
        self.assertEqual(r["reason_code"], "REVENUE_CONCEPT_CONFLICT")
        self.assertIsNone(r["growth_pct"])

    def test_conflicting_primary_and_fallback_fail(self):
        data = facts(concepts=(TAG, "Revenues"))
        data["facts"]["us-gaap"]["Revenues"]["units"]["USD"][1]["val"] = 300
        self.assertEqual(verify(data)["reason_code"], "REVENUE_CONCEPT_CONFLICT")

    def test_partial_selected_filing_fallback_fails(self):
        data = facts(concepts=("Revenues", "SalesRevenueNet"))
        data["facts"]["us-gaap"]["SalesRevenueNet"]["units"]["USD"].pop()
        r = verify(data)
        self.assertEqual(r["reason_code"], "REVENUE_CONCEPT_INCOMPLETE_OR_INVALID")
        self.assertIsNone(r["growth_pct"])

    def test_missing_primary_does_not_hide_primary_invalid(self):
        data = facts(concepts=(TAG, "Revenues"))
        data["facts"]["us-gaap"][TAG]["units"]["USD"][0]["val"] = True
        self.assertEqual(verify(data)["reason_code"], "INVALID_USD_REVENUE")

    def test_prior_only_primary_does_not_prevent_current_accession_fallback(self):
        data = facts(concepts=(TAG, "Revenues"))
        for row in data["facts"]["us-gaap"][TAG]["units"]["USD"]:
            row["accn"] = "0000000001-24-000001"
        r = verify(data)
        self.assertEqual(r["status"], "calculated_unverified")
        self.assertEqual(r["revenue_concept"], "Revenues")
        self.assertEqual(r["annual_period_starts"],
                         ["2023-10-01", "2024-10-01"])

    def test_conflicting_period_start_between_tags_blocks(self):
        data = facts(concepts=("Revenues", "SalesRevenueNet"))
        data["facts"]["us-gaap"]["SalesRevenueNet"]["units"]["USD"][1]["start"] = "2023-09-30"
        r = verify(data)
        self.assertEqual(r["reason_code"], "REVENUE_CONCEPT_CONFLICT")

    def test_non_target_accession_alternative_does_not_block(self):
        data = facts(concepts=("Revenues", "SalesRevenueNet"))
        for row in data["facts"]["us-gaap"]["SalesRevenueNet"]["units"]["USD"]:
            row["accn"] = "0000000001-24-000001"
        r = verify(data)
        self.assertEqual(r["status"], "calculated_unverified")
        self.assertEqual(r["revenue_concept"], "Revenues")

    def test_only_future_alt_fails_as_of(self):
        data = facts()
        for row in data["facts"]["us-gaap"]["Revenues"]["units"]["USD"]:
            row["filed"] = "2025-10-17"
        self.assertEqual(verify(data)["reason_code"], "FILING_AFTER_AS_OF")

    def test_revenues_claim_conflict_preserves_guard_signal(self):
        self.assertEqual(verify(facts(), claimed_growth_pct="300")["status"], "conflict")
        self.assertEqual(verify(facts(), claimed_growth_pct="100")["status"], "calculated_unverified")

    def test_incompatible_tax_inclusive_concept_not_auto_selected(self):
        data = facts(concepts=("RevenueFromContractWithCustomerIncludingAssessedTax",))
        self.assertEqual(verify(data)["reason_code"], "MISSING_OR_OVERSIZED_REVENUE_RECORDS")

    def test_genuine_zip_reader_guard_audit_with_alt_revenue_and_no_http(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "capture.zip"
            db = root / "guard.sqlite"
            raws = {
                "submissions": synthetic_submissions(),
                "companyfacts": json.dumps(facts()).encode(),
                "original_filing": SYNTHETIC_HTML,
            }
            save_local_capture_bundle(src, receipt=receipt(raws), **raws)
            request = {
                "issuer_cik": SYNTHETIC_CIK,
                "accession": SYNTHETIC_ACCESSION,
                "as_of": "2025-10-16", "requested_intent": "GROWTH_CHECK",
                "capture_zip": str(src), "audit_db": str(db),
                "run_id": "p9-alt-001",
                "current_end": "2025-09-30",
                "prior_end": "2024-09-30", "needle": PHRASE,
                "claimed_growth_pct": "100.00",
            }
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
                r = run_offline_proposal_replay(
                    request, {"action": "RUN", "intent": "GROWTH_CHECK"},
                    acknowledge_local_audit_persistence=True,
                )
            network.assert_not_called()
            self.assertEqual(r["status"], "completed")
            self.assertEqual(r["verification"]["revenue_concept"], "Revenues")
            self.assertEqual(r["verification"]["growth_pct"], "100.00")
            self.assertEqual(r["guard"]["decision"], "HOLD")
            self.assertTrue(GuardAuditStore(db).verify_chain())
            repeat = replay_saved_capture(
                bundle_path=src, audit_db=db, run_id="p9-alt-001",
                current_end="2025-09-30", prior_end="2024-09-30",
                needle=PHRASE, claimed_growth_pct="100.00",
                acknowledge_local_audit_persistence=True,
            )
            self.assertTrue(repeat["audit"]["replayed"])

    def test_conflicting_alt_tags_in_zip_do_not_write_guard_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, src = root / "guard.sqlite", root / "conflicting.zip"
            data = facts(concepts=("Revenues", "SalesRevenueNet"))
            data["facts"]["us-gaap"]["SalesRevenueNet"]["units"]["USD"][0]["val"] = 300
            raws = {"submissions": synthetic_submissions(),
                    "companyfacts": json.dumps(data).encode(),
                    "original_filing": SYNTHETIC_HTML}
            save_local_capture_bundle(src, receipt=receipt(raws), **raws)
            with self.assertRaisesRegex(ValueError, "REVENUE_CONCEPT_CONFLICT"):
                replay_saved_capture(
                    bundle_path=src, audit_db=db, run_id="p9-conflict-001",
                    current_end="2025-09-30", prior_end="2024-09-30",
                    needle=PHRASE,
                    acknowledge_local_audit_persistence=True,
                )
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
