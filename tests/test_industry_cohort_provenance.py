"""P161 offline evidence-role separation: SEC issuer, peers, sector."""
from __future__ import annotations

import unittest

from proofinvest.industry_cohort_provenance import require_disjoint_cohort_evidence


def cohort():
    rows = [
        {"id": "target-old", "sha256": "a" * 64},
        {"id": "target-new", "sha256": "b" * 64},
        {"id": "peer-old", "sha256": "c" * 64},
        {"id": "peer-new", "sha256": "d" * 64},
        {"id": "sector-old", "sha256": "e" * 64},
        {"id": "sector-new", "sha256": "f" * 64},
    ]
    target = {"cik": "0001045810",
              "source_ids": ["target-old", "target-new"]}
    peers = [{"cik": "0000320193",
              "source_ids": ["peer-old", "peer-new"]}]
    return rows, target, peers, ["sector-old", "sector-new"]


class CohortSourceProvenanceTests(unittest.TestCase):
    def test_distinct_company_and_sector_sources_pass_as_unverified(self):
        rows, target, peers, sector = cohort()
        out = require_disjoint_cohort_evidence(
            rows, target=target, peers=peers, industry_source_ids=sector)
        self.assertEqual(out["status"], "DISJOINT_SOURCE_CLAIMS_ONLY_UNVERIFIED")
        self.assertEqual(out["peer_count"], 1)
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["rights_verified"])

    def test_peer_reusing_target_source_id_rejected(self):
        rows, target, peers, sector = cohort()
        peers[0]["source_ids"][0] = "target-old"
        with self.assertRaisesRegex(ValueError, "CROSS_ISSUER"):
            require_disjoint_cohort_evidence(
                rows, target=target, peers=peers, industry_source_ids=sector)

    def test_distinct_ids_same_source_hash_rejected(self):
        rows, target, peers, sector = cohort()
        rows[2]["sha256"] = rows[0]["sha256"]
        with self.assertRaisesRegex(ValueError, "CROSS_ISSUER"):
            require_disjoint_cohort_evidence(
                rows, target=target, peers=peers, industry_source_ids=sector)

    def test_sector_cannot_reuse_peer_data(self):
        rows, target, peers, sector = cohort()
        rows[-1]["sha256"] = rows[3]["sha256"]
        with self.assertRaisesRegex(ValueError, "CROSS_ISSUER"):
            require_disjoint_cohort_evidence(
                rows, target=target, peers=peers, industry_source_ids=sector)

    def test_two_years_one_company_may_use_same_10k_hash(self):
        rows, target, peers, sector = cohort()
        rows[1]["sha256"] = rows[0]["sha256"]
        out = require_disjoint_cohort_evidence(
            rows, target=target, peers=peers, industry_source_ids=sector)
        self.assertEqual(out["peer_count"], 1)

    def test_duplicate_peer_cik_or_unknown_source_fails(self):
        rows, target, peers, sector = cohort()
        peers[0]["cik"] = target["cik"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CIK"):
            require_disjoint_cohort_evidence(
                rows, target=target, peers=peers, industry_source_ids=sector)
        rows, target, peers, sector = cohort()
        peers[0]["source_ids"][1] = "unknown"
        with self.assertRaisesRegex(ValueError, "ROLE_INVALID"):
            require_disjoint_cohort_evidence(
                rows, target=target, peers=peers, industry_source_ids=sector)


if __name__ == "__main__":
    unittest.main()
