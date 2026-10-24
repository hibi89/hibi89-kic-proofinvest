import unittest
from decimal import Decimal
from proofinvest.engine import calculate,amount,parse_accounts
from proofinvest.dart_adapter import fetch_major_accounts

ROWS=[{"account_nm":"매출액","fs_div":"CFS","thstrm_amount":"120","frmtrm_amount":"100","rcept_no":"","currency":"KRW"},
      {"account_nm":"매출액","fs_div":"OFS","thstrm_amount":"999","frmtrm_amount":"100","rcept_no":"","currency":"KRW"},
      {"account_nm":"부채총계","fs_div":"CFS","thstrm_amount":"80","frmtrm_amount":"70","rcept_no":"","currency":"KRW"},
      {"account_nm":"자본총계","fs_div":"CFS","thstrm_amount":"30","frmtrm_amount":"30","rcept_no":"","currency":"KRW"}]

class EngineTests(unittest.TestCase):
    def test_amount(self):self.assertEqual(amount('1,230'),Decimal(1230))
    def test_invalid_amount_not_invented(self):self.assertIsNone(amount('N/A'))
    def test_cfs_preferred(self):self.assertEqual(parse_accounts(ROWS,2024)['revenue']['current'],120)
    def test_yoy_verified(self):self.assertEqual(calculate(ROWS,2024,'20',True)['checks'][0]['state'],'verified')
    def test_yoy_conflict(self):self.assertEqual(calculate(ROWS,2024,'30',True)['checks'][0]['state'],'conflict')
    def test_missing_is_unavailable(self):self.assertEqual(calculate([],2024)['checks'][0]['state'],'unavailable')
    def test_no_division_by_zero(self):
        test=[dict(r) for r in ROWS]
        for r in test:
            if r['account_nm']=='자본총계':r['thstrm_amount']='0'
        self.assertIsNone(calculate(test,2024)['risk_signals'][0]['triggered'])
    def test_duplicate_revenue_rejected_in_same_statement(self):
        duplicated=[dict(r) for r in ROWS]
        duplicated.append(dict(ROWS[0],thstrm_amount="999"))
        accounts=parse_accounts(duplicated,2024)
        self.assertNotIn("revenue",accounts)
        outcome=calculate(duplicated,2024,"20",True)
        self.assertEqual(outcome["checks"][0]["state"],"unavailable")
        self.assertIsNone(outcome["checks"][0]["value"])

    def test_even_identical_duplicate_revenue_rejected(self):
        duplicated=[dict(r) for r in ROWS]+[dict(ROWS[0])]
        self.assertEqual(calculate(duplicated,2024,"20",True)["checks"][0]["state"],"unavailable")

    def test_multiple_duplicates_cannot_resurrect_revenue(self):
        duplicated=[dict(r) for r in ROWS]+[
            dict(ROWS[0],thstrm_amount=str(n)) for n in (999,998)
        ]
        self.assertNotIn("revenue",parse_accounts(duplicated,2024))

    def test_duplicate_risk_input_prevents_risk_signal(self):
        duplicated=[dict(r) for r in ROWS]+[dict(ROWS[2],thstrm_amount="777")]
        result=calculate(duplicated,2024,"20",True)
        self.assertEqual(result["checks"][0]["state"],"verified")
        self.assertIsNone(result["risk_signals"][0]["triggered"])
        self.assertIsNone(result["risk_signals"][0]["value"])

    def test_duplicates_outside_selected_cfs_do_not_poison_cfs(self):
        duplicated=[dict(r) for r in ROWS]+[dict(ROWS[1],thstrm_amount="1")]
        self.assertEqual(parse_accounts(duplicated,2024)["revenue"]["current"],Decimal(120))
        self.assertEqual(calculate(duplicated,2024,"20",True)["checks"][0]["state"],"verified")

    def test_matching_annual_metadata_keeps_comparable_rows(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011") for r in ROWS]
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_selected_statement_mixed_year_fails_closed(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011") for r in ROWS]
        rows[2]["bsns_year"]="2023"
        result=calculate(rows,2024,"20",True)
        self.assertEqual(result["checks"][0]["state"],"unavailable")
        self.assertIsNone(result["risk_signals"][0]["triggered"])

    def test_quarterly_report_not_annual_comparison(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011") for r in ROWS]
        rows[0]["reprt_code"]="11013"
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"unavailable")

    def test_missing_report_metadata_amid_annual_rows_fails_closed(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011") for r in ROWS]
        del rows[2]["reprt_code"]
        self.assertEqual(parse_accounts(rows,2024),{})

    def test_period_dates_accept_ranges_and_single_end_dates(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2024.01.01 ~ 2024.12.31",
                   frmtrm_dt="2023.01.01 ~ 2023.12.31") for r in ROWS]
        rows[2]["thstrm_dt"]="2024.12.31"
        rows[2]["frmtrm_dt"]="2023.12.31"
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_mixed_disclosed_period_end_dates_fail_closed(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2024.01.01 ~ 2024.12.31",
                   frmtrm_dt="2023.01.01 ~ 2023.12.31") for r in ROWS]
        rows[2]["thstrm_dt"]="2024.09.30"
        self.assertEqual(parse_accounts(rows,2024),{})

    def test_reversed_or_unreadable_period_dates_fail_closed(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2024.12.31",frmtrm_dt="2023.12.31") for r in ROWS]
        rows[0]["frmtrm_dt"]="2025.12.31"
        self.assertEqual(parse_accounts(rows,2024),{})
        rows[0]["frmtrm_dt"]="not a date"
        self.assertEqual(parse_accounts(rows,2024),{})

    def test_invalid_nonselected_ofs_does_not_poison_cfs(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011") for r in ROWS]
        rows[1]["bsns_year"]="2022"
        rows[1]["reprt_code"]="11013"
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_only_ofs_rows_must_match_year_and_report(self):
        rows=[dict(ROWS[1],bsns_year="2023",reprt_code="11011")]
        self.assertEqual(calculate(rows,2024,"899",True)["checks"][0]["state"],"unavailable")
        rows[0]["bsns_year"]="2024"
        # OFS synthetic revenue 999 vs 100 => 899% growth, not 20%.
        self.assertEqual(calculate(rows,2024,"899",True)["checks"][0]["state"],"verified")

    def test_annual_report_cannot_reuse_stale_year_end(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2023.01.01 ~ 2023.12.31",
                   frmtrm_dt="2022.01.01 ~ 2022.12.31") for r in ROWS]
        self.assertEqual(parse_accounts(rows,2024),{})
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"unavailable")

    def test_annual_report_cannot_skip_prior_fiscal_year(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2024.01.01 ~ 2024.12.31",
                   frmtrm_dt="2022.01.01 ~ 2022.12.31") for r in ROWS]
        self.assertEqual(parse_accounts(rows,2024),{})
        self.assertIsNone(calculate(rows,2024,"20",True)["risk_signals"][0]["triggered"])

    def test_non_december_annual_fiscal_year_still_allowed(self):
        rows=[dict(r,bsns_year="2024",reprt_code="11011",
                   thstrm_dt="2023.04.01 ~ 2024.03.31",
                   frmtrm_dt="2022.04.01 ~ 2023.03.31") for r in ROWS]
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_mixed_cfs_currency_fails_closed_without_ofs_fallback(self):
        rows=[dict(r) for r in ROWS]
        rows[2]["currency"]="USD"
        self.assertEqual(parse_accounts(rows,2024),{})
        result=calculate(rows,2024,"20",True)
        self.assertEqual(result["checks"][0]["state"],"unavailable")
        self.assertIsNone(result["risk_signals"][0]["value"])

    def test_mixed_explicit_amount_units_fail_closed(self):
        rows=[dict(r,amount_unit="원") for r in ROWS]
        rows[3]["amount_unit"]="천원"
        self.assertEqual(parse_accounts(rows,2024),{})

    def test_partial_amount_unit_metadata_fails_closed(self):
        rows=[dict(r) for r in ROWS]
        rows[0]["amount_unit"]="원"
        self.assertEqual(parse_accounts(rows,2024),{})

    def test_uniform_unit_metadata_preserves_calculation(self):
        rows=[dict(r,amount_unit="원",unit_nm="원") for r in ROWS]
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_unselected_ofs_unit_conflict_does_not_poison_cfs(self):
        rows=[dict(r,amount_unit="원") for r in ROWS]
        rows[1]["currency"]="USD"
        rows[1]["amount_unit"]="천원"
        self.assertEqual(calculate(rows,2024,"20",True)["checks"][0]["state"],"verified")

    def test_no_live_without_key(self):
        import os
        old=os.environ.pop('OPENDART_API_KEY',None)
        try:
            with self.assertRaises(RuntimeError):fetch_major_accounts('00126380',2024)
        finally:
            if old is not None:os.environ['OPENDART_API_KEY']=old
    def test_no_unvalidated_corp_code(self):
        with self.assertRaises(ValueError):fetch_major_accounts('invalid',2024,api_key='dummy')

if __name__=='__main__':unittest.main()
