"""Peer screening is structural and synthetic; never real market advice."""
import copy
import unittest

from proofinvest.peers import screen_peer_candidates
from proofinvest.research import normalize_research


def data():
    base = {
        "industry_code": "SYNTH-001",
        "product_group": "Synthetic infrastructure",
        "business_model": "Synthetic licensing",
        "market_region": "TEST_REGION",
        "size_band": "MEDIUM",
        "fiscal_year": 2024,
        "fs_div": "CFS",
        "currency": "KRW",
    }
    target = dict(base, issuer_id="DEMO-T", source_ids=["S1"])
    matched = dict(base, issuer_id="DEMO-A", source_ids=["S2"])
    return target, matched


def research():
    sources = []
    for n in ("S1", "S2"):
        sources.append({
            "id": n, "title": f"SYNTHETIC_FIXTURE {n}",
            "url": f"https://example.org/peer/{n}",
            "published_at": "2024-12-31", "collected_at": "2025-01-10",
            "license": "SYNTHETIC_FIXTURE",
        })
    return normalize_research({
        "target_name": "Synthetic target",
        "as_of": "2025-01-31",
        "sources": sources,
        "findings": [
            {"claim": "Synthetic example only", "source_ids": ["S1", "S2"], "as_of": "2025-01-31"},
        ],
    })


class PeerScreenTests(unittest.TestCase):
    def test_comparable_is_provisional_never_verified(self):
        target, candidate = data()
        out = screen_peer_candidates(target, [candidate], research())
        self.assertEqual(out["status"], "candidates_for_review")
        self.assertEqual(out["candidates"][0]["state"], "candidate_for_review")
        self.assertFalse(out["verified_real_company_peers"])
        self.assertFalse(out["candidates"][0]["authenticated_external_source"])

    def test_same_industry_alone_is_insufficient(self):
        target, candidate = data()
        for name in ("product_group", "business_model", "market_region", "size_band"):
            with self.subTest(name=name):
                changed = dict(candidate, **{name: "OTHER"})
                row = screen_peer_candidates(target, [changed], research())["candidates"][0]
                self.assertEqual(row["state"], "excluded")
                self.assertIn(name, row["reasons"])

    def test_reporting_year_currency_and_scope_must_match(self):
        target, candidate = data()
        for field, value in (("fiscal_year", 2023), ("currency", "USD"), ("fs_div", "OFS")):
            with self.subTest(field=field):
                row = screen_peer_candidates(target, [dict(candidate, **{field: value})], research())["candidates"][0]
                self.assertIn(field, row["reasons"])

    def test_candidate_with_registered_but_uncited_source_is_excluded(self):
        target, candidate = data()
        evidence = research()
        evidence["findings"][0]["source_ids"] = ["S1"]
        # S2 is still a legitimate Research source, but no surviving
        # finding actually cites it. A profile may not use it as proof.
        before = copy.deepcopy((target, candidate, evidence))
        out = screen_peer_candidates(target, [candidate], evidence)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["candidates"][0]["state"], "excluded")
        self.assertIn("candidate_evidence_missing", out["candidates"][0]["reasons"])
        self.assertEqual((target, candidate, evidence), before)

    def test_target_with_registered_but_uncited_source_blocks_screen(self):
        target, candidate = data()
        evidence = research()
        evidence["findings"][0]["source_ids"] = ["S1"]
        target["source_ids"] = ["S2"]
        out = screen_peer_candidates(target, [candidate], evidence)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["candidates"], [])
        self.assertIn("target_evidence_missing", out["warnings"])

    def test_forged_success_without_valid_findings_cannot_select_peers(self):
        target, candidate = data()
        for invalid in ([], None, [{"source_ids": ["S1", "S2"]}],
                        [{"claim": "synthetic", "source_ids": [[]]}]):
            with self.subTest(invalid=invalid):
                evidence = research()
                evidence["findings"] = invalid
                evidence["status"] = "success"
                out = screen_peer_candidates(target, [candidate], evidence)
                self.assertEqual(out["status"], "unavailable")
                self.assertEqual(out["candidates"], [])
                self.assertIn("malformed_or_uncited_research_findings", out["warnings"])

    def test_partial_research_with_valid_cited_findings_keeps_peer_review(self):
        target, candidate = data()
        evidence = research()
        evidence["status"] = "partial"
        evidence["warnings"].append({"code": "invalid_claim", "detail": "other claim removed"})
        out = screen_peer_candidates(target, [candidate], evidence)
        self.assertEqual(out["status"], "candidates_for_review")
        self.assertEqual(out["candidates"][0]["state"], "candidate_for_review")

    def test_missing_evidence_fails_closed_even_with_matching_sector(self):
        target, candidate = data()
        candidate["source_ids"] = ["UNKNOWN"]
        out = screen_peer_candidates(target, [candidate], research())
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("candidate_evidence_missing", out["candidates"][0]["reasons"])

    def test_missing_target_evidence_stops_whole_screen(self):
        target, candidate = data()
        target["source_ids"] = ["UNKNOWN"]
        out = screen_peer_candidates(target, [candidate], research())
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["candidates"], [])
        self.assertIn("target_evidence_missing", out["warnings"])

    def test_duplicate_candidate_is_not_silently_selected(self):
        target, candidate = data()
        different = dict(candidate, size_band="LARGE")
        out = screen_peer_candidates(target, [candidate, different], research())
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(len(out["candidates"]), 1)
        self.assertIn("duplicate_issuer_id", out["candidates"][0]["reasons"])

    def test_same_target_or_invalid_scope_are_excluded(self):
        target, candidate = data()
        out = screen_peer_candidates(target, [dict(target)], research())
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("same_issuer_as_target", out["candidates"][0]["reasons"])
        invalid = dict(candidate, fs_div="MIXED")
        out = screen_peer_candidates(target, [invalid], research())
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("missing_comparison_metadata", out["candidates"][0]["reasons"])

    def test_cross_module_duplicate_url_alias_cannot_qualify_peer(self):
        target, candidate = data()
        normalized = research()
        self.assertEqual(normalized["status"], "success")
        # Recreate caller-supplied records instead of bypassing the normalizer.
        src = [
            {"id": key, "title": "SYNTHETIC_FIXTURE", "url": "https://example.org/shared",
             "published_at": "2024-12-31", "collected_at": "2025-01-10",
             "license": "SYNTHETIC_FIXTURE"}
            for key in ("S1", "S2")
        ]
        poisoned = normalize_research({
            "target_name": "Synthetic target", "as_of": "2025-01-31",
            "sources": src,
            "findings": [{"claim": "Claim with aliased citations",
                          "source_ids": ["S1", "S2"], "as_of": "2025-01-31"}],
        })
        self.assertEqual(poisoned["status"], "unavailable")
        result = screen_peer_candidates(target, [candidate], poisoned)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["candidates"], [])
        self.assertIn("no_usable_research_evidence", result["warnings"])

    def test_pure_deterministic_and_no_unlinked_data(self):
        target, candidate = data()
        evidence = research()
        before = copy.deepcopy((target, candidate, evidence))
        first = screen_peer_candidates(target, [candidate], evidence)
        self.assertEqual(first, screen_peer_candidates(target, [candidate], evidence))
        self.assertEqual((target, candidate, evidence), before)
        self.assertEqual(screen_peer_candidates(target, [candidate], {})["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
