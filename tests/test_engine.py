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
