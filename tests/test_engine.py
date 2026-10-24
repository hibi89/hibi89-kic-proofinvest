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
