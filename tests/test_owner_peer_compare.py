"""P268 true two independent issuer 10-K source structures, synthetic only."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import unittest
from unittest.mock import patch

from proofinvest.owner_peer_compare import (
    compare_owner_peer,verify_owner_peer,render_owner_peer_html,
)
from tests.test_ticker_local_report_replay import report_case
from tests.test_ixbrl_revenue_review import xhtml


def paired_synthetic_sources():
    _,primary=report_case()
    peer=dict(primary)
    submissions=json.loads(primary["submissions"])
    submissions["cik"]=320193
    for i,accn in enumerate(submissions["filings"]["recent"]["accessionNumber"]):
        submissions["filings"]["recent"]["accessionNumber"][i]=(
            accn.replace("0001045810","0000320193"))
    peer["submissions"]=json.dumps(submissions,sort_keys=True).encode()
    companyfacts=json.loads(primary["companyfacts"])
    companyfacts["cik"]=320193
    for item in companyfacts["facts"]["us-gaap"].values():
        for row in item["units"]["USD"]:
            row["accn"]=row["accn"].replace("0001045810","0000320193")
            if row["end"]=="2025-09-30":
                row["val"]=300
    peer["companyfacts"]=json.dumps(companyfacts,sort_keys=True).encode()
    peer["original_10k"]=xhtml(current_num="3").replace(
        b"0000000001</xbrli:identifier>",
        b"0000320193</xbrli:identifier>")
    return primary,peer


def run_pair(**overrides):
    original,peer=paired_synthetic_sources()
    opts={
        "ticker":"NVDA","peer_ticker":"AAPL","as_of":"2025-10-16",
        "sources":original,"peer_sources":peer,
    }
    return compare_owner_peer(**(opts|overrides))


class OwnerPeerComparisonTests(unittest.TestCase):
    def test_distinct_real_source_workflows_with_synthetic_peer(self):
        primary,peer=paired_synthetic_sources()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as net:
            result=run_pair(sources=primary,peer_sources=peer)
            self.assertTrue(verify_owner_peer(
                result,ticker="NVDA",peer_ticker="AAPL",as_of="2025-10-16",
                sources=primary,peer_sources=peer),result)
        net.assert_not_called()
        self.assertEqual(result["status"],
                         "TWO_DISTINCT_OWNER_FILINGS_REPLAYED_UNVERIFIED",result)
        self.assertEqual(result["primary"]["ticker"],"NVDA")
        self.assertEqual(result["peer"]["ticker"],"AAPL")
        self.assertNotEqual(result["primary"]["cik"],result["peer"]["cik"])
        self.assertEqual(result["primary"]["revenue_growth_pct"],"100.00")
        self.assertEqual(result["peer"]["revenue_growth_pct"],"200.00")
        self.assertEqual(result["growth_gap_primary_minus_peer_pp"],"-100.00")
        self.assertEqual(result["tool_calls"],14)
        self.assertEqual(result["comparison_guard"],"HOLD")
        self.assertFalse(result["sector_representative"])
        self.assertFalse(result["peer_reuse_rights_verified"])
        self.assertFalse(result["external_sharing_allowed"])
        self.assertFalse(result["source_authenticated"])
        self.assertEqual(result["network_requests"],0)
        self.assertEqual(len(result["integrity_sha256"]),64)
        html=render_owner_peer_html(result,ticker="NVDA",
            peer_ticker="AAPL",as_of="2025-10-16",
            sources=primary,peer_sources=peer)
        self.assertIn(b"<!doctype html>",html.lower())
        self.assertIn(b"-100.00",html)
        self.assertNotIn(b"<script",html.lower())
        self.assertNotIn(b"TEST_LITERAL_SOURCE_SPAN",html)

    def test_other_cik_or_same_ticker_fail_closed(self):
        primary,peer=paired_synthetic_sources()
        for q in ({"ticker":"NVDA","peer_ticker":"NVDA"},
                  {"ticker":"AAPL","peer_ticker":"AAPL"},
                  {"ticker":"NVDA","peer_ticker":"nvda"},
                  {"ticker":"NVDA","peer_ticker":"AAPL",
                   "peer_sources":primary}):
            with self.subTest(q=q):
                result=run_pair(**q)
                self.assertEqual(result["status"],"BLOCKED")
                self.assertFalse(result["trade_executed"])

    def test_substituted_bytes_for_any_of_eight_files_fail_replay(self):
        primary,peer=paired_synthetic_sources()
        base=run_pair()
        for role in ("sources","peer_sources"):
            for key in primary:
                with self.subTest(role=role,key=key):
                    changed=primary.copy() if role=="sources" else peer.copy()
                    changed[key]+=b" "
                    opts={"ticker":"NVDA","peer_ticker":"AAPL",
                          "as_of":"2025-10-16","sources":primary,
                          "peer_sources":peer}
                    opts[role]=changed
                    self.assertFalse(verify_owner_peer(base,**opts))
                    with self.assertRaises(ValueError):
                        render_owner_peer_html(base,**opts)

    def test_fake_hash_and_guard_must_replay_independent_source(self):
        primary,peer=paired_synthetic_sources()
        original=run_pair()
        for key,value in (
            ("growth_gap_primary_minus_peer_pp","900.00"),
            ("comparison_guard","APPROVE"),
            ("peer_reuse_rights_verified",True),
            ("comparison_status","SAME_VINTAGE_OWNED_LICENSED"),
            ("tool_calls",1),
        ):
            with self.subTest(key=key):
                altered=deepcopy(original)
                altered[key]=value
                self.assertFalse(verify_owner_peer(altered,ticker="NVDA",
                    peer_ticker="AAPL",as_of="2025-10-16",
                    sources=primary,peer_sources=peer))

    def test_mismatched_vintages_disable_gap_not_claim_sector(self):
        primary,peer=paired_synthetic_sources()
        # A truly self-consistent peer 10-K ending three months earlier:
        # alter its own submissions, CompanyFacts annual periods and iXBRL
        # contexts together, not a post-verification intermediate dict.
        filings=json.loads(peer["submissions"])
        filings["filings"]["recent"]["reportDate"][1]="2025-06-30"
        peer["submissions"]=json.dumps(filings,sort_keys=True).encode()
        facts=json.loads(peer["companyfacts"])
        updates={
            "2024-10-01":"2024-07-01",
            "2025-09-30":"2025-06-30",
            "2023-10-01":"2023-07-01",
            "2024-09-30":"2024-06-30",
        }
        for record in facts["facts"]["us-gaap"].values():
            for row in record["units"]["USD"]:
                for field in ("start","end"):
                    row[field]=updates.get(row[field],row[field])
        peer["companyfacts"]=json.dumps(facts,sort_keys=True).encode()
        original=peer["original_10k"]
        for old,new in updates.items():
            original=original.replace(old.encode(),new.encode())
        peer["original_10k"]=original
        result=run_pair(sources=primary,peer_sources=peer)
        self.assertEqual(result["status"],
                         "TWO_DISTINCT_OWNER_FILINGS_REPLAYED_UNVERIFIED",result)
        self.assertEqual(result["comparison_status"],
                         "UNAVAILABLE_FISCAL_PERIODS_NOT_ALIGNED",result)
        self.assertIsNone(result["growth_gap_primary_minus_peer_pp"])
        self.assertFalse(result["complete_engine_c"])
        self.assertTrue(verify_owner_peer(result,ticker="NVDA",
            peer_ticker="AAPL",as_of="2025-10-16",
            sources=primary,peer_sources=peer))

    def test_mutated_intermediate_growth_is_not_accepted_after_report_replay(self):
        from proofinvest.owner_peer_compare import run_local_ticker_workflow
        normal=run_local_ticker_workflow
        def mutate(**kwargs):
            result=normal(**kwargs)
            if kwargs["ticker"]=="AAPL" and result.get("revenue"):
                result["revenue"]["growth_pct"]="500.00"
            return result
        with patch("proofinvest.owner_peer_compare.run_local_ticker_workflow",
                   side_effect=mutate):
            result=run_pair()
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["reason_code"],
                         "PAIR_SOURCE_OR_PERIOD_REPLAY_FAILED")

    def test_ui_gate_unmodified_by_peer_feature(self):
        with patch("proofinvest.owner_peer_compare.run_local_ticker_workflow",
                   side_effect=AssertionError("NEVER_CALLED")):
            blocked=run_pair(ticker="NVDA",peer_ticker="NVDA")
            self.assertEqual(blocked["tool_calls"],0)


if __name__=="__main__":
    unittest.main()
