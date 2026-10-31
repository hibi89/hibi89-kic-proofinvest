"""P50 tests for bounded market data vintage/adjustment declaration gates.

These are synthetic local claim-consistency tests, NOT vendor authentication.
"""
from __future__ import annotations

from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.market_data_evidence import validate_market_evidence
from proofinvest.market_price_csv import market_price_csv_to_json
from proofinvest.real_data_preflight import inspect_offline_data_files
from tests.test_market_price_csv import csv_from_fixture
from tests.test_real_data_preflight import create_files, args


def evidence_fixture(csv: bytes | None = None, *, basis: str = "PRICE_ONLY_CLOSE") -> dict:
    csv = csv_from_fixture() if csv is None else csv
    return {
        "schema": "kuodra.market-data-evidence.v1",
        "issuer_cik": "0000000001",
        "as_of": "2025-10-16",
        "symbol": "SYNTH",
        "benchmark": "NASDAQ_100",
        "return_basis": basis,
        "market_csv_sha256": sha256(csv).hexdigest(),
        "price_first_date": "2025-08-01",
        "price_last_date": "2025-10-02",
        "claimed_source_url": "https://example.org/combined-price-sheet",
        "claimed_published_at": "2025-10-15",
        "captured_at_utc": "2025-10-15T12:00:00Z",
        "price_provider": "SYNTHETIC_ONLY",
        "rights_scope": "UNKNOWN",
        "revision_policy": "VERSIONED_SNAPSHOT_CLAIMED",
        "stock_split_treatment": "UNADJUSTED",
        "stock_dividend_treatment": "EXCLUDED",
        "benchmark_total_return_claimed": False,
    }


def payload(csv: bytes | None = None, *, basis: str = "PRICE_ONLY_CLOSE") -> dict:
    csv = csv_from_fixture() if csv is None else csv
    return json.loads(market_price_csv_to_json(
        csv, issuer_cik="0000000001", as_of="2025-10-16",
        symbol="SYNTH", benchmark="NASDAQ_100",
        return_basis=basis,
        source_url="https://example.org/combined-price-sheet",
        published_at="2025-10-15",
    ))


def check(x: dict, csv: bytes | None = None, *, basis: str = "PRICE_ONLY_CLOSE"):
    csv = csv_from_fixture() if csv is None else csv
    return validate_market_evidence(
        json.dumps(x, sort_keys=True).encode(), csv_bytes=csv,
        normalized_market_payload=payload(csv, basis=basis),
    )


class MarketDataEvidenceTests(unittest.TestCase):
    def test_claims_matched_to_real_local_csv_bytes_but_never_authenticated(self):
        csv=csv_from_fixture()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_NETWORK")) as network:
            out=check(evidence_fixture(csv),csv)
        network.assert_not_called()
        self.assertEqual(out["market_csv_sha256"],sha256(csv).hexdigest())
        self.assertEqual(out["claimed_vintage_status"],
                         "PRE_ASOF_CAPTURE_CLAIMED_UNAUTHENTICATED")
        self.assertEqual(out["status"],"LOCAL_DECLARATIONS_CONSISTENT_UNVERIFIED")
        for key in ("source_authenticated","data_rights_verified",
                    "corporate_actions_verified",
                    "historical_market_vintage_authenticated",
                    "point_in_time_backtest_verified","trade_signal",
                    "external_http_called"):
            self.assertFalse(out[key],key)
        self.assertNotIn("rights_verified",out)

    def test_retrospective_capture_is_still_recorded_not_pit_claim(self):
        x=evidence_fixture()
        x["captured_at_utc"]="2025-10-17T12:00:00Z"
        out=check(x)
        self.assertEqual(out["claimed_vintage_status"],
                         "RETROSPECTIVE_CAPTURE_NOT_POINT_IN_TIME")
        self.assertFalse(out["historical_market_vintage_authenticated"])

    def test_adjusted_basis_requires_coherent_but_unverified_dividends(self):
        x=evidence_fixture(basis="ADJUSTED_CLOSE_TOTAL_RETURN_PROXY")
        x["stock_split_treatment"]="ADJUSTED_CLAIMED"
        x["stock_dividend_treatment"]="INCLUDED_CLAIMED"
        x["benchmark_total_return_claimed"]=True
        out=check(x,basis="ADJUSTED_CLOSE_TOTAL_RETURN_PROXY")
        self.assertEqual(out["return_basis"],"ADJUSTED_CLOSE_TOTAL_RETURN_PROXY")
        self.assertFalse(out["corporate_actions_verified"])
        for changed in (
            {"stock_split_treatment":"UNADJUSTED"},
            {"stock_dividend_treatment":"EXCLUDED"},
            {"benchmark_total_return_claimed":False},
        ):
            with self.subTest(change=changed), self.assertRaisesRegex(
                    ValueError,"ADJUSTED_RETURN_DEFINITION_CONFLICT"):
                check(x | changed,basis="ADJUSTED_CLOSE_TOTAL_RETURN_PROXY")

    def test_wrong_sha_issuer_symbol_date_or_url_are_rejected(self):
        x=evidence_fixture()
        for changed in (
            {"market_csv_sha256":"0"*64},
            {"issuer_cik":"0000000002"},
            {"symbol":"WRONG"},
            {"benchmark":"DJIA"},
            {"as_of":"2025-10-15"},
            {"claimed_source_url":"https://other.example.org/data"},
            {"price_first_date":"2025-07-31"},
            {"price_last_date":"2025-10-01"},
            {"claimed_published_at":"2025-10-14"},
            {"claimed_published_at":"2025-10-17"},
        ):
            with self.subTest(change=changed),self.assertRaises(ValueError):
                check(x|changed)

    def test_malformed_or_inconsistent_manifest_does_not_pass(self):
        x=evidence_fixture()
        x["captured_at_utc"]="2025-10-14T12:00:00Z"
        with self.assertRaisesRegex(ValueError,"CAPTURE_BEFORE_REPORTED_RELEASE"):
            check(x)
        for stamp in ("2025-10-15T12:00:00+00:00",
                      "2025-02-30T12:00:00Z","2025-10-15 12:00:00"):
            x=evidence_fixture()|{"captured_at_utc":stamp}
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                check(x)
        x=evidence_fixture()|{"stock_dividend_treatment":"UNKNOWN"}
        with self.assertRaisesRegex(ValueError,"PRICE_RETURN_DEFINITION_CONFLICT"):
            check(x)
        x=evidence_fixture()|{"benchmark_total_return_claimed":"false"}
        with self.assertRaises(ValueError):
            check(x)
        x=evidence_fixture()|{"provider_license_key":"DO_NOT_WRITE_KEYS"}
        with self.assertRaisesRegex(ValueError,"EXACT_SCHEMA_FIELDS_REQUIRED"):
            check(x)
        data=json.dumps(evidence_fixture()).encode()
        with self.assertRaises(ValueError):
            validate_market_evidence(
                data + b"\x00"*(8192),csv_bytes=csv_from_fixture(),
                normalized_market_payload=payload(),
            )
        with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
            validate_market_evidence(
                b'{"schema":"x","schema":"y"}',csv_bytes=csv_from_fixture(),
                normalized_market_payload=payload(),
            )

    def test_local_preflight_optional_manifest_and_adjusted_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p50-") as d:
            root=Path(d)
            bundle,market,sector,_=create_files(root)
            base=args(bundle,market,sector)
            no_manifest=inspect_offline_data_files(**base)
            self.assertEqual(no_manifest["status"],
                             "local_structure_pass_origin_unverified")
            self.assertEqual(no_manifest["market_evidence_status"],
                             "MISSING_OPERATOR_EVIDENCE")
            adjusted=base | {"return_basis":"ADJUSTED_CLOSE_TOTAL_RETURN_PROXY"}
            no_adjusted_manifest=inspect_offline_data_files(**adjusted)
            self.assertEqual(no_adjusted_manifest["status"],"blocked")
            self.assertEqual(no_adjusted_manifest["reason_code"],
                             "ADJUSTED_PRICE_REQUIRES_EVIDENCE_MANIFEST")
            manifest=evidence_fixture(market.read_bytes())
            manifest.update(
                issuer_cik="0000000001",
                claimed_source_url="https://example.org/legal-operator-csv",
            )
            outpath=root/"market-evidence.json"
            outpath.write_bytes(json.dumps(manifest).encode())
            result=inspect_offline_data_files(
                **(base|{"market_evidence_json":outpath}))
            self.assertEqual(result["status"],"local_structure_pass_origin_unverified")
            self.assertEqual(result["market_evidence_status"],
                             "LOCAL_DECLARATIONS_CONSISTENT_UNVERIFIED")
            self.assertEqual(result["market_evidence_sha256"],
                             sha256(outpath.read_bytes()).hexdigest())
            self.assertEqual(result["market_evidence_vintage"],
                             "PRE_ASOF_CAPTURE_CLAIMED_UNAUTHENTICATED")
            before=result["market_csv_original_sha256"]
            manifest["market_csv_sha256"]="f"*64
            outpath.write_bytes(json.dumps(manifest).encode())
            blocked=inspect_offline_data_files(
                **(base|{"market_evidence_json":outpath}))
            self.assertEqual(blocked["status"],"blocked")
            self.assertFalse(blocked["three_engine_real_world_validated"])
            self.assertEqual(before,sha256(market.read_bytes()).hexdigest())

    def test_manifest_without_csv_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p50-") as d:
            root=Path(d)
            bundle,market,sector,_=create_files(root)
            manifest=root/"evidence.json"
            manifest.write_bytes(json.dumps(evidence_fixture(market.read_bytes())).encode())
            result=inspect_offline_data_files(
                **(args(bundle)|{"market_evidence_json":manifest}))
            self.assertEqual(result["reason_code"],"MARKET_EVIDENCE_WITHOUT_PRICE_CSV")
            alias=root/"link.json"
            try:
                alias.symlink_to(manifest)
            except (OSError, NotImplementedError):
                return
            result=inspect_offline_data_files(
                **(args(bundle,market)|{"market_evidence_json":alias}))
            self.assertEqual(result["status"],"blocked")


if __name__=="__main__":
    unittest.main()
