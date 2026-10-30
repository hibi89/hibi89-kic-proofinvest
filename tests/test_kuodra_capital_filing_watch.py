"""P26 issuer submissions capital/holder filing watch: metadata-only."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions, SYNTHETIC_CIK,
    SYNTHETIC_ACCESSION, AS_OF, COLLECTED_AT,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_capital_filing_watch import review_issuer_capital_filing_watch
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.guard_audit import GuardAuditStore


def make(forms):
    data=json.loads(synthetic_submissions())
    r=data["filings"]["recent"]
    for i,(form,day) in enumerate(forms, start=3):
        r["accessionNumber"].append(f"0000000001-25-{i:06}")
        r["form"].append(form)
        r["filingDate"].append(day)
        r["primaryDocument"].append("untrusted.htm")
        r["acceptanceDateTime"].append(day+"T11:00:00Z")
    return json.dumps(data).encode()


def inspect(raw, **kw):
    return review_issuer_capital_filing_watch(
        raw, cik=kw.get("cik",SYNTHETIC_CIK),
        as_of=kw.get("as_of",AS_OF),
        collected_at=kw.get("collected_at",COLLECTED_AT),
    )


class CapitalFilingsTests(unittest.TestCase):
    def test_issuer_index_absence_is_not_no_ownership_change(self):
        r=inspect(synthetic_submissions())
        self.assertEqual(r["status"],"no_candidates_in_limited_issuer_index")
        self.assertEqual(r["total_matching_recent_metadata"],0)
        self.assertTrue(r["other_filers_cik_not_queried"])
        self.assertTrue(r["absence_does_not_establish_no_issuance_or_ownership_change"])

    def test_registration_event_and_holder_form_are_only_metadata_leads(self):
        r=inspect(make([("S-3","2025-10-14"),("8-K","2025-10-15"),
                        ("SC 13D","2025-10-13"),("424B5","2025-10-15")]))
        self.assertEqual(r["status"],"metadata_candidates_unverified")
        self.assertEqual(r["total_matching_recent_metadata"],4)
        self.assertFalse(r["filing_contents_verified"])
        self.assertFalse(r["capital_change_verified"])
        self.assertFalse(r["beneficial_ownership_verified"])
        self.assertFalse(r["source_authenticated"])
        self.assertIn("REGISTRATION_NOT_ISSUANCE_PROOF",
                      [x["review_class"] for x in r["candidates"]])

    def test_after_asof_is_excluded_without_backdating(self):
        x=inspect(make([("S-3","2025-10-17"),("8-K","2025-10-14")]))
        self.assertEqual(x["total_matching_recent_metadata"],1)
        self.assertEqual(x["candidates"][0]["form"],"8-K")

    def test_cutoff_cannot_precede_claimed_collection(self):
        r=inspect(make([("8-K","2025-10-15")]),collected_at="2025-10-17T01:00:00Z")
        self.assertEqual(r["status"],"unavailable")
        self.assertEqual(r["reason_code"],"SUBMISSIONS_OR_AS_OF_INVALID")

    def test_cross_issuer_and_column_mismatch_block(self):
        x=make([("8-K","2025-10-15")])
        self.assertEqual(inspect(x,cik="0000000002")["reason_code"],"SUBMISSIONS_ISSUER_MISMATCH")
        d=json.loads(x);d["filings"]["recent"]["filingDate"].pop()
        self.assertEqual(inspect(json.dumps(d).encode())["reason_code"],
                         "RECENT_FILING_COLUMNS_INVALID")

    def test_bad_row_and_duplicate_accession_block(self):
        d=json.loads(make([("8-K","2025-10-14")]))
        d["filings"]["recent"]["accessionNumber"][-1]="injected"
        self.assertEqual(inspect(json.dumps(d).encode())["reason_code"],
                         "MALFORMED_CAPITAL_FILING_METADATA")
        d=json.loads(make([("8-K","2025-10-14"),("S-3","2025-10-15")]))
        d["filings"]["recent"]["accessionNumber"][-1]=d["filings"]["recent"]["accessionNumber"][-2]
        self.assertEqual(inspect(json.dumps(d).encode())["reason_code"],
                         "MALFORMED_CAPITAL_FILING_METADATA")

    def test_output_limit_and_order_are_bounded(self):
        rows=[("8-K","2025-10-15")]*12
        x=inspect(make(rows))
        self.assertEqual(x["total_matching_recent_metadata"],12)
        self.assertTrue(x["display_truncated"])
        self.assertEqual(len(x["candidates"]),8)
        self.assertGreater(x["candidates"][0]["accession"],x["candidates"][-1]["accession"])

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        self.assertEqual(inspect(b'{"cik":1,"cik":1,"filings":{}}')["status"],"unavailable")
        self.assertEqual(inspect(b'{"cik":NaN}')["status"],"unavailable")

    def test_unsupported_form_and_untrusted_filer_are_not_guessed(self):
        x=inspect(make([("10-Q","2025-10-14"),("UNKNOWN","2025-10-14")]))
        self.assertEqual(x["total_matching_recent_metadata"],0)
        self.assertTrue(x["other_filers_cik_not_queried"])

    def test_guard_sqlite_html_and_no_network(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p26-") as temp:
            db=Path(temp)/"audit.sqlite"
            with patch("urllib.request.build_opener",side_effect=AssertionError("NO_HTTP")) as net:
                report=review_local_sec_with_guard(
                    submissions_json=make([("8-K","2025-10-15"),("S-3","2025-10-14")]),
                    companyfacts_json=json.dumps(synthetic_companyfacts()).encode(),
                    original_filing=SYNTHETIC_HTML,cik=SYNTHETIC_CIK,
                    accession=SYNTHETIC_ACCESSION,as_of=AS_OF,
                    collected_at=COLLECTED_AT,current_end="2025-09-30",
                    prior_end="2024-09-30",needle=PHRASE,
                    audit_db_path=db,run_id="p26-issuer-watch-1")
            net.assert_not_called()
            self.assertEqual(report["guard"]["decision"],"HOLD")
            self.assertEqual(report["capital_filing_watch"]["total_matching_recent_metadata"],2)
            self.assertFalse(report["capital_filing_watch"]["guard_policy_modified"])
            self.assertTrue(GuardAuditStore(db).verify_chain())
            html=render_local_sec_html(report).decode()
            self.assertIn("발행·주요 주주 관련 제출 문서",html)
            self.assertIn("미발견은 발행",html)
            self.assertNotIn("<script",html.lower())


if __name__=="__main__":
    unittest.main()
