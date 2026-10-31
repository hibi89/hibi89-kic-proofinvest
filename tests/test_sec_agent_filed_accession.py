"""P36: external submitter CIK is not necessarily subject issuer CIK.

Only fabricated input and mocked SEC transport. Genuine source unverified.
"""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    SYNTHETIC_CIK, SYNTHETIC_ACCESSION, AS_OF, COLLECTED_AT,
    synthetic_submissions, synthetic_companyfacts,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.sec_companyfacts import verify_sec_annual_revenue
from proofinvest.local_sec_packet import build_local_sec_review_packet
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.kuodra_loose_sec_compatibility import inspect_loose_sec_bytes
from proofinvest.kuodra_local_workspace import discover_uploaded_periods
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.sec_capture_bundle import save_local_capture_bundle, verify_local_capture_bundle
from proofinvest.kuodra_offline_preflight import inspect_saved_capture_periods
from proofinvest.kuodra_operator_replay import run_offline_proposal_replay
from proofinvest.kuodra_operator_html import render_kuodra_operator_html
from proofinvest.kuodra_history import index_pinned_history
from proofinvest import sec_three_source, kuodra_sec_guard

SUBMITTER_ACCESSION = "0000950170-25-000001"
MISSING_ACCESSION = "0000950170-25-999999"


def made_up_sources():
    submissions = json.loads(synthetic_submissions())
    submissions["filings"]["recent"]["accessionNumber"][0] = SUBMITTER_ACCESSION
    facts = synthetic_companyfacts()
    rows = facts["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"]
    for row in rows:
        row["accn"] = SUBMITTER_ACCESSION
    return {
        "submissions": json.dumps(submissions).encode(),
        "companyfacts": json.dumps(facts).encode(),
        "original_filing": SYNTHETIC_HTML,
    }


def kw():
    return dict(
        cik=SYNTHETIC_CIK, accession=SUBMITTER_ACCESSION,
        as_of=AS_OF, collected_at=COLLECTED_AT,
        current_end="2025-09-30", prior_end="2024-09-30",
        needle=PHRASE, claimed_growth_pct="100.00",
    )


class AgentFiledAccessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw, self.args = made_up_sources(), kw()

    def test_decimal_checks_subject_cik_and_exact_filing_rows(self):
        facts = json.loads(self.raw["companyfacts"])
        k = {name:self.args[name] for name in (
            "cik", "accession", "as_of", "current_end", "prior_end",
        )}
        good = verify_sec_annual_revenue(facts, **k)
        self.assertEqual(good["status"], "calculated_unverified")
        self.assertEqual(good["growth_pct"], "100.00")
        self.assertIn("/data/1/000095017025000001/", good["sec_filing_index"])
        self.assertFalse(good["authenticated_external_source"])
        self.assertEqual(
            verify_sec_annual_revenue({**facts, "cik": 2}, **k)["reason_code"],
            "CIK_MISMATCH",
        )
        self.assertEqual(
            verify_sec_annual_revenue(
                facts, **(k | {"accession": MISSING_ACCESSION})
            )["reason_code"], "ANNUAL_FACTS_UNAVAILABLE",
        )

    def test_loose_discovery_and_guard_still_bind_sources_offline(self):
        found = inspect_loose_sec_bytes(
            submissions_json=self.raw["submissions"],
            companyfacts_json=self.raw["companyfacts"],
            original_filing=self.raw["original_filing"],
            cik=SYNTHETIC_CIK, accession=SUBMITTER_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
        )
        self.assertEqual(found["status"], "operator_review_required")
        self.assertEqual(
            inspect_loose_sec_bytes(
                submissions_json=self.raw["submissions"],
                companyfacts_json=self.raw["companyfacts"],
                original_filing=self.raw["original_filing"],
                cik=SYNTHETIC_CIK, accession=MISSING_ACCESSION,
                as_of=AS_OF, collected_at=COLLECTED_AT,
            )["reason_code"], "TARGET_10K_NOT_IN_SAVED_RECENT_SUBMISSIONS",
        )
        ui = discover_uploaded_periods(
            self.raw, cik=SYNTHETIC_CIK, accession=SUBMITTER_ACCESSION,
            as_of=AS_OF, collected_at=COLLECTED_AT,
        )
        self.assertEqual(ui["status"], "periods_require_operator_selection")
        db = self.root / "audit.sqlite"
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO HTTP")) as network:
            report = review_local_sec_with_guard(
                submissions_json=self.raw["submissions"],
                companyfacts_json=self.raw["companyfacts"],
                original_filing=self.raw["original_filing"],
                audit_db_path=db, run_id="agent-accession", **self.args,
            )
        network.assert_not_called()
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(db).verify_chain())
        self.assertFalse(report["limits"]["external_source_authenticated"])
        with self.assertRaisesRegex(ValueError, "FILING_UNAVAILABLE"):
            build_local_sec_review_packet(
                submissions_json=self.raw["submissions"],
                companyfacts_json=self.raw["companyfacts"],
                original_filing=self.raw["original_filing"],
                **(self.args | {"accession": MISSING_ACCESSION}),
            )

    def test_save_zip_replay_and_html_keep_subject_distinct(self):
        dest = self.root / "source.zip"
        record = {
            "schema": "proofinvest.sec-3source-explicit-transport.v1",
            "status": "three_sec_https_responses_captured_unverified",
            "http_requests_attempted": 3, "live_sec_http_called": True,
            "issuer_cik": SYNTHETIC_CIK, "accession": SUBMITTER_ACCESSION,
            "source_uris": {
                "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
                "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000095017025000001/synthetic10k.htm",
            },
            "raw_response_sha256": {
                name: hashlib.sha256(value).hexdigest() for name,value in self.raw.items()
            },
            "observed_utc_day": AS_OF,
            "submissions_observed_at_utc": COLLECTED_AT.replace("Z", "+00:00"),
            "companyfacts_observed_at_utc": "2025-10-16T12:00:01+00:00",
            "original_observed_at_utc": "2025-10-16T12:00:02+00:00",
            "capture_bytes_persisted": False,
            "source_authenticated": False,
            "financial_facts_authenticated": False,
            "source_rights_verified": False,
            "official_contest_submission": False,
        }
        save_local_capture_bundle(dest, receipt=record, **self.raw)
        self.assertEqual(
            verify_local_capture_bundle(dest)["status"],
            "bundle_integrity_pass_origin_unverified",
        )
        preview = inspect_saved_capture_periods(dest)
        self.assertEqual(preview["status"], "review_candidates_available")
        db = self.root / "operator.sqlite"
        request = {
            "issuer_cik": SYNTHETIC_CIK, "accession": SUBMITTER_ACCESSION,
            "as_of": AS_OF, "requested_intent": "GROWTH_CHECK",
            "capture_zip": str(dest), "audit_db": str(db),
            "run_id": "agent-prefix", "current_end": self.args["current_end"],
            "prior_end": self.args["prior_end"], "needle": PHRASE,
            "claimed_growth_pct": "100.00",
            "expected_source_sha256": preview["source_sha256"],
        }
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO HTTP")) as network:
            done = run_offline_proposal_replay(
                request, '{"action":"RUN","intent":"GROWTH_CHECK"}',
                acknowledge_local_audit_persistence=True,
            )
        network.assert_not_called()
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["issuer"]["cik"], SYNTHETIC_CIK)
        self.assertEqual(done["issuer"]["accession"], SUBMITTER_ACCESSION)
        self.assertIn(b"0000950170-25-000001", render_kuodra_operator_html(done))
        self.assertTrue(GuardAuditStore(db).verify_chain())
        self.assertEqual(
            run_offline_proposal_replay(
                request | {"accession": MISSING_ACCESSION},
                '{"action":"RUN","intent":"GROWTH_CHECK"}',
                acknowledge_local_audit_persistence=True,
            )["status"], "blocked",
        )

    def test_pinned_old_history_accepts_different_submitter_only_when_listed(self):
        base = json.loads(self.raw["submissions"])
        base["filings"]["recent"]["form"][0] = "8-K"
        base["filings"]["recent"]["accessionNumber"][0] = "0000000001-25-000005"
        base["filings"]["files"] = [{
            "name": f"CIK{SYNTHETIC_CIK}-submissions-001.json",
            "filingFrom": "2025-10-15", "filingTo": "2025-10-15",
            "filingCount": 1,
        }]
        history = {
            "accessionNumber": [SUBMITTER_ACCESSION], "form": ["10-K"],
            "filingDate": ["2025-10-15"], "primaryDocument": ["synthetic10k.htm"],
            "acceptanceDateTime": ["2025-10-15T12:00:00Z"],
        }
        index = index_pinned_history(
            base_raw=json.dumps(base).encode(),
            history_raw=json.dumps(history).encode(),
            page_name=f"CIK{SYNTHETIC_CIK}-submissions-001.json",
            cik=SYNTHETIC_CIK, as_of=AS_OF, collected_at=COLLECTED_AT,
        )
        self.assertEqual(index["filings"][0]["accession"], SUBMITTER_ACCESSION)
        self.assertEqual(index["filings"][0]["issuer_cik"], SYNTHETIC_CIK)

    def test_mock_3source_and_guard_wrapper_no_real_http(self):
        from tests.test_sec_three_source import _Opener, FIXED
        raw_companyfacts = self.raw["companyfacts"]
        args = {
            "cik": SYNTHETIC_CIK, "accession": SUBMITTER_ACCESSION,
            "current_end": self.args["current_end"],
            "prior_end": self.args["prior_end"],
            "user_agent": "KUODRA research reachable@reviewer.org",
            "allow_network": True, "acknowledge_three_requests": True,
        }
        with (patch.object(sec_three_source, "_utcnow", return_value=FIXED),
              patch.object(sec_three_source.time, "sleep"),
              patch.object(sec_three_source, "fetch_submissions",
                           return_value=self.raw["submissions"]) as subs,
              patch.object(sec_three_source, "fetch_original",
                           return_value=(SYNTHETIC_HTML, "text/html")) as original,
              patch.object(sec_three_source.urllib.request, "build_opener",
                           return_value=_Opener(raw_companyfacts)) as fake):
            captured = sec_three_source.run_sec_three_source_review(**args)
        self.assertEqual(captured["status"], "three_sec_https_responses_captured_unverified")
        self.assertEqual((subs.call_count, fake.call_count, original.call_count),
                         (1,1,1))
        self.assertFalse(captured["source_authenticated"])
        db = self.root / "guard.sqlite"
        with (patch.object(sec_three_source, "_utcnow", return_value=FIXED),
              patch.object(sec_three_source.time, "sleep"),
              patch.object(sec_three_source, "fetch_submissions",
                           return_value=self.raw["submissions"]),
              patch.object(sec_three_source, "fetch_original",
                           return_value=(SYNTHETIC_HTML, "text/html")),
              patch.object(sec_three_source.urllib.request, "build_opener",
                           return_value=_Opener(raw_companyfacts))):
            guarded = kuodra_sec_guard.run_kuodra_sec_guard(
                **args, audit_db=db, run_id="agent-guard",
                acknowledge_local_audit_persistence=True,
            )
        self.assertEqual(guarded["status"], "REVIEW_RECORDED_SOURCE_UNVERIFIED")
        self.assertEqual(guarded["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(db).verify_chain())


if __name__ == "__main__":
    unittest.main()
