"""P269 synthetic Massive-format multi-company regression, zero GET."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
import json
import unittest
from proofinvest.market_panel_offline import LocalMassivePanel
TICKERS=(("NVDA","0001045810"),("AAPL","0000320193"),("MSFT","0000789019"))

def raw(symbol, count=65, bump=None):
    points=[]
    first=date(2026,7,1)
    for n in range(180):
        d=first+timedelta(days=n)
        if d.weekday()>=5:
            continue
        val=(10000 if symbol=="I:NDX" else 100)+n*(1.55 if symbol=="I:NDX" else 0.25)
        if bump is not None and len(points)==bump:
            val+=30
        dt=datetime(d.year,d.month,d.day,5,tzinfo=timezone.utc)
        points.append({"t":int(dt.timestamp()*1000),"c":round(val,2)})
        if len(points)==count:
            break
    obj={"status":"OK","ticker":symbol,"results":points,
         "queryCount":len(points),"resultsCount":len(points)}
    if symbol!="I:NDX":
        obj["adjusted"]=False
    return json.dumps(obj,separators=(",",":")).encode()

class PanelTests(unittest.TestCase):
    def cache(self):
        panel=LocalMassivePanel()
        for sym in ("I:NDX","NVDA","AAPL","MSFT"):
            panel.ingest(raw(sym),symbol=sym,as_of="2026-10-01")
        return panel
    def companies(self):
        return [{"ticker":s,"issuer_cik":c,"filing_date":"2026-07-31"}
                for s,c in TICKERS]
    def test_three_stocks_one_real_index_symbol_and_guard(self):
        r=self.cache().analyze(companies=self.companies(),as_of="2026-10-01")
        self.assertEqual(r["status"],"MULTI_ISSUER_ENGINE_A_DESCRIPTIVE_UNVERIFIED",r)
        self.assertEqual(r["issuer_count"],3)
        self.assertEqual(r["index_symbol"],"I:NDX")
        self.assertEqual(len({x["index_response_sha256"] for x in r["issuers"]}),1)
        self.assertTrue(all(x["market_analysis"]["beta"] is not None and
                            x["matched_observation_count"]>=31 for x in r["issuers"]))
        self.assertFalse(r["source_rights_verified"])
        self.assertFalse(r["full_a_b_c_ready"])
        self.assertEqual(r["guard_decision"],"HOLD")
        self.assertEqual(r["network_requests"],0)
        self.assertNotIn("close_observations",json.dumps(r))
    def test_missing_ndx_or_qqq_rejected(self):
        panel=LocalMassivePanel()
        for sym,_ in TICKERS:
            panel.ingest(raw(sym),symbol=sym,as_of="2026-10-01")
        self.assertEqual(panel.analyze(companies=self.companies(),
                         as_of="2026-10-01")["status"],"BLOCKED")
        with self.assertRaises(ValueError):
            panel.ingest(raw("QQQ"),symbol="QQQ",as_of="2026-10-01")
        with self.assertRaises(ValueError):
            panel.ingest(raw("QQQ"),symbol="I:NDX",as_of="2026-10-01")
    def test_cache_hit_and_rate_batches(self):
        panel=self.cache()
        self.assertEqual(panel.ingest(raw("NVDA"),symbol="NVDA",
                         as_of="2026-10-01")["status"],"CACHE_HIT")
        self.assertEqual(panel.refresh_plan(symbols=["NVDA","AAPL","MSFT"],
                         as_of="2026-10-01")
                         ["estimated_provider_requests_if_separately_approved"],0)
        plan=LocalMassivePanel().refresh_plan(
            symbols=["NVDA","AAPL","MSFT","AMZN","GOOGL"],as_of="2026-10-01")
        self.assertEqual([len(x) for x in plan["batches_max_five_per_minute"]],[5,1])
        self.assertEqual(plan["network_requests"],0)
    def test_rolling_update_conflict_and_rollback(self):
        panel=self.cache()
        self.assertEqual(panel.ingest(raw("NVDA",66),symbol="NVDA",
                         as_of="2026-10-02")["status"],"INGESTED_UNVERIFIED")
        with self.assertRaisesRegex(ValueError,"STALE_SNAPSHOT"):
            panel.ingest(raw("NVDA"),symbol="NVDA",as_of="2026-10-01")
        with self.assertRaisesRegex(ValueError,"HISTORICAL_REVISION"):
            panel.ingest(raw("NVDA",67,bump=9),symbol="NVDA",as_of="2026-10-03")
    def test_duplicate_company_cik_and_bad_post_filing_window(self):
        panel=self.cache()
        bad=self.companies()
        bad[1]["issuer_cik"]=bad[0]["issuer_cik"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_COMPANY"):
            panel.analyze(companies=bad,as_of="2026-10-01")
        bad=self.companies()
        bad[1]["filing_date"]="2026-09-01"
        self.assertEqual(panel.analyze(companies=bad,
                         as_of="2026-10-01")["status"],"BLOCKED")
    def test_missing_new_asof_and_clear(self):
        panel=self.cache()
        self.assertEqual(panel.analyze(companies=self.companies(),
                         as_of="2026-10-02")["status"],"BLOCKED")
        panel.clear()
        self.assertEqual(panel.refresh_plan(symbols=["NVDA","AAPL","MSFT"],
                         as_of="2026-10-01")
                         ["estimated_provider_requests_if_separately_approved"],4)

if __name__=="__main__":
    unittest.main()
