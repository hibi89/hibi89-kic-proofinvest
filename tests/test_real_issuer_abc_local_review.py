"""P224 actual issuer B + operator local A + AMD/Intel peer C single artifact."""
from __future__ import annotations
from datetime import date,timedelta
from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch
from proofinvest.real_issuer_local_market import review_real_issuer_local_market_pair
from proofinvest.real_issuer_abc_local_review import (
    build_partial_source_bound_abc,replay_partial_source_bound_abc,
)
from proofinvest.intel_amd_peer_cohort import review_two_official_10k_peers

def market(symbol,base):
    day=date(2026,8,18);rows={};i=0
    while day<=date(2026,11,4):
        if day.weekday()<5:
            rows[day.isoformat()]={"4. close":str(base+i*2+(i%5)*3)}
            i+=1
        day+=timedelta(days=1)
    return json.dumps({"Meta Data":{"2. Symbol":symbol},
                       "Time Series (Daily)":rows}).encode()

def ab(ticker="NVDA"):
    return review_real_issuer_local_market_pair(
        ticker=ticker,stock_json=market(ticker,120),
        ndx_json=market("NDX",10000))

class ThreeEngineRealLocalPartialTests(unittest.TestCase):
    def test_actual_issuer_and_two_peers_in_one_guarded_packet(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK")) as net:
            packet=build_partial_source_bound_abc(ab_review=ab())
            self.assertTrue(replay_partial_source_bound_abc(packet),packet)
            net.assert_not_called()
        self.assertEqual(packet["ticker"],"NVDA")
        self.assertEqual(packet["engine_ab_partial"]["engine_b"]["revenue_growth_pct"],"65.47")
        self.assertEqual(packet["engine_c_partial"]["peer_count"],2)
        self.assertEqual([r["ticker"] for r in packet["engine_c_partial"]["source_revenue_growth_observations_not_sector_rank"]],["NVDA","AMD","INTC"])
        self.assertEqual(packet["engine_c_partial"]["nvda_minus_amd_growth_pp"],"31.14")
        self.assertEqual(packet["engine_c_partial"]["nvda_minus_intc_growth_pp"],"65.94")
        self.assertEqual(packet["stock_uploaded_sha256"],sha256(market("NVDA",120)).hexdigest())
        self.assertEqual(packet["ndx_uploaded_sha256"],sha256(market("NDX",10000)).hexdigest())
        for key in ("guard_executed","full_abc_complete","market_rights_verified",
                    "peer_rights_verified","sec_edgar_original_bytes_verified",
                    "ai_model_source_processing_authorized","source_provider_authenticated",
                    "investment_recommendation","trade_executed","ai_agent_executed"):
            self.assertFalse(packet[key],key)
        self.assertEqual(packet["guard_policy_preview"],"HOLD")
        self.assertEqual(packet["network_requests"],0)
        exported=json.dumps(packet)
        for raw in ('"Time Series (Daily)"','"4. close"','"apikey"'):
            self.assertNotIn(raw,exported)
        self.assertLess(len(exported.encode()),65536)

    def test_wrong_issuer_and_tampered_ab_block(self):
        self.assertEqual(build_partial_source_bound_abc(ab_review=ab("DELL"))["status"],"BLOCKED")
        for field,value in (("combined_review_sha256","f"*64),
                            ("issuer_source_sha256","a"*64),
                            ("ticker","INTC"),("as_of","2026-11-06")):
            forged=deepcopy(ab());forged[field]=value
            self.assertEqual(build_partial_source_bound_abc(ab_review=forged)["status"],"BLOCKED")

    def test_c_peer_mutation_or_loss_fail_closed(self):
        original=review_two_official_10k_peers()
        forged=deepcopy(original);forged["intel_filing_accession"]="0000050863-26-000012"
        self.assertEqual(build_partial_source_bound_abc(
            ab_review=ab(),peer_review=forged)["status"],"BLOCKED")
        with patch("proofinvest.real_issuer_abc_local_review.review_two_official_10k_peers",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(build_partial_source_bound_abc(ab_review=ab())["status"],"BLOCKED")

    def test_rehash_cannot_fake_real_peer_numbers(self):
        report=build_partial_source_bound_abc(ab_review=ab())
        self.assertTrue(replay_partial_source_bound_abc(report))
        forged=deepcopy(report)
        forged["engine_c_partial"]["nvda_minus_intc_growth_pp"]="999.99"
        self.assertFalse(replay_partial_source_bound_abc(forged))
        unsigned=deepcopy(forged);unsigned.pop("derived_sha256")
        forged["derived_sha256"]=sha256(json.dumps(
            unsigned,sort_keys=True,ensure_ascii=False,
            separators=(",",":"),allow_nan=False).encode()).hexdigest()
        self.assertFalse(replay_partial_source_bound_abc(forged))
        extra=deepcopy(report);extra["raw_market_secret"]="x"
        self.assertFalse(replay_partial_source_bound_abc(extra))
