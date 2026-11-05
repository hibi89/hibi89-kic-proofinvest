"""P225 fact-review case: genuine NVDA B + unlicensed local A + AMD/INTC C."""
from __future__ import annotations

from copy import deepcopy
from datetime import date,timedelta
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.real_issuer_local_market import review_real_issuer_local_market_pair
from proofinvest.real_issuer_abc_local_review import build_partial_source_bound_abc
from proofinvest.real_issuer_abc_fact_review import (
    build_source_factual_abc_brief, replay_source_factual_abc_brief,
    source_factual_brief_html,
)


def vendor(ticker,base):
    d=date(2026,8,18);i=0;rows={}
    while d<=date(2026,11,4):
        if d.weekday()<5:
            rows[d.isoformat()]={"4. close":str(base+i*2+(i%5)*3)}
            i+=1
        d+=timedelta(days=1)
    return json.dumps({"Meta Data":{"2. Symbol":ticker},
                       "Time Series (Daily)":rows}).encode()


def ab(ticker="NVDA"):
    return review_real_issuer_local_market_pair(
        ticker=ticker,stock_json=vendor(ticker,120),
        ndx_json=vendor("NDX",10000))


def joined():
    return build_partial_source_bound_abc(ab_review=ab())


class RealAbcFactReviewTests(unittest.TestCase):
    def test_real_cross_source_a_b_c_fact_sheet_and_safe_html(self):
        packet=joined()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
            report=build_source_factual_abc_brief(packet)
            self.assertTrue(replay_source_factual_abc_brief(report,packet))
            html=source_factual_brief_html(report,packet)
            network.assert_not_called()
        self.assertEqual(report["status"],
                         "LOCAL_A_B_C_CLAIM_REVIEW_FOR_HUMAN_ONLY",report)
        self.assertEqual(report["review_outcomes"],
                         ["UNAVAILABLE","VERIFIED","VERIFIED","VERIFIED","VERIFIED"])
        self.assertEqual([f["engine"] for f in report["claims"]],
                         ["A","B","B","C","C"])
        self.assertEqual([f["value"] for f in report["claims"]],
                         [None,"65.47","0.8555","34.34","-0.47"])
        self.assertEqual(report["publisher_source_sha256"],
                         packet["source_linked_issuer_sha256"])
        self.assertEqual(report["linked_abc_digest"],packet["derived_sha256"])
        self.assertEqual([ref["ticker"] for ref in report["source_links"]],
                         ["NVDA","AMD","INTC"])
        self.assertEqual(report["guard_policy_preview"],"HOLD")
        for key in ("llm_invoked","ai_agent_executed","trade_executed",
                    "investment_recommendation","market_rights_verified",
                    "source_rights_verified","peer_raw_sources_verified",
                    "full_abc_complete","external_sharing_allowed"):
            self.assertFalse(report[key],key)
        self.assertEqual(report["network_requests"],0)
        self.assertLess(len(html),32768)
        self.assertIn("NVIDIA".encode(),html)
        self.assertIn("AMD".encode(),html)
        self.assertNotIn(b"Time Series (Daily)",html)
        self.assertNotIn(b"4. close",html)
        self.assertNotIn(b"apikey",html.lower())
        self.assertNotIn(b"<script",html.lower())
        self.assertIn(b"rel=\"noopener noreferrer\"",html)

    def test_issuer_market_peer_identity_forgery_or_added_raw_fails_closed(self):
        for key,forged in (
            ("source_linked_issuer_sha256","a"*64),
            ("ticker","DELL"),
            ("source_provider_authenticated",True),
            ("market_rights_verified",True),
        ):
            changed=deepcopy(joined())
            changed[key]=forged
            with self.subTest(key=key):
                out=build_source_factual_abc_brief(changed)
                self.assertEqual(out["status"],"BLOCKED")
        changed=deepcopy(joined())
        changed["raw_market_rows"]="PRIVATE"
        self.assertEqual(build_source_factual_abc_brief(changed)["status"],"BLOCKED")

    def test_recomputed_digest_cannot_rewrite_real_peer_or_text(self):
        packet=joined()
        report=build_source_factual_abc_brief(packet)
        forged=deepcopy(report)
        forged["claims"][3]["value"]="10000"
        unsigned=deepcopy(forged)
        unsigned.pop("brief_sha256")
        forged["brief_sha256"]=sha256(json.dumps(
            unsigned,ensure_ascii=False,sort_keys=True,
            separators=(",",":"),allow_nan=False).encode()).hexdigest()
        self.assertFalse(replay_source_factual_abc_brief(forged,packet))
        with self.assertRaises(ValueError):
            source_factual_brief_html(forged,packet)
        extra=deepcopy(report)
        extra["approved_investment"]="BUY"
        self.assertFalse(replay_source_factual_abc_brief(extra,packet))

    def test_blocked_market_issuer_or_missing_peer_does_not_yield_fact_sheet(self):
        invalid=build_partial_source_bound_abc(ab_review=ab("DELL"))
        self.assertEqual(build_source_factual_abc_brief(invalid)["status"],"BLOCKED")
        with patch("proofinvest.real_issuer_abc_fact_review.review_supported_real_ticker",
                   return_value={"status":"BLOCKED"}):
            self.assertEqual(build_source_factual_abc_brief(joined())["status"],"BLOCKED")
