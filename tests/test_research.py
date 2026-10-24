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
