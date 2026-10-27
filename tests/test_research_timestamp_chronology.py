"""Timezone-aware source publication/collection order is never reversed."""
import copy
import unittest

from proofinvest.research import normalize_research


def fixture():
    return {
        "target_name": "Synthetic Corp", "target_id": "SYNTHETIC-001",
        "as_of": "2026-01-31",
        "sources": [{
            "id": "S1", "title": "Synthetic publication",
            "url": "https://example.org/research/one",
            "published_at": "2026-01-10T18:00:00+09:00",
            "collected_at": "2026-01-10T18:00:01+09:00",
            "license": "not_verified",
        }],
        "findings": [{
            "claim": "Hypothetical sample claim",
            "source_ids": ["S1"], "as_of": "2026-01-31",
        }],
    }


class IntradayResearchChronologyTests(unittest.TestCase):
    @staticmethod
    def warnings(result):
        return [x["code"] for x in result["warnings"]]

    def test_earlier_same_day_collection_is_rejected(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-10T17:59:59+09:00"
        result = normalize_research(data)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["findings"], [])
        self.assertIn("invalid_source_date", self.warnings(result))

    def test_mixed_offsets_use_absolute_instant_not_local_clock(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-10T08:59:59Z"
        # Published at 09:00 UTC, so 08:59:59Z is one second too early.
        self.assertEqual(normalize_research(data)["status"], "unavailable")

    def test_same_instant_different_offsets_is_valid(self):
        data = fixture()
        data["sources"][0]["collected_at"] = "2026-01-10T09:00:00Z"
        self.assertEqual(normalize_research(data)["status"], "success")

    def test_explicit_offsets_accept_valid_cross_calendar_date_order(self):
        data = fixture()
        # Published at Jan 10 10:30 UTC, collected Jan 10 23:00 UTC.
        # Local dates are reversed due to +14:00, not true chronology.
        data["sources"][0]["published_at"] = "2026-01-11T00:30:00+14:00"
        data["sources"][0]["collected_at"] = "2026-01-10T23:00:00Z"
        out = normalize_research(data)
        self.assertEqual(out["status"], "success")
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(len(out["sources"]), 1)

    def test_explicit_offsets_still_reject_true_reversed_instants(self):
        data = fixture()
        # Published at Jan 11 11:30 UTC; collection at 07:00 UTC is early,
        # despite collected local calendar day being later than published.
        data["sources"][0]["published_at"] = "2026-01-10T23:30:00-12:00"
        data["sources"][0]["collected_at"] = "2026-01-11T07:00:00Z"
        out = normalize_research(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("invalid_source_date", self.warnings(out))

    def test_mixed_precision_keeps_conservative_day_ordering(self):
        data = fixture()
        data["sources"][0]["published_at"] = "2026-01-11"
        data["sources"][0]["collected_at"] = "2026-01-10T23:00:00Z"
        out = normalize_research(data)
        self.assertEqual(out["status"], "unavailable")
        self.assertIn("invalid_source_date", self.warnings(out))

    def test_day_precision_legacy_dates_remain_valid(self):
        data = fixture()
        data["sources"][0]["published_at"] = "2026-01-10"
        data["sources"][0]["collected_at"] = "2026-01-10"
        self.assertEqual(normalize_research(data)["status"], "success")
        data["sources"][0]["collected_at"] = "2026-01-10T05:00:00Z"
        self.assertEqual(normalize_research(data)["status"], "success")

    def test_invalid_source_does_not_poison_independent_source(self):
        data = fixture()
        bad = copy.deepcopy(data["sources"][0])
        bad["id"] = "S2"
        bad["url"] = "https://example.org/research/two"
        bad["collected_at"] = "2026-01-10T17:59:59+09:00"
        data["sources"].append(bad)
        data["findings"].append({
            "claim": "Unsupported bad-timestamp claim",
            "source_ids": ["S2"], "as_of": "2026-01-31",
        })
        before = copy.deepcopy(data)
        result = normalize_research(data)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([s["id"] for s in result["sources"]], ["S1"])
        self.assertEqual([f["source_ids"] for f in result["findings"]], [["S1"]])
        self.assertIn("invalid_source_date", self.warnings(result))
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
