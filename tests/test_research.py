"""SYNTHETIC_FIXTURE — generated data only, never a factual investment source."""
import copy
import unittest

from proofinvest.research import normalize_research


SYNTHETIC_FIXTURE = {
    "target_name": "Synthetic Example Corp",
    "target_id": "EXAMPLE-001",
    "as_of": "2026-01-31",
    "sources": [{
        "id": "S1",
        "title": "SYNTHETIC_FIXTURE quarterly sample",
        "url": "https://example.org/research/sample",
        "published_at": "2026-01-10",
        "collected_at": "2026-01-11T09:00:00+09:00",
        "license": "SYNTHETIC_FIXTURE",
    }],
    "findings": [{
        "claim": "Synthetic example statement (not a real-world assertion).",
        "source_ids": ["S1"],
        "as_of": "2026-01-31",
    }],
}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.data = copy.deepcopy(SYNTHETIC_FIXTURE)

    def test_valid_linked_finding(self):
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["findings"][0]["source_ids"], ["S1"])
        self.assertEqual(result["sources"][0]["id"], "S1")

    def test_pure_deterministic_and_input_unchanged(self):
        before = copy.deepcopy(self.data)
        self.assertEqual(normalize_research(self.data), normalize_research(self.data))
        self.assertEqual(self.data, before)

    def test_empty_sources_and_findings_are_unavailable(self):
        self.data["sources"] = []
        self.data["findings"] = []
        self.assertEqual(normalize_research(self.data)["status"], "unavailable")

    def test_http_url_fails_closed(self):
        self.data["sources"][0]["url"] = "http://example.org/plain"
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertIn("invalid_source_url", self._codes(result))

    def test_empty_url_fails_closed(self):
        self.data["sources"][0]["url"] = " "
        self.assertEqual(normalize_research(self.data)["status"], "unavailable")

    def test_unregistered_source_id_rejects_finding(self):
        self.data["findings"][0]["source_ids"].append("NONEXISTENT")
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["findings"], [])
        self.assertIn("unavailable_evidence", self._codes(result))

    def test_divergent_duplicate_id_poisoned(self):
        conflicting = dict(self.data["sources"][0], url="https://other.example.org/page")
        self.data["sources"].append(conflicting)
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertIn("source_id_conflict", self._codes(result))

    def test_identical_duplicate_accepted_once(self):
        self.data["sources"].append(dict(self.data["sources"][0]))
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["sources"]), 1)

    def test_distinct_ids_same_url_are_not_two_evidence_sources(self):
        alias = dict(self.data["sources"][0], id="S2")
        self.data["sources"].append(alias)
        self.data["findings"][0]["source_ids"] = ["S1", "S2"]
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["findings"], [])
        self.assertIn("duplicate_source_url", self._codes(result))
        self.assertIn("unavailable_evidence", self._codes(result))

    def test_distinct_ids_same_url_with_conflicting_license_are_rejected(self):
        alias = dict(self.data["sources"][0], id="S2", license="Different rights claim")
        self.data["sources"].append(alias)
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertIn("duplicate_source_url", self._codes(result))

    def test_distinct_sources_remain_valid_and_order_independent(self):
        original = copy.deepcopy(self.data)
        other = dict(original["sources"][0], id="S2",
                     url="https://example.org/research/independent-source")
        original["sources"].append(other)
        original["findings"][0]["source_ids"] = ["S1", "S2"]
        first = normalize_research(original)
        self.assertEqual(first["status"], "success")
        self.assertEqual({s["id"] for s in first["sources"]}, {"S1", "S2"})
        second = copy.deepcopy(original)
        second["sources"].reverse()
        reversed_result = normalize_research(second)
        self.assertEqual(reversed_result["status"], "success")
        self.assertEqual({s["id"] for s in reversed_result["sources"]}, {"S1", "S2"})

    def test_duplicate_source_does_not_poison_independent_finding(self):
        original = copy.deepcopy(self.data)
        original["sources"].append(dict(original["sources"][0], id="S2"))
        original["sources"].append(dict(original["sources"][0], id="S3",
                                        url="https://example.org/research/independent"))
        original["findings"] = [
            dict(claim="Alias-dependent claim", source_ids=["S1"], as_of="2026-01-31"),
            dict(claim="Independent claim", source_ids=["S3"], as_of="2026-01-31"),
        ]
        result = normalize_research(original)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([s["id"] for s in result["sources"]], ["S3"])
        self.assertEqual([f["claim"] for f in result["findings"]], ["Independent claim"])
        self.assertIn("duplicate_source_url", self._codes(result))

    def test_future_published_source_excluded(self):
        self.data["sources"][0]["published_at"] = "2026-02-01"
        self.data["sources"][0]["collected_at"] = "2026-02-02"
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("future_published", self._codes(result))

    def test_finding_cannot_precede_source(self):
        self.data["findings"][0]["as_of"] = "2026-01-01"
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("finding_precedes_source", self._codes(result))

    def test_future_finding_as_of_excluded(self):
        self.data["findings"][0]["as_of"] = "2026-02-01"
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("invalid_finding_date", self._codes(result))

    def test_empty_claim_is_never_supported(self):
        self.data["findings"][0]["claim"] = "   "
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("invalid_claim", self._codes(result))

    def test_mixed_valid_and_invalid_findings_is_partial(self):
        self.data["findings"].append({
            "claim": "Uncited, fabricated assertion",
            "source_ids": ["MISSING"],
            "as_of": "2026-01-31",
        })
        result = normalize_research(self.data)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["findings"]), 1)

    def test_license_label_does_not_grant_republication(self):
        for label in ("SYNTHETIC_FIXTURE", "CC-BY-4.0", "public domain", "OpenDART"):
            with self.subTest(label=label):
                data = copy.deepcopy(self.data)
                data["sources"][0]["license"] = label
                result = normalize_research(data)
                self.assertEqual(result["status"], "success")
                source = result["sources"][0]
                self.assertEqual(source["license"], label)
                self.assertEqual(source["rights_review_status"], "not_verified")
                self.assertEqual(source["redistribution_clearance"], "not_established")

    def test_one_source_rights_status_does_not_certify_another(self):
        data = copy.deepcopy(self.data)
        extra = dict(data["sources"][0], id="S2", license="unknown",
                     url="https://example.org/research/independent-rights-source")
        data["sources"].append(extra)
        data["findings"][0]["source_ids"] = ["S1", "S2"]
        result = normalize_research(data)
        self.assertEqual(result["status"], "success")
        self.assertEqual({x["id"] for x in result["sources"]}, {"S1", "S2"})
        self.assertTrue(all(
            x["redistribution_clearance"] == "not_established"
            for x in result["sources"]
        ))

    def test_missing_license_rejects_evidence(self):
        self.data["sources"][0]["license"] = ""
        self.assertEqual(normalize_research(self.data)["status"], "unavailable")

    def test_missing_target_or_as_of_fail_closed(self):
        self.data["target_name"] = ""
        self.assertEqual(normalize_research(self.data)["status"], "unavailable")
        self.data["target_name"] = "Synthetic Example Corp"
        self.data["as_of"] = "2026-02-30"
        self.assertEqual(normalize_research(self.data)["status"], "unavailable")

    def test_malformed_collections_fail_closed(self):
        self.data["sources"] = {"S1": self.data["sources"][0]}
        self.assertIn("invalid_collection", self._codes(normalize_research(self.data)))

    def test_no_reference_ids_rejects_finding(self):
        self.data["findings"][0]["source_ids"] = []
        self.assertIn("missing_source_ids", self._codes(normalize_research(self.data)))

    @staticmethod
    def _codes(result):
        return [warning["code"] for warning in result["warnings"]]


if __name__ == "__main__":
    unittest.main()
