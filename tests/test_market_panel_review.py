"""P270: local UI pure controller boundary; only synthetic vendor-format bytes."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from proofinvest.market_panel_review import (
    review_local_market_panel, verify_local_market_panel,
)
from tests.test_market_panel_offline import raw


def case(count=3):
    symbols=["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL"][:count]
    sources={s:raw(s) for s in ["I:NDX", *symbols]}
    dates={s:"2026-07-31" for s in symbols}
    return sources,symbols,dates


class LocalMarketReviewTests(unittest.TestCase):
    def test_three_and_five_issuers_replay_no_network(self):
        for n in (3,5):
            with self.subTest(n=n):
                sources,symbols,dates=case(n)
                with patch("urllib.request.urlopen",
                           side_effect=AssertionError("NO_PROVIDER_NETWORK")) as net:
                    result=review_local_market_panel(
                        sources,symbols,dates,as_of="2026-10-01")
                    self.assertTrue(verify_local_market_panel(
                        result,sources,symbols,dates,as_of="2026-10-01"),result)
                net.assert_not_called()
                self.assertEqual(result["issuer_count"],n)
                self.assertEqual(result["index_symbol"],"I:NDX")
                self.assertEqual(result["guard_decision"],"HOLD")
                self.assertFalse(result["source_rights_verified"])
                self.assertFalse(result["vendor_response_authenticity_verified"])
                self.assertFalse(result["full_a_b_c_ready"])
                self.assertEqual(result["network_requests"],0)
                self.assertEqual(len({x["index_response_sha256"]
                                      for x in result["issuers"]}),1)

    def test_tampered_bytes_cannot_replay_export(self):
        sources,symbols,dates=case()
        packet=review_local_market_panel(sources,symbols,dates,as_of="2026-10-01")
        modified=dict(sources)
        modified["AAPL"]=raw("AAPL",bump=3)
        self.assertFalse(verify_local_market_panel(
            packet,modified,symbols,dates,as_of="2026-10-01"))
        self.assertFalse(verify_local_market_panel(
            {**packet,"source_rights_verified":True},sources,symbols,dates,
            as_of="2026-10-01"))

    def test_missing_index_wrong_identity_and_unbounded_size_block(self):
        sources,symbols,dates=case()
        for invalid in (
            {k:v for k,v in sources.items() if k!="I:NDX"},
            {**sources,"I:NDX":raw("QQQ")},
            {**sources,"MSFT":b"0" * 262145},
        ):
            with self.subTest(size=len(invalid)):
                r=review_local_market_panel(invalid,symbols,dates,
                                            as_of="2026-10-01")
                self.assertEqual(r["status"],"BLOCKED")
                self.assertEqual(r["guard_decision"],"HOLD")
                self.assertFalse(r["source_rights_verified"])

    def test_postfiling_gate_and_extra_symbol(self):
        sources,symbols,dates=case()
        invalid_dates={**dates,"NVDA":"2026-10-01"}
        self.assertEqual(review_local_market_panel(
            sources,symbols,invalid_dates,
            as_of="2026-10-01")["status"],"BLOCKED")
        self.assertEqual(review_local_market_panel(
            sources,symbols+["TSLA"],dates,
            as_of="2026-10-01")["status"],"BLOCKED")
        self.assertEqual(review_local_market_panel(
            sources,symbols,{**dates,"AAPL":"wrong"},
            as_of="2026-10-01")["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
