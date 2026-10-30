"""KUODRA macro metadata, source-span and as-of fail-closed tests."""
from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from proofinvest.kuodra_macro import CANDIDATES, review_macro_context

RAW = b"Synthetic SEC HTML: the issuer has material USD sales exposure in this filing."
QUOTE = "material USD sales exposure"
START = RAW.index(QUOTE.encode("utf-8"))


def exposure(sid="SP500"):
    return {
        "series_id": sid, "start_byte": START,
        "end_byte_exclusive": START + len(QUOTE.encode("utf-8")),
        "literal": QUOTE, "rationale": "Currency translation and index demand context.",
    }


def observation(sid="SP500"):
    return {
        "series_id": sid,
        "benchmark": "Index benchmark (caller assertion only)",
        "unit": CANDIDATES[sid],
        "value": "123.45",
        "period_end": "2025-09-30",
        "released_at": "2025-10-15T09:00:00+00:00",
        "vintage_at": "2025-10-15T09:00:01+00:00",
        "collected_at": "2025-10-15T09:00:02+00:00",
        "source_url": "https://example.org/economic-index",
        "payload_sha256": hashlib.sha256(b"synthetic observations").hexdigest(),
        "rights_review": "LOCAL_ANALYSIS_PERMITTED_ATTESTED",
        "rights_basis_url": "https://example.org/terms",
        "rights_note": "Caller says local research is allowed; not independently proven.",
    }


def review(exposures=None, observations=None, raw=RAW):
    return review_macro_context(
        original_filing=raw, issuer_cik="0000000001", as_of="2025-10-16",
        exposures=[exposure()] if exposures is None else exposures,
        observations=[observation()] if observations is None else observations,
    )


def state(result, sid="SP500"):
    return next(x for x in result["candidate_checks"] if x["series_id"] == sid)


class KuodraMacroTests(unittest.TestCase):
    def test_valid_local_data_anchors_raw_bytes_but_never_certifies_source(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("NO_NETWORK")) as client:
            result = review()
        client.assert_not_called()
        self.assertEqual(len(CANDIDATES), 11)
        self.assertEqual(len(result["candidate_checks"]), 11)
        self.assertEqual(state(result)["status"], "METADATA_ELIGIBLE_UNVERIFIED")
        self.assertEqual(result["cards"][0]["value"], "123.45")
        for k in ("source_authenticated", "source_rights_verified", "live_api_called",
                  "guard_policy_modified", "trade_executed"):
            self.assertIs(result[k], False)

    def test_wrong_issuer_filing_span_is_not_accepted(self):
        bad = exposure()
        bad["literal"] = "invented claim not in source"
        self.assertEqual(state(review(exposures=[bad]))["reason_code"],
                         "NO_EXACT_FILING_EXPOSURE")

    def test_unattested_rights_fails_closed(self):
        row = observation()
        row["rights_review"] = "PENDING"
        self.assertEqual(state(review(observations=[row]))["reason_code"],
                         "LOCAL_ANALYSIS_RIGHTS_NOT_ATTESTED")

    def test_unit_mismatch_fails_closed(self):
        row = observation("US_CPI_YOY")
        row["unit"] = "index_points"
        self.assertEqual(state(review(exposures=[exposure("US_CPI_YOY")],
                                      observations=[row]), "US_CPI_YOY")["reason_code"],
                         "UNIT_OR_BENCHMARK_MISMATCH")

    def test_future_vintage_and_collection_rejected(self):
        for key in ("vintage_at", "collected_at", "released_at"):
            with self.subTest(key=key):
                row = observation()
                row[key] = "2025-10-17T01:00:00Z"
                self.assertEqual(state(review(observations=[row]))["reason_code"],
                                 "FUTURE_OR_OUT_OF_ORDER_VINTAGE")

    def test_midnight_timezone_offset_does_not_backdate(self):
        row = observation()
        row.update(released_at="2025-10-16T23:30:00-12:00",
                   vintage_at="2025-10-17T00:00:00-12:00",
                   collected_at="2025-10-17T01:00:00-12:00")
        self.assertEqual(state(review(observations=[row]))["reason_code"],
                         "FUTURE_OR_OUT_OF_ORDER_VINTAGE")

    def test_naive_timestamp_rejected(self):
        row = observation()
        row["collected_at"] = "2025-10-15T09:00:02"
        self.assertEqual(state(review(observations=[row]))["reason_code"],
                         "MISSING_OR_NAIVE_CHRONOLOGY")

    def test_duplicate_vintage_not_cherry_picked(self):
        self.assertEqual(state(review(observations=[observation(), observation()]))[
            "reason_code"], "AMBIGUOUS_OBSERVATION_VINTAGES")

    def test_duplicate_exposure_not_cherry_picked(self):
        self.assertEqual(state(review(exposures=[exposure(), exposure()]))[
            "reason_code"], "DUPLICATE_EXPOSURE")

    def test_injected_or_floating_point_value_rejected(self):
        for value in (100.0, "NaN", "1e5", "100; DROP TABLE", "Infinity"):
            with self.subTest(value=value):
                row = observation()
                row["value"] = value
                self.assertEqual(state(review(observations=[row]))[
                    "reason_code"], "INVALID_DECIMAL_VALUE")

    def test_missing_observations_return_all_not_checked(self):
        result = review(observations=[])
        self.assertFalse(result["cards"])
        self.assertEqual(state(result)["reason_code"], "NO_LOCAL_OBSERVATION")

    def test_bounded_max_three_cards(self):
        ids = list(CANDIDATES)[:5]
        result = review(exposures=[exposure(x) for x in ids],
                        observations=[observation(x) for x in ids])
        self.assertEqual(len(result["cards"]), 3)
        self.assertEqual(state(result, ids[3])["reason_code"], "CARD_LIMIT")
        self.assertEqual(state(result, ids[4])["reason_code"], "CARD_LIMIT")

    def test_invalid_url_or_digest_rejected(self):
        row = observation()
        row["source_url"] = "https://user:password@example.com/secret"
        self.assertEqual(state(review(observations=[row]))["reason_code"],
                         "SOURCE_OR_RIGHTS_LINK_INVALID")
        row = observation()
        row["payload_sha256"] = "not-a-sha"
        self.assertEqual(state(review(observations=[row]))["reason_code"],
                         "SOURCE_PAYLOAD_DIGEST_MISSING")

    def test_invalid_outer_contract_fails_before_analysis(self):
        with self.assertRaisesRegex(ValueError, "MACRO_CONTEXT_INVALID_INPUT"):
            review_macro_context(original_filing=RAW, issuer_cik="0000000001",
                                 as_of="2025-10-16", exposures=[], observations=[{}] * 33)


if __name__ == "__main__":
    unittest.main()
