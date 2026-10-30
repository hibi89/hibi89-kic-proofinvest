"""P6 local SEC balance sheet is strictly matched, descriptive, never approved."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kuodra_sec_balance import review_sec_balance_sheet
from proofinvest.kic_dl_demo import synthetic_submissions, synthetic_companyfacts, SYNTHETIC_CIK, SYNTHETIC_ACCESSION
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.kuodra_capture_replay import replay_saved_capture
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.guard_audit import GuardAuditStore

END, AS_OF = "2025-09-30", "2025-10-16"
VALUES = {"Assets": 300, "Liabilities": 200, "StockholdersEquity": 100}


def fixture(values=None):
    data = synthetic_companyfacts()
    for key, val in (VALUES if values is None else values).items():
        data["facts"]["us-gaap"][key] = {"units": {"USD": [
            {"accn": SYNTHETIC_ACCESSION, "form": "10-K", "end": END,
             "filed": "2025-10-15", "val": val},
        ]}}
    return data


def review(data, *, end=END, as_of=AS_OF):
    return review_sec_balance_sheet(
        json.dumps(data).encode(), cik=SYNTHETIC_CIK, accession=SYNTHETIC_ACCESSION,
        period_end=end, as_of=as_of,
    )


class KuodraBalanceReviewTests(unittest.TestCase):
    def test_valid_reconciled_balance_and_decimal_ratio(self):
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("UNAPPROVED_NETWORK")) as net:
            res = review(fixture())
        net.assert_not_called()
        self.assertEqual(res["status"], "reviewed_unverified")
        self.assertEqual(res["liabilities_to_equity_pct"], "200.00")
        self.assertTrue(res["exploratory_ratio_200pct_signal"])
        self.assertTrue(res["balance_identity_match"])
        self.assertTrue(res["ratio_is_total_liabilities_not_interest_bearing_debt"])
        self.assertFalse(res["source_authenticated"])
        self.assertFalse(res["risk_authenticated"])

    def test_unrounded_threshold_is_not_rounded_up_to_alert(self):
        res = review(fixture({"Assets": 300000, "Liabilities": 199999, "StockholdersEquity": 100001}))
        self.assertEqual(res["liabilities_to_equity_pct"], "200.00")
        self.assertFalse(res["exploratory_ratio_200pct_signal"])

    def test_equity_zero_or_negative_ratio_not_reported_as_safe(self):
        for values in (
            {"Assets": 100, "Liabilities": 100, "StockholdersEquity": 0},
            {"Assets": 100, "Liabilities": 110, "StockholdersEquity": -10},
        ):
            with self.subTest(values=values):
                res = review(fixture(values))
                self.assertEqual(res["status"], "unavailable")
                self.assertEqual(res["reason_code"], "NON_POSITIVE_EQUITY_RATIO_UNDEFINED")
                self.assertIsNone(res["liabilities_to_equity_pct"])

    def test_nonreconciled_balance_withholds_ratio(self):
        res = review(fixture({"Assets": 110, "Liabilities": 80, "StockholdersEquity": 20}))
        self.assertEqual(res["reason_code"], "BALANCE_IDENTITY_NOT_RECONCILED")
        self.assertFalse(res["balance_identity_match"])
        self.assertIsNone(res["exploratory_ratio_200pct_signal"])

    def test_missing_tag_withholds_not_fabricate(self):
        data = synthetic_companyfacts()
        res = review(data)
        self.assertEqual(res["status"], "unavailable")
        self.assertEqual(res["reason_code"], "BALANCE_FACT_UNAVAILABLE_OR_MIXED_UNITS")
        self.assertIsNone(res["inputs_usd"])

    def test_mixed_units_rejected(self):
        data = fixture()
        data["facts"]["us-gaap"]["Assets"]["units"]["EUR"] = []
        self.assertEqual(review(data)["reason_code"], "BALANCE_FACT_UNAVAILABLE_OR_MIXED_UNITS")

    def test_ambiguous_same_filing_values_rejected(self):
        data = fixture()
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"].append({
            "accn": SYNTHETIC_ACCESSION, "form": "10-K", "end": END,
            "filed": "2025-10-15", "val": 301,
        })
        self.assertEqual(review(data)["reason_code"], "AMBIGUOUS_BALANCE_FACT")

    def test_future_filed_fact_rejected_as_of(self):
        data = fixture()
        for tag in VALUES:
            data["facts"]["us-gaap"][tag]["units"]["USD"][0]["filed"] = "2025-10-17"
        self.assertEqual(review(data)["reason_code"], "BALANCE_FILING_AFTER_AS_OF")

    def test_mixed_filing_dates_rejected(self):
        data = fixture()
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["filed"] = "2025-10-16"
        self.assertEqual(review(data)["reason_code"], "MIXED_BALANCE_FILING_DATES")

    def test_cross_issuer_accession_and_period_unavailable(self):
        data = fixture()
        cases = [
            (dict(data, cik=2), END, AS_OF, "COMPANYFACTS_ISSUER_MISMATCH"),
            (data, "2025-08-31", AS_OF, "BALANCE_FACT_NOT_IN_SELECTED_FILING"),
            (data, END, "2025-09-29", "INVALID_INPUT"),
        ]
        for variant, period, asof, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(review(variant, end=period, as_of=asof)["reason_code"], reason)

    def test_missing_instant_period_or_bad_liabilities(self):
        for tag, field, value, reason in (
            ("Assets", "start", "2024-10-01", "INVALID_INSTANT_FACT_OR_AMOUNT"),
            ("Liabilities", "val", True, "INVALID_INSTANT_FACT_OR_AMOUNT"),
            ("Liabilities", "val", -1, "NEGATIVE_ASSETS_OR_LIABILITIES"),
        ):
            with self.subTest(tag=tag, field=field):
                data = fixture()
                data["facts"]["us-gaap"][tag]["units"]["USD"][0][field] = value
                self.assertEqual(review(data)["reason_code"], reason)

    def _instant(self, value, filed="2025-10-15"):
        return {"units": {"USD": [{"accn": SYNTHETIC_ACCESSION,
                                    "form": "10-K", "end": END,
                                    "filed": filed, "val": value}]}}

    def test_explicit_consolidated_equity_only(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        del data["facts"]["us-gaap"]["StockholdersEquity"]
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(120)
        value = review(data)
        self.assertEqual(value["status"], "reviewed_unverified")
        self.assertEqual(value["equity_denominator_usd"], "120")
        self.assertEqual(value["liabilities_to_equity_pct"], "166.67")
        self.assertEqual(value["equity_denominator_basis"],
                         "CONSOLIDATED_EQUITY_INCLUDING_NCI")

    def test_parent_equity_plus_explicit_noncontrolling_interest(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(20)
        value = review(data)
        self.assertEqual(value["status"], "reviewed_unverified")
        self.assertEqual(value["noncontrolling_interest_usd"], "20")
        self.assertEqual(value["equity_denominator_basis"],
                         "PARENT_EQUITY_PLUS_EXPLICIT_NCI")
        self.assertEqual(value["liabilities_to_equity_pct"], "166.67")

    def test_explicit_total_parent_nci_all_must_reconcile(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(20)
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(120)
        value = review(data)
        self.assertEqual(value["status"], "reviewed_unverified")
        self.assertTrue(value["balance_identity_match"])
        self.assertEqual(value["equity_denominator_usd"], "120")

    def test_mismatched_parent_total_without_nci_fails_closed(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(120)
        value = review(data)
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["reason_code"], "NCI_BRIDGE_UNAVAILABLE")
        self.assertIsNone(value["liabilities_to_equity_pct"])

    def test_conflicting_noncontrolling_bridge_fails(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(120)
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(21)
        self.assertEqual(review(data)["reason_code"], "NCI_EQUITY_COMPONENT_CONFLICT")

    def test_zero_total_equity_is_not_safe(self):
        data = fixture({"Assets": 200, "Liabilities": 200, "StockholdersEquity": 100})
        del data["facts"]["us-gaap"]["StockholdersEquity"]
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(0)
        value = review(data)
        self.assertEqual(value["reason_code"], "NON_POSITIVE_EQUITY_RATIO_UNDEFINED")
        self.assertIsNone(value["exploratory_ratio_200pct_signal"])

    def test_negative_nci_can_still_reconcile_without_unsafe_abs(self):
        data = fixture({"Assets": 290, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(-10)
        value = review(data)
        self.assertEqual(value["equity_denominator_usd"], "90")
        self.assertEqual(value["liabilities_to_equity_pct"], "222.22")
        self.assertTrue(value["exploratory_ratio_200pct_signal"])

    def test_future_nci_and_mismatched_dates_block_even_if_parent_valid(self):
        data = fixture({"Assets": 300, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(0, "2025-10-17")
        self.assertEqual(review(data)["reason_code"], "BALANCE_FILING_AFTER_AS_OF")
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(0, "2025-10-16")
        self.assertEqual(review(data)["reason_code"], "MIXED_BALANCE_FILING_DATES")

    def test_ambiguous_or_malformed_optional_total_does_not_silently_fallback(self):
        data = fixture()
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(100)
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]["units"]["USD"].append({
            "accn": SYNTHETIC_ACCESSION, "form": "10-K",
            "end": END, "filed": "2025-10-15", "val": 101,
        })
        self.assertEqual(review(data)["reason_code"], "AMBIGUOUS_BALANCE_FACT")
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]["units"]["USD"] = [{
            "accn": SYNTHETIC_ACCESSION, "form": "10-K",
            "end": END, "filed": "2025-10-15", "val": True,
        }]
        self.assertEqual(review(data)["reason_code"], "INVALID_INSTANT_FACT_OR_AMOUNT")

    def test_nci_present_but_nonreconciled_amount_blocks(self):
        data = fixture({"Assets": 321, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(20)
        out = review(data)
        self.assertEqual(out["reason_code"], "BALANCE_IDENTITY_NOT_RECONCILED")
        self.assertFalse(out["balance_identity_match"])

    def test_distinct_same_accession_zero_nci_remains_backward_compatible(self):
        data = fixture()
        data["facts"]["us-gaap"]["MinorityInterest"] = self._instant(0)
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(100)
        out = review(data)
        self.assertEqual(out["status"], "reviewed_unverified")
        self.assertEqual(out["liabilities_to_equity_pct"], "200.00")

    def test_explicit_null_optional_equity_cannot_bypass_conflicting_source(self):
        data = fixture({"Assets": 320, "Liabilities": 200, "StockholdersEquity": 100})
        data["facts"]["us-gaap"]["StockholdersEquity"] = None
        data["facts"]["us-gaap"]["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"] = self._instant(120)
        value = review(data)
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["reason_code"], "BALANCE_FACT_UNAVAILABLE_OR_MIXED_UNITS")

    def test_saved_zip_to_guard_sqlite_with_balance_and_no_policy_upgrade(self):
        root = tempfile.TemporaryDirectory(prefix="kuodra-balance-")
        self.addCleanup(root.cleanup)
        directory = Path(root.name)
        zip_path, db = directory / "capture.zip", directory / "audit.sqlite"
        sources = {
            "submissions": synthetic_submissions(),
            "companyfacts": json.dumps(fixture()).encode(),
            "original_filing": SYNTHETIC_HTML,
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
            "raw_response_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in sources.items()},
            "observed_utc_day": AS_OF,
            "submissions_observed_at_utc": "2025-10-16T12:00:00+00:00",
            "companyfacts_observed_at_utc": "2025-10-16T12:00:01+00:00",
            "original_observed_at_utc": "2025-10-16T12:00:02+00:00",
            "capture_bytes_persisted": False, "source_authenticated": False,
            "financial_facts_authenticated": False, "source_rights_verified": False,
            "official_contest_submission": False,
        }
        save_local_capture_bundle(zip_path, receipt=receipt, **sources)
        request = {
            "issuer_cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
            "as_of": AS_OF, "requested_intent": "GROWTH_CHECK",
            "capture_zip": str(zip_path), "audit_db": str(db),
            "run_id": "p6-audit-001", "current_end": END,
            "prior_end": "2024-09-30", "needle": PHRASE,
            "claimed_growth_pct": "100.00",
        }
        with patch("urllib.request.build_opener", side_effect=AssertionError("NO_HTTP")) as net:
            approved = run_offline_proposal_replay(
                request, {"action": "RUN", "intent": "GROWTH_CHECK"},
                acknowledge_local_audit_persistence=True,
            )
        net.assert_not_called()
        self.assertEqual(approved["status"], "completed")
        self.assertEqual(approved["balance_sheet"]["liabilities_to_equity_pct"], "200.00")
        self.assertTrue(approved["balance_sheet"]["exploratory_ratio_200pct_signal"])
        self.assertEqual(approved["guard"]["decision"], "HOLD")
        self.assertFalse(approved["source_authenticated"])
        self.assertTrue(GuardAuditStore(db).verify_chain())
        repeat = replay_saved_capture(
            bundle_path=zip_path, audit_db=db, run_id="p6-audit-001",
            current_end=END, prior_end="2024-09-30", needle=PHRASE,
            claimed_growth_pct="100.00", acknowledge_local_audit_persistence=True,
        )
        self.assertTrue(repeat["audit"]["replayed"])
        self.assertTrue(repeat["balance_sheet"]["exploratory_ratio_200pct_signal"])
        # The source cannot be upgraded to trusted Risk by local arithmetic.
        self.assertIn("RISK_UNAVAILABLE", approved["guard"]["reason_codes"])


if __name__ == "__main__":
    unittest.main()
