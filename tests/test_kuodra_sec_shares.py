"""P25 descriptive SEC shares snapshots, without inventing dilution."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from proofinvest.kuodra_sec_shares import review_sec_shares_outstanding
from proofinvest.kic_dl_demo import synthetic_companyfacts, synthetic_submissions, SYNTHETIC_CIK, SYNTHETIC_ACCESSION, AS_OF, COLLECTED_AT
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.guard_audit import GuardAuditStore

CUR="2025-09-30"
PREV="2024-09-30"

def row(val, end=CUR, filed="2025-10-15", accession=SYNTHETIC_ACCESSION):
    return {"accn":accession,"form":"10-K","end":end,"filed":filed,"val":val}

def data(curr=None, prev=None, dei=None):
    f=synthetic_companyfacts()
    if curr is not None:
        r=[row(curr)]
        if prev is not None:r.append(row(prev,PREV))
        f["facts"]["us-gaap"]["CommonStockSharesOutstanding"]={"units":{"shares":r}}
    if dei is not None:
        f["facts"]["dei"]={"EntityCommonStockSharesOutstanding":{"units":{"shares":[row(dei,"2025-10-01")]}}}
    return f

def assess(f, asof=AS_OF):
    return review_sec_shares_outstanding(json.dumps(f).encode(),cik=SYNTHETIC_CIK,accession=SYNTHETIC_ACCESSION,period_end=CUR,prior_end=PREV,as_of=asof)

class SharesTests(unittest.TestCase):
    def test_same_filing_fiscal_shares_change_not_dilution(self):
        with patch("urllib.request.build_opener",side_effect=AssertionError("HTTP")) as net:
            x=assess(data(120000000,100000000))
        net.assert_not_called()
        self.assertEqual(x["shares_change_pct"],"20.00")
        self.assertEqual(x["basis"],"FISCAL_END_INSTANT")
        self.assertTrue(x["shares_change_is_not_dilution_or_issuance"])
        self.assertFalse(x["ownership_verified"])
        self.assertFalse(x["source_authenticated"])

    def test_current_only_has_no_invented_change(self):
        x=assess(data(curr=100))
        self.assertEqual(x["shares_outstanding"],"100")
        self.assertIsNone(x["shares_change_pct"])

    def test_dei_cover_date_distinct_from_fiscal_end(self):
        x=assess(data(dei=55))
        self.assertEqual(x["basis"],"COVER_PAGE_DATE_NOT_FISCAL_END")
        self.assertEqual(x["snapshot_date"],"2025-10-01")
        self.assertIsNone(x["shares_change_pct"])

    def test_nonmatching_accession_or_missing_is_unavailable(self):
        x=data(curr=100)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"][0]["accn"]="0000000001-25-000099"
        self.assertEqual(assess(x)["status"],"unavailable")
        self.assertEqual(assess(synthetic_companyfacts())["status"],"unavailable")

    def test_bad_units_and_duplicate_values_never_pass(self):
        x=data(curr=100)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["USD"]=[]
        self.assertEqual(assess(x)["reason_code"],"SHARES_UNSUPPORTED_OR_MIXED_UNITS")
        x=data(curr=100)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"].append(row(101))
        self.assertEqual(assess(x)["reason_code"],"SHARES_MULTIPLE_SNAPSHOT_AMBIGUOUS")

    def test_invalid_integer_and_duration_rejected(self):
        for value in (True,-1,0,10**13):
            with self.subTest(value=value):
                self.assertEqual(assess(data(curr=value))["status"],"unavailable")
        x=data(curr=100)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"][0]["start"]="2024-10-01"
        self.assertEqual(assess(x)["reason_code"],"SHARES_INVALID_INSTANT_OR_AMOUNT")

    def test_later_filing_cannot_be_backdated(self):
        x=data(curr=100)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"][0]["filed"]="2025-10-17"
        self.assertEqual(assess(x)["reason_code"],"SHARES_FILING_AFTER_AS_OF")

    def test_malformed_fiscal_tag_not_replaced_by_dei(self):
        x=data(curr=100,dei=99)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"][0]["val"]=0
        self.assertEqual(assess(x)["status"],"unavailable")

    def test_wrong_issuer_and_mixed_filing_dates(self):
        x=data(curr=100,prev=75);x["cik"]=2
        self.assertEqual(assess(x)["reason_code"],"SHARES_ISSUER_MISMATCH")
        x=data(curr=100,prev=75)
        x["facts"]["us-gaap"]["CommonStockSharesOutstanding"]["units"]["shares"][1]["filed"]="2025-10-14"
        self.assertEqual(assess(x)["reason_code"],"MIXED_SHARES_FILING_DATES_NO_COMPARISON")

    def test_guard_sqlite_and_html_show_shares_without_authorization(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p25-") as tmp:
            db=Path(tmp)/"audit.sqlite"
            with patch("urllib.request.build_opener",side_effect=AssertionError("NO_EXTERNAL")) as net:
                x=review_local_sec_with_guard(
                    submissions_json=synthetic_submissions(),
                    companyfacts_json=json.dumps(data(curr=120000000,prev=100000000)).encode(),
                    original_filing=SYNTHETIC_HTML,cik=SYNTHETIC_CIK,
                    accession=SYNTHETIC_ACCESSION,as_of=AS_OF,collected_at=COLLECTED_AT,
                    current_end=CUR,prior_end=PREV,needle=PHRASE,
                    audit_db_path=db,run_id="p25-001")
            net.assert_not_called()
            self.assertEqual(x["guard"]["decision"],"HOLD")
            self.assertEqual(x["share_capital"]["shares_change_pct"],"20.00")
            self.assertTrue(GuardAuditStore(db).verify_chain())
            page=render_local_sec_html(x).decode()
            self.assertIn("120000000 shares",page)
            self.assertIn("주식 수 변화는",page)
            self.assertFalse(x["limits"]["external_source_authenticated"])

if __name__=="__main__":
    unittest.main()
