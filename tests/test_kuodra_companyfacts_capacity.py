"""P39: realistic bounded whole-issuer SEC CompanyFacts support without live calls.

A larger JSON document is synthetic, not a real SEC transport or provenance
claim. Tests exercise the same 24 MB cap in local UI, 3-source transport and
explicit retention ZIP, preserving <=8 MB submissions and history limits.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from disclosure_lightning.core import MAX_JSON_BYTES
from proofinvest import sec_three_source as transport
from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_submissions, synthetic_companyfacts,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML, PHRASE
from proofinvest.kuodra_local_workspace import preview_uploaded_triplet, review_uploaded_triplet
from proofinvest.local_sec_packet import _MAX_FILE_BYTES, _json_object
from proofinvest.sec_capture_bundle import (
    _MAX_ZIP_BYTES, _PARTS, save_local_capture_bundle, verify_local_capture_bundle,
)
from tests.test_sec_three_source import _Opener, _MockResp, FIXED, ARGS


def big_companyfacts() -> bytes:
    facts = synthetic_companyfacts()
    # SEC's combined CompanyFacts size includes hundreds of other concepts;
    # the deliberately unused field merely produces an over-8 MB byte shape.
    facts["entityName"] = "synthetic-boundary-" + "X" * 8_001_000
    raw = json.dumps(facts, separators=(",", ":")).encode()
    assert 8_000_000 < len(raw) < _MAX_FILE_BYTES
    return raw


class CompanyFactsCapacityTests(unittest.TestCase):
    def test_caps_are_unified_without_expanding_submissions_or_originals(self):
        self.assertEqual(_MAX_FILE_BYTES, 24_000_000)
        self.assertEqual(transport._MAX_FACTS, _MAX_FILE_BYTES)
        self.assertEqual(dict((name, limit) for _, name, limit in _PARTS)[
            "companyfacts.json"
        ], _MAX_FILE_BYTES)
        self.assertEqual(
            _MAX_ZIP_BYTES, MAX_JSON_BYTES + _MAX_FILE_BYTES
            + 25_000_000 + 100_000,
        )
        self.assertLess(MAX_JSON_BYTES, _MAX_FILE_BYTES)

    def test_large_local_three_file_preview_guard_and_originals_not_retained(self):
        raw = {
            "submissions": synthetic_submissions(),
            "companyfacts": big_companyfacts(),
            "original_filing": SYNTHETIC_HTML,
        }
        request = {
            "cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
            "as_of": AS_OF, "collected_at": COLLECTED_AT,
            "current_end": "2025-09-30", "prior_end": "2024-09-30",
            "needle": PHRASE, "claimed_growth_pct": "100.00",
        }
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NEVER_CALL_SEC")) as network:
            preview = preview_uploaded_triplet(raw, request)
            report, html = review_uploaded_triplet(
                raw, request, expected_preview=preview, consent=True,
            )
        network.assert_not_called()
        self.assertEqual(report["verification"]["growth_pct"], "100.00")
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertTrue(report["operator_reviewed_source_digests_matched"])
        self.assertEqual(
            report["source"]["companyfacts_sha256"],
            hashlib.sha256(raw["companyfacts"]).hexdigest(),
        )
        self.assertIn(b"KUODRA", html)
        self.assertFalse(report["limits"]["external_source_authenticated"])

    def test_large_transport_pinned_zip_and_integrity_offline_mock(self):
        import zipfile
        raw = big_companyfacts()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "companyfacts-large.zip"
            with (patch.object(transport, "_utcnow", return_value=FIXED),
                  patch.object(transport.time, "sleep"),
                  patch.object(transport, "fetch_submissions",
                               return_value=synthetic_submissions()) as submissions,
                  patch.object(transport, "fetch_original",
                               return_value=(SYNTHETIC_HTML, "text/html")) as original,
                  patch.object(transport.urllib.request, "build_opener",
                               return_value=_Opener(raw)) as opener):
                result = transport.run_sec_three_source_review(
                    **ARGS, output_bundle=path, acknowledge_local_retention=True,
                )
            self.assertEqual(result["status"], "three_sec_https_responses_captured_unverified")
            self.assertEqual(result["http_requests_attempted"], 3)
            self.assertEqual((submissions.call_count, opener.call_count,
                              original.call_count), (1, 1, 1))
            self.assertTrue(path.is_file())
            verified = verify_local_capture_bundle(path)
            self.assertEqual(verified["status"], "bundle_integrity_pass_origin_unverified")
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read("companyfacts.json"), raw)
            self.assertEqual(
                result["raw_response_sha256"]["companyfacts"],
                hashlib.sha256(raw).hexdigest(),
            )
            self.assertFalse(result["source_authenticated"])
            self.assertFalse(verified["sec_origin_authenticated"])

    def test_transport_rejects_over_cap_header_before_read_or_retention(self):
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json"
        class HeaderTooBig:
            def open(self, req, timeout):
                return _MockResp(url, b"{}", length=str(_MAX_FILE_BYTES+1))
        with patch.object(transport.urllib.request, "build_opener",
                          return_value=HeaderTooBig()) as opener:
            with self.assertRaisesRegex(ValueError, "COMPANYFACTS_SIZE"):
                transport._fetch_companyfacts(SYNTHETIC_CIK, ARGS["user_agent"])
        self.assertEqual(opener.call_count, 1)
        with self.assertRaisesRegex(ValueError, "OVERSIZED"):
            _json_object(b"{}", limit=1)


if __name__ == "__main__":
    unittest.main()
