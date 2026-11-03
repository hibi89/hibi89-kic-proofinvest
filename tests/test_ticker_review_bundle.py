"""P171 reproducible all-in-one evidence ZIP, no raw originals or rights grants."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import unittest
from unittest.mock import patch
import zipfile

from proofinvest.ticker_review_bundle import (
    build_review_bundle_bytes, inspect_review_bundle_bytes,
)
from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from proofinvest.local_market_csv_bridge import (
    normalize_market_csv, build_csv_lineage_receipt,
)
from tests.test_ticker_offline_review_builder import payload
from tests.test_local_market_csv_bridge import local_csv


def originals(csv: bool = False):
    p = payload()
    stock_csv = local_csv("NVDA") if csv else None
    ndx_csv = local_csv("NDX", 10000) if csv else None
    source_stock = source_ndx = None
    if csv:
        source_stock = normalize_market_csv(
            stock_csv, symbol="NVDA", as_of=p["as_of"], is_index=False,
        )
        source_ndx = normalize_market_csv(
            ndx_csv, symbol="NDX", as_of=p["as_of"], is_index=True,
        )
        p["stock_raw"] = source_stock["normalized_json"]
        p["index_raw"] = source_ndx["normalized_json"]
    review = build_offline_initial_review(**p)
    assert review["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED", review
    lineage = (build_csv_lineage_receipt(
        stock=source_stock, index=source_ndx,
        packet=review["review_packet"],
        stock_csv_raw=stock_csv, index_csv_raw=ndx_csv,
    ) if csv else None)
    return review, lineage


def repack(parts: dict[str, bytes]):
    # Deliberately reproduce a well-formed ZIP with changed individual bytes.
    obj = BytesIO()
    with zipfile.ZipFile(obj, mode="w") as z:
        for name, data in sorted(parts.items()):
            z.writestr(name, data)
    return obj.getvalue()


class OfflineEvidenceBundleTests(unittest.TestCase):
    def test_complete_json_and_csv_modes_generate_verifiable_bundles(self):
        for csv in (False, True):
            with self.subTest(csv=csv), patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("NO_VENDOR_HTTP"),
            ) as provider:
                review, lineage = originals(csv)
                args = dict(
                    review_packet=review["review_packet"],
                    rights_gap_report=review["source_clearance_report"],
                    csv_lineage=lineage,
                )
                zipped = build_review_bundle_bytes(**args)
                validated = inspect_review_bundle_bytes(zipped)
                self.assertEqual(zipped, build_review_bundle_bytes(**args))
                self.assertLess(len(zipped), 150000)
                self.assertEqual(
                    validated["status"],
                    "INTERNAL_CONTENT_VERIFIED_ORIGIN_RIGHTS_PENDING",
                )
                self.assertEqual(validated["ticker"], "NVDA")
                self.assertEqual(validated["files_verified"], 4 if csv else 3)
                self.assertEqual(validated["guard_policy_preview"], "HOLD")
                self.assertEqual(validated["network_requests"], 0)
                for k in (
                    "source_authenticated", "source_rights_verified",
                    "external_sharing_allowed", "contest_submission_approved",
                    "trade_executed",
                ):
                    self.assertIs(validated[k], False)
                with zipfile.ZipFile(BytesIO(zipped)) as z:
                    names = set(z.namelist())
                    self.assertEqual(names, {
                        "review-packet.json",
                        "source-rights-GAPS.json",
                        "single-ticker-review.html",
                        "manifest.json",
                    } | ({"market-csv-lineage.json"} if csv else set()))
                    for item in z.infolist():
                        self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                    self.assertNotIn(b"Time Series (Daily)", zipped)
                    self.assertNotIn(b"close_observations", zipped)
                    self.assertNotIn(b"symbol,date,close", zipped)
                    self.assertNotIn(b"<script", zipped.lower())
                provider.assert_not_called()

    def test_single_member_corruption_or_extra_original_is_rejected(self):
        reviewed, lineage = originals(True)
        raw = build_review_bundle_bytes(
            review_packet=reviewed["review_packet"],
            rights_gap_report=reviewed["source_clearance_report"],
            csv_lineage=lineage,
        )
        with zipfile.ZipFile(BytesIO(raw)) as z:
            docs = {name: z.read(name) for name in z.namelist()}
        cases = [
            {"single-ticker-review.html": docs["single-ticker-review.html"] + b" "},
            {"review-packet.json": docs["review-packet.json"] + b" "},
            {"source-rights-GAPS.json": b"{}"},
            {"market-csv-lineage.json": docs["market-csv-lineage.json"] + b" "},
            {"original-10k.html": b"<html>PRIVATE ORIGINAL</html>"},
            {"../escape.json": b"secret"},
            {"manifest.json": b"{}"},
        ]
        for changes in cases:
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                inspect_review_bundle_bytes(repack({**docs, **changes}))

    def test_canonical_manifest_cannot_claim_false_release_even_if_resigned(self):
        review, _ = originals()
        raw = build_review_bundle_bytes(
            review_packet=review["review_packet"],
            rights_gap_report=review["source_clearance_report"],
        )
        with zipfile.ZipFile(BytesIO(raw)) as z:
            docs = {name: z.read(name) for name in z.namelist()}
        for name in ("source_rights_verified", "external_sharing_allowed",
                     "contest_submission_approved", "source_authenticated",
                     "trade_executed"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                mutated = json.loads(docs["manifest.json"])
                mutated[name] = True
                mutated.pop("manifest_sha256")
                enc = lambda o: (
                    json.dumps(o, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False) + "\n").encode()
                mutated["manifest_sha256"] = sha256(enc(mutated)).hexdigest()
                inspect_review_bundle_bytes(repack({
                    **docs, "manifest.json": enc(mutated),
                }))

    def test_no_zip_traversal_suid_symlink_unknown_compression_and_large_input(self):
        review, _ = originals()
        raw = build_review_bundle_bytes(
            review_packet=review["review_packet"],
            rights_gap_report=review["source_clearance_report"],
        )
        for bad in (b"{}", b"PK", raw + b"x" * 150001):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                inspect_review_bundle_bytes(bad)
        with self.assertRaises(ValueError):
            build_review_bundle_bytes(
                review_packet=review["review_packet"] + b" ",
                rights_gap_report=review["source_clearance_report"],
            )

    def test_zip_no_user_side_effect_or_network_before_explicit_click(self):
        review, lineage = originals(True)
        with (
            patch("proofinvest.ticker_sec_transport._open_once",
                  side_effect=AssertionError("SEC_NET_FORBIDDEN")) as sec,
            patch("urllib.request.urlopen",
                  side_effect=AssertionError("PROVIDER_NET_FORBIDDEN")) as provider,
        ):
            z = build_review_bundle_bytes(
                review_packet=review["review_packet"],
                rights_gap_report=review["source_clearance_report"],
                csv_lineage=lineage,
            )
            inspected = inspect_review_bundle_bytes(z)
        sec.assert_not_called()
        provider.assert_not_called()
        self.assertFalse(inspected["source_authenticated"])


if __name__ == "__main__":
    unittest.main()
