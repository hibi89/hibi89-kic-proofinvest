"""P34 local GUI data path: in-memory input, explicit preview, disposable Guard."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_local_workspace import (
    preview_uploaded_triplet, review_uploaded_triplet,
)
from proofinvest.kuodra_local_workspace_ui import local_workspace_enabled
from proofinvest.guard_audit import GuardAuditStore


class FakeStreamlit:
    def __init__(self, address):
        self.address = address
    def get_option(self, name):
        if name != "server.address":
            raise KeyError(name)
        return self.address


class LocalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "submissions": synthetic_submissions(),
            "companyfacts": json.dumps(synthetic_companyfacts()).encode(),
            "original_filing": SYNTHETIC_HTML,
        }
        self.req = {
            "cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
            "as_of": AS_OF, "collected_at": COLLECTED_AT,
            "current_end": "2025-09-30", "prior_end": "2024-09-30",
            "needle": PHRASE, "claimed_growth_pct": "100.00",
        }

    def test_local_ui_disabled_by_default_and_on_public_bind(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KUODRA_ENABLE_LOCAL_SOURCE_UI", None)
            self.assertFalse(local_workspace_enabled(FakeStreamlit("127.0.0.1")))
        with patch.dict(os.environ, {"KUODRA_ENABLE_LOCAL_SOURCE_UI": "1"}):
            for address in ("", "0.0.0.0", "::", "192.168.1.10"):
                self.assertFalse(local_workspace_enabled(FakeStreamlit(address)))
            self.assertTrue(local_workspace_enabled(FakeStreamlit("127.0.0.1")))
            self.assertTrue(local_workspace_enabled(FakeStreamlit("localhost")))

    def test_preview_to_guard_html_without_original_retention_or_http(self):
        originals = {k: bytes(v) for k, v in self.raw.items()}
        with tempfile.TemporaryDirectory() as tmp:
            # Only explicit test-owned output dir used to detect persistence.
            before = tuple(Path(tmp).iterdir())
            with patch("urllib.request.build_opener",
                       side_effect=AssertionError("NO_NETWORK")) as remote:
                preview = preview_uploaded_triplet(self.raw, self.req)
                self.assertEqual(preview["status"],
                                 "requires_explicit_ephemeral_audit_consent")
                self.assertFalse(preview["audit_written"])
                self.assertNotIn(PHRASE, json.dumps(preview))
                report, html = review_uploaded_triplet(
                    self.raw, self.req, expected_preview=preview, consent=True,
                )
            remote.assert_not_called()
            self.assertEqual(before, tuple(Path(tmp).iterdir()))
        self.assertEqual(originals, self.raw)
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertTrue(report["audit_chain_valid"])
        self.assertTrue(report["operator_reviewed_source_digests_matched"])
        self.assertIn(b"KUODRA", html) if b"KUODRA" in html else self.assertIn(b"SEC", html)
        self.assertNotIn(str(Path.home()).encode(), html)
        self.assertFalse(report["limits"]["live_api_called"])

    def test_readonly_memory_discovery_suggests_real_verified_period_pair(self):
        from proofinvest.kuodra_local_workspace import discover_uploaded_periods
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_HTTP")) as network, patch(
            "proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
            side_effect=AssertionError("NO_PERSISTENT_AUDIT")
        ) as guard:
            found = discover_uploaded_periods(
                self.raw, cik=self.req["cik"],
                accession=self.req["accession"], as_of=self.req["as_of"],
                collected_at=self.req["collected_at"],
            )
        network.assert_not_called()
        guard.assert_not_called()
        self.assertEqual(found["status"], "periods_require_operator_selection")
        self.assertEqual(found["period_candidates"][0]["current_end"], "2025-09-30")
        self.assertEqual(found["period_candidates"][0]["prior_end"], "2024-09-30")
        self.assertEqual(found["local_needle_candidates"], [])
        self.assertFalse(found["original_text_disclosed"])
        self.assertFalse(found["source_authenticated"])
        self.assertFalse(found["audit_written"])
        self.assertNotIn(PHRASE, json.dumps(found))

    def test_explicit_local_text_disclosure_gives_only_bounded_unique_candidates(self):
        from proofinvest.kuodra_local_workspace import discover_uploaded_periods
        found = discover_uploaded_periods(
            self.raw, cik=self.req["cik"],
            accession=self.req["accession"], as_of=self.req["as_of"],
            collected_at=self.req["collected_at"],
            show_local_needle_candidates=True,
        )
        self.assertTrue(found["original_text_disclosed"])
        self.assertGreaterEqual(len(found["local_needle_candidates"]), 1)
        self.assertLessEqual(len(found["local_needle_candidates"]), 5)
        self.assertIn(PHRASE, [x["needle"] for x in found["local_needle_candidates"]])
        self.assertTrue(all(x["source_authenticated"] is False
                            for x in found["local_needle_candidates"]))

    def test_discovery_rejects_changed_issuer_and_false_flag_before_audit(self):
        from proofinvest.kuodra_local_workspace import discover_uploaded_periods
        args = {
            "cik": self.req["cik"], "accession": self.req["accession"],
            "as_of": self.req["as_of"], "collected_at": self.req["collected_at"],
        }
        with self.assertRaisesRegex(ValueError, "CANDIDATES_UNAVAILABLE"):
            discover_uploaded_periods(self.raw, **(args | {"cik": "0000000002"}))
        with self.assertRaisesRegex(ValueError, "FLAG_REQUIRED"):
            discover_uploaded_periods(
                self.raw, **args, show_local_needle_candidates="true",
            )
        with patch("proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
                   side_effect=AssertionError("NO_GUARD")) as guard:
            with self.assertRaises(ValueError):
                discover_uploaded_periods(
                    self.raw | {"companyfacts": b'{"broken":true}'}, **args,
                )
        guard.assert_not_called()

    def test_history_fourth_file_periods_preview_and_guard_report(self):
        from proofinvest.kuodra_local_workspace import discover_uploaded_periods
        from tests.test_kuodra_history import PAGE, data
        base, history = data()
        raw = self.raw | {"submissions": base, "history_page": history}
        req = self.req | {"history_page_name": PAGE}
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_EXTERNAL_NETWORK")) as network:
            found = discover_uploaded_periods(
                raw, cik=req["cik"], accession=req["accession"],
                as_of=req["as_of"], collected_at=req["collected_at"],
                history_page_name=PAGE, show_local_needle_candidates=True,
            )
            preview = preview_uploaded_triplet(raw, req)
            report, html = review_uploaded_triplet(
                raw, req, expected_preview=preview, consent=True,
            )
        network.assert_not_called()
        self.assertEqual(found["period_candidates"][0]["current_end"], req["current_end"])
        self.assertIn("history_page", found["source_sha256"])
        self.assertTrue(found["original_text_disclosed"])
        self.assertEqual(preview["history_page_name"], PAGE)
        self.assertEqual(preview["source_sha256"], found["source_sha256"])
        self.assertEqual(report["source"]["source_index_kind"], "PINNED_HISTORY")
        self.assertTrue(report["operator_reviewed_source_digests_matched"])
        self.assertEqual(report["guard"]["decision"], "HOLD")
        self.assertIn(b"HTML", html)

    def test_history_fourth_file_swap_blocks_before_guard(self):
        from tests.test_kuodra_history import PAGE, data
        base, history = data()
        raw = self.raw | {"submissions": base, "history_page": history}
        req = self.req | {"history_page_name": PAGE}
        preview = preview_uploaded_triplet(raw, req)
        with patch("proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
                   side_effect=AssertionError("NO_WRITES")) as guarded:
            with self.assertRaisesRegex(ValueError, "CHANGED"):
                review_uploaded_triplet(
                    raw | {"history_page": history + b" "}, req,
                    expected_preview=preview, consent=True,
                )
            with self.assertRaisesRegex(ValueError, "CHANGED"):
                review_uploaded_triplet(
                    raw, req | {"history_page_name": "CIK0000000001-submissions-002.json"},
                    expected_preview=preview, consent=True,
                )
            with self.assertRaisesRegex(ValueError, "HISTORY_FILE_AND_NAME"):
                preview_uploaded_triplet(raw, self.req)
        guarded.assert_not_called()

    def test_conflict_claim_is_rejected_not_approved(self):
        req = {**self.req, "claimed_growth_pct": "300.00"}
        prev = preview_uploaded_triplet(self.raw, req)
        report, _ = review_uploaded_triplet(
            self.raw, req, expected_preview=prev, consent=True,
        )
        self.assertEqual(report["verification"]["status"], "conflict")
        self.assertEqual(report["guard"]["decision"], "REJECT")

    def test_guard_denies_without_consent_before_any_audit(self):
        prev = preview_uploaded_triplet(self.raw, self.req)
        with patch("proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
                   side_effect=AssertionError("NO_AUDIT")) as guard:
            with self.assertRaisesRegex(ValueError, "CONSENT"):
                review_uploaded_triplet(
                    self.raw, self.req, expected_preview=prev, consent=False,
                )
        guard.assert_not_called()

    def test_preview_pins_prevent_source_swap_and_request_change(self):
        prev = preview_uploaded_triplet(self.raw, self.req)
        for key in self.raw:
            with self.subTest(source=key):
                tampered = dict(self.raw)
                tampered[key] = tampered[key] + b" "
                with patch("proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
                           side_effect=AssertionError("NO_AUDIT")) as guard:
                    with self.assertRaisesRegex(ValueError, "CHANGED"):
                        review_uploaded_triplet(
                            tampered, self.req, expected_preview=prev, consent=True,
                        )
                guard.assert_not_called()
        changed_request = {**self.req, "current_end": "2025-09-29"}
        with self.assertRaisesRegex(ValueError, "CHANGED"):
            review_uploaded_triplet(self.raw, changed_request,
                                    expected_preview=prev, consent=True)

    def test_rejects_invalid_and_oversized_byte_shapes(self):
        for bad in (
            {"submissions": b"", "companyfacts": self.raw["companyfacts"],
             "original_filing": self.raw["original_filing"]},
            {"submissions": self.raw["submissions"],
             "companyfacts": self.raw["companyfacts"],
             "original_filing": self.raw["original_filing"], "extra": b"abc"},
            {"submissions": str(self.raw["submissions"]),
             "companyfacts": self.raw["companyfacts"],
             "original_filing": self.raw["original_filing"]},
        ):
            with self.subTest(input=str(list(bad))):
                with self.assertRaises(ValueError):
                    preview_uploaded_triplet(bad, self.req)

    def test_no_source_authentication_upgrade_through_preview(self):
        preview = preview_uploaded_triplet(self.raw, self.req)
        altered = {**preview, "source_authenticated": True}
        with patch("proofinvest.kuodra_local_workspace.review_local_sec_with_guard",
                   side_effect=AssertionError("NO_AUDIT")):
            with self.assertRaisesRegex(ValueError, "CHANGED"):
                review_uploaded_triplet(
                    self.raw, self.req, expected_preview=altered, consent=True,
                )


if __name__ == "__main__":
    unittest.main()
