"""P10 inspect saved SEC capture without DB, model, network or auto-run."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    SYNTHETIC_ACCESSION, SYNTHETIC_CIK, synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods, main
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.sec_companyfacts import TAG


def make_zip(path: Path, *, facts=None, submissions=None, timestamps=None,
             original=None):
    raws = {
        "submissions": submissions if submissions is not None else synthetic_submissions(),
        "companyfacts": json.dumps(
            facts if facts is not None else synthetic_companyfacts()
        ).encode("utf-8"),
        "original_filing": original if original is not None else SYNTHETIC_HTML,
    }
    recorded = timestamps or [
        "2025-10-16T12:00:00Z",
        "2025-10-16T12:00:01Z",
        "2025-10-16T12:00:02Z",
    ]
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
        "raw_response_sha256": {
            key: hashlib.sha256(raw).hexdigest() for key, raw in raws.items()
        },
        "observed_utc_day": "2025-10-16",
        "submissions_observed_at_utc": recorded[0],
        "companyfacts_observed_at_utc": recorded[1],
        "original_observed_at_utc": recorded[2],
        "capture_bytes_persisted": False,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    save_local_capture_bundle(path, receipt=receipt, **raws)
    return raws


class OfflinePreflightTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(prefix="kuodra-preflight-")
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.bundle = self.root / "source.zip"
        self.db = self.root / "audit.sqlite"
        self.raws = make_zip(self.bundle)

    def test_discovers_real_annual_pair_read_only(self):
        initial = self.bundle.read_bytes()
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as client:
            report = inspect_saved_capture_periods(self.bundle)
        client.assert_not_called()
        self.assertEqual(report["status"], "review_candidates_available")
        self.assertEqual(report["issuer_cik_self_reported"], SYNTHETIC_CIK)
        self.assertEqual(report["accession_self_reported"], SYNTHETIC_ACCESSION)
        self.assertEqual(report["period_candidates"], [{
            "current_end": "2025-09-30",
            "prior_end": "2024-09-30",
            "growth_pct_unverified": "100.00",
            "revenue_concept": TAG,
            "filing_date": "2025-10-15",
        }])
        self.assertEqual(report["source_sha256"]["companyfacts"],
                         hashlib.sha256(self.raws["companyfacts"]).hexdigest())
        self.assertEqual(self.bundle.read_bytes(), initial)
        self.assertFalse(self.db.exists())
        self.assertFalse(report["audit_written"])
        self.assertIsNone(report["selected_period"])
        self.assertFalse(report["source_authenticated"])
        self.assertEqual(report["network_calls"], 0)
        self.assertIn("needle", report["operator_must_confirm"])

    def test_alt_revenues_candidate_without_primary(self):
        different = synthetic_companyfacts()
        us = different["facts"]["us-gaap"]
        us["Revenues"] = us.pop(TAG)
        new = self.root / "alt.zip"
        make_zip(new, facts=different)
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["status"], "review_candidates_available")
        self.assertEqual(report["period_candidates"][0]["revenue_concept"],
                         "Revenues")
        self.assertFalse(self.db.exists())

    def test_conflicting_concepts_are_not_suggested(self):
        different = synthetic_companyfacts()
        us = different["facts"]["us-gaap"]
        us["Revenues"] = json.loads(json.dumps(us[TAG]))
        us["Revenues"]["units"]["USD"][0]["val"] = 300
        new = self.root / "conflict.zip"
        make_zip(new, facts=different)
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "NO_VERIFIABLE_REVENUE_PERIOD_PAIR")
        self.assertEqual(report["period_candidates"], [])
        self.assertFalse(self.db.exists())

    def test_missing_target_accession_not_reported_as_candidate(self):
        different = synthetic_companyfacts()
        for row in different["facts"]["us-gaap"][TAG]["units"]["USD"]:
            row["accn"] = "0000000001-24-000001"
        new = self.root / "wrong-acc.zip"
        make_zip(new, facts=different)
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "NO_CONSECUTIVE_ANNUAL_PERIODS")

    def test_digest_tamper_rejected_no_audit(self):
        broken = bytearray(self.bundle.read_bytes())
        i = broken.find(SYNTHETIC_HTML)
        self.assertGreaterEqual(i, 0)
        broken[i] ^= 1
        self.bundle.write_bytes(broken)
        report = inspect_saved_capture_periods(self.bundle)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(self.db.exists())

    def test_non_monotonic_capture_times_block(self):
        new = self.root / "time.zip"
        make_zip(new, timestamps=[
            "2025-10-16T12:00:02Z",
            "2025-10-16T12:00:01Z",
            "2025-10-16T12:00:03Z",
        ])
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["reason_code"], "CAPTURE_OBSERVATION_CLOCK_INVALID")
        self.assertFalse(self.db.exists())

    def test_future_selected_filing_not_in_asof_submissions(self):
        different = json.loads(synthetic_submissions())
        different["filings"]["recent"]["filingDate"][0] = "2025-10-17"
        different["filings"]["recent"]["acceptanceDateTime"][0] = "2025-10-17T12:00:00Z"
        new = self.root / "future.zip"
        make_zip(new, submissions=json.dumps(different).encode())
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(self.db.exists())

    def test_cli_read_only_success_and_missing_zip_failure(self):
        data = io.StringIO()
        with redirect_stdout(data):
            self.assertEqual(main(["--capture-zip", str(self.bundle)]), 0)
        report = json.loads(data.getvalue())
        self.assertEqual(report["status"], "review_candidates_available")
        self.assertFalse(self.db.exists())
        missing = self.root / "missing.zip"
        data = io.StringIO()
        with redirect_stdout(data):
            self.assertEqual(main(["--capture-zip", str(missing)]), 2)
        self.assertEqual(json.loads(data.getvalue())["status"], "blocked")
        self.assertNotIn(str(missing), data.getvalue())

    def test_invalid_target_year_fact_does_not_suggest_candidate(self):
        different = synthetic_companyfacts()
        different["facts"]["us-gaap"][TAG]["units"]["USD"][0]["val"] = True
        new = self.root / "invalid-amount.zip"
        make_zip(new, facts=different)
        report = inspect_saved_capture_periods(new)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "INVALID_TARGET_ANNUAL_FACT")

    def test_explicit_candidate_preview_finds_exact_unique_visible_text(self):
        report = inspect_saved_capture_periods(
            self.bundle, show_local_needle_candidates=True,
        )
        self.assertEqual(report["status"], "review_candidates_available")
        choices = report["local_needle_candidates"]
        self.assertTrue(choices)
        found = [x for x in choices if x["needle"] == "TEST_LITERAL_SOURCE_SPAN"]
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual(
            SYNTHETIC_HTML[item["start_byte"]:item["end_byte_exclusive"]],
            item["needle"].encode("ascii"),
        )
        self.assertTrue(item["text_node_only_not_rendered_visibility"])
        self.assertFalse(item["source_authenticated"])
        self.assertFalse(self.db.exists())

    def test_default_preview_does_not_copy_original_needle_text(self):
        r = inspect_saved_capture_periods(self.bundle)
        self.assertNotIn("local_needle_candidates", r)
        self.assertNotIn("TEST_LITERAL_SOURCE_SPAN", json.dumps(r))

    def test_script_only_candidate_never_suggested(self):
        raw = (b"<html><body><script>PRIVATE_SCRIPT_ONLY_TOKEN_98765"
               b"</script><p>Public test paragraph in text body.</p></body></html>")
        src = self.root / "script.zip"
        make_zip(src, original=raw)
        out = inspect_saved_capture_periods(
            src, show_local_needle_candidates=True,
        )
        self.assertEqual(out["status"], "review_candidates_available")
        literals = [x["needle"] for x in out["local_needle_candidates"]]
        self.assertTrue(all("PRIVATE_SCRIPT_ONLY_TOKEN" not in x for x in literals))
        self.assertFalse(self.db.exists())

    def test_ambiguous_duplicate_literal_not_offered(self):
        original = (b"<html><body><p>TEST_LITERAL_SOURCE_SPAN</p>"
                    b"<p>TEST_LITERAL_SOURCE_SPAN</p></body></html>")
        src = self.root / "duplicate.zip"
        make_zip(src, original=original)
        result = inspect_saved_capture_periods(
            src, show_local_needle_candidates=True,
        )
        self.assertEqual(result["status"], "review_candidates_available")
        self.assertNotIn("TEST_LITERAL_SOURCE_SPAN",
                         [x["needle"] for x in result["local_needle_candidates"]])

    def test_cli_opt_in_shows_candidates_but_never_creates_audit(self):
        import io
        from contextlib import redirect_stdout
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([
                "--capture-zip", str(self.bundle),
                "--show-local-needle-candidates",
            ])
        self.assertEqual(code, 0)
        parsed = json.loads(output.getvalue())
        self.assertEqual(parsed["status"], "review_candidates_available")
        self.assertIn("local_needle_candidates", parsed)
        self.assertFalse(self.db.exists())

    def test_bad_needle_preview_flag_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_saved_capture_periods(
                self.bundle, show_local_needle_candidates="yes",
            )

    def test_original_text_not_in_json_summary(self):
        report = inspect_saved_capture_periods(self.bundle)
        self.assertNotIn(SYNTHETIC_HTML.decode("utf-8"), json.dumps(report))
        self.assertNotIn(str(self.bundle), json.dumps(report))
        self.assertFalse(report["trade_executed"])


if __name__ == "__main__":
    unittest.main()
