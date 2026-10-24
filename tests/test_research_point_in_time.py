"""Offline point-in-time provenance: no evidence obtained after claim/as_of."""
import copy
import unittest

from proofinvest.research import normalize_research


def fixture():
    return {
        "target_name": "Synthetic Test", "target_id": "EXAMPLE-001",
        "as_of": "2026-01-31",
        "sources": [{
            "id": "S1", "title": "Synthetic Test Source",
            "url": "https://example.org/research/source1",
            "published_at": "2026-01-10", "collected_at": "2026-01-11",
            "license": "not_verified",
        }],
        "findings": [{
            "claim": "Synthetic statement, not a real financial fact",
            "source_ids": ["S1"], "as_of": "2026-01-31",
        }],
    }


class PointInTimeResearchTests(unittest.TestCase):
    def test_future_collection_cannot_support_past_as_of(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-02-01"
        out = normalize_research(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["sources"], [])
        self.assertEqual(out["findings"], [])
        self.assertIn("future_collected", [x["code"] for x in out["warnings"]])

    def test_finding_cannot_predate_actual_evidence_collection(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-25"
        data["findings"][0]["as_of"] = "2026-01-20"
        out = normalize_research(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(len(out["sources"]), 1)
        self.assertEqual(out["findings"], [])
        self.assertIn("finding_precedes_collection", [x["code"] for x in out["warnings"]])

    def test_collection_on_same_as_of_day_is_permitted(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-31"
        self.assertEqual(normalize_research(data)["status"], "success")

    def test_finding_on_collection_day_is_permitted(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-25"
        data["findings"][0]["as_of"] = "2026-01-25"
        self.assertEqual(normalize_research(data)["status"], "success")

    def test_one_future_source_does_not_poison_independent_valid_claim(self):
        data = fixture()
        late = dict(data["sources"][0], id="S2",
                    url="https://example.org/research/late-source",
                    collected_at="2026-02-01")
        data["sources"].append(late)
        data["findings"].append(dict(claim="Unsupported late-source assertion",
                                     source_ids=["S2"], as_of="2026-01-31"))
        before = copy.deepcopy(data)
        out = normalize_research(data)
        self.assertEqual(out["status"], "partial")
        self.assertEqual([x["id"] for x in out["sources"]], ["S1"])
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out["findings"][0]["source_ids"], ["S1"])
        self.assertEqual(before, data)
        self.assertTrue(all(x["redistribution_clearance"] == "not_established"
                            for x in out["sources"]))


if __name__ == "__main__":
    unittest.main()
