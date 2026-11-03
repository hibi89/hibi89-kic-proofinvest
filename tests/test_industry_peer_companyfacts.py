"""Offline CompanyFacts -> Engine C peer evidence checks (synthetic only)."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.industry_peer_companyfacts import bind_peer_companyfacts_to_industry
from proofinvest.sec_companyfacts import TAG
from tests.test_industry_vision import fixture


PEER_CIK = "0000000007"
PEER_ACCESSION = "0000000007-26-000001"


def peer_input():
    data = fixture()
    peer_fact = {
        "cik": 7,
        "entityName": "SYNTHETIC_PEER",
        "facts": {"us-gaap": {TAG: {"units": {"USD": [
            {"accn": PEER_ACCESSION, "form": "10-K",
             "start": "2025-01-01", "end": "2025-12-31",
             "filed": "2026-02-01", "val": 130},
            {"accn": PEER_ACCESSION, "form": "10-K",
             "start": "2024-01-01", "end": "2024-12-31",
             "filed": "2026-02-01", "val": 100},
        ]}}}},
    }
    raw = json.dumps(peer_fact, sort_keys=True).encode()
    digest = sha256(raw).hexdigest()
    for s in data["sources"]:
        if s["id"] in ("peer-old", "peer-now"):
            s["url"] = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000007.json"
            s["sha256"] = digest
            s["published_at"] = "2026-02-01"
    return data, raw


def check(data, raw, *, cik=PEER_CIK, accession=PEER_ACCESSION):
    return bind_peer_companyfacts_to_industry(
        json.dumps(data).encode(),
        peer_sources=[(cik, accession, raw)],
    )


class PeerCompanyFactsTests(unittest.TestCase):
    def test_real_parser_and_offline_peer_growth_pass_without_authentication(self):
        data, raw = peer_input()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("FORBID_SEC_API")) as network:
            out = check(data, raw)
        network.assert_not_called()
        self.assertEqual(out["peer_count"], 1)
        self.assertEqual(out["peer_records"][0]["growth_pct"], "30.00")
        self.assertEqual(out["peer_records"][0]["companyfacts_sha256"],
                         sha256(raw).hexdigest())
        self.assertEqual(out["status"],
                         "local_peer_values_hash_matched_origin_unverified")
        self.assertFalse(out["source_authenticated"])
        self.assertFalse(out["source_rights_verified"])
        self.assertFalse(out["live_sec_called"])
        self.assertFalse(out["audit_written"])

    def test_revenue_mismatch_blocks_without_mutating_inputs(self):
        data, raw = peer_input()
        original = deepcopy(data)
        data["peers"][0]["current_revenue_usd"] = "131"
        with self.assertRaisesRegex(ValueError, "PEER_FACTS_REVENUE_CONFLICT"):
            check(data, raw)
        self.assertEqual(original["sources"], data["sources"])

    def test_hash_source_url_and_filing_date_each_bound_to_raw_bytes(self):
        for field in ("sha256", "url", "published_at"):
            data, raw = peer_input()
            src = next(s for s in data["sources"] if s["id"] == "peer-now")
            src[field] = {
                "sha256": "9" * 64,
                "url": "https://www.sec.gov/Archives/wrong-source",
                "published_at": "2026-02-02",
            }[field]
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "PEER_FACTS_SOURCE_HASH_OR_DATE_MISMATCH"):
                check(data, raw)

    def test_peer_digest_colliding_with_target_is_rejected_before_byte_binding(self):
        # A forged peer digest that reuses a different issuer's source is
        # a cross-issuer collision, not merely a local peer-byte mismatch.
        data, raw = peer_input()
        src = next(s for s in data["sources"] if s["id"] == "peer-now")
        src["sha256"] = "a" * 64  # target-old from synthetic fixture
        with self.assertRaisesRegex(
                ValueError, "COHORT_CROSS_ISSUER_SOURCE_COLLISION"):
            check(data, raw)

    def test_no_forged_peer_cik_or_accession(self):
        data, raw = peer_input()
        for cik, accession in (
            ("0000000008", PEER_ACCESSION),
            (PEER_CIK, "0000000008-26-000001"),
            ("0000320193", PEER_ACCESSION),
        ):
            with self.subTest(cik=cik, accession=accession), self.assertRaises(ValueError):
                check(data, raw, cik=cik, accession=accession)

    def test_future_filing_refused(self):
        data, raw = peer_input()
        obj = json.loads(raw)
        for row in obj["facts"]["us-gaap"][TAG]["units"]["USD"]:
            row["filed"] = "2026-11-01"
        changed = json.dumps(obj, sort_keys=True).encode()
        new_hash = sha256(changed).hexdigest()
        for src in data["sources"]:
            if src["id"] in ("peer-old", "peer-now"):
                src["sha256"] = new_hash
        with self.assertRaisesRegex(
                ValueError, "PEER_FACTS_FINANCIAL_UNAVAILABLE_OR_UNTRUSTED"):
            check(data, changed)

    def test_duplicate_and_missing_peer_evidence_block(self):
        data, raw = peer_input()
        original = json.dumps(data).encode()
        for sources in ([], [(PEER_CIK, PEER_ACCESSION, raw)] * 2):
            with self.subTest(n=len(sources)), self.assertRaises(ValueError):
                bind_peer_companyfacts_to_industry(original, peer_sources=sources)

    def test_duplicate_json_keys_rejected(self):
        data, raw = peer_input()
        poisoned = raw.replace(b'"cik": 7', b'"cik": 7, "cik": 7')
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            check(data, poisoned)


if __name__ == "__main__":
    unittest.main()
