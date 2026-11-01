"""P96 local industry builder UX and source-backed integration tests.

Only generated SEC-shaped synthetic data. No provider API or trading.
"""
from __future__ import annotations

from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.industry_source_builder_ui import (
    _uploaded_bytes, prepare_ui_industry_packet, render_local_industry_builder,
)
from proofinvest.industry_vision_ui import render_local_industry_vision
from proofinvest.kuodra_local_workspace_ui import (
    _selected_workspace_sources, _verify_uploaded_peers,
)
from proofinvest.peer_cash_conversion import compare_peer_cash_conversion
from proofinvest.industry_vision import analyze_industry_vision, parse_industry_vision_json
from proofinvest.operator_sec_zip import make_operator_sec_zip_bytes
from tests.test_peer_cash_trend import extend_with_prior
from tests.test_industry_packet_builder import CSV
from tests.test_sec_bundle_replay import fixture


class Upload:
    def __init__(self, content: bytes):
        self.data = content
        self.size = len(content)

    def getvalue(self):
        return self.data

    def replace(self, raw: bytes):
        self.data = raw
        self.size = len(raw)


def case(*, two_peers=False):
    _, target, peers = extend_with_prior(two_peers=two_peers)
    options = {
        "target_companyfacts": target[2],
        "target_cik": target[0],
        "target_accession": target[1],
        "target_name": "SYNTHETIC_FIRM",
        "peer_uploads": [
            (cik, accession, "SYNTHETIC_PEER_" + str(i), Upload(raw))
            for i, (cik, accession, raw) in enumerate(peers, 1)
        ],
        "sector_upload": Upload(CSV),
        "sector_url": "https://www.bea.gov/data/industry/synthetic-manual-normalization",
        "sector_published_at": "2025-10-15",
        "as_of": "2025-10-16",
        "prior_end": "2024-09-30",
        "current_end": "2025-09-30",
        "industry_name": "SYNTHETIC_SECTOR",
        "series_name": "INDEX_TWO_ANNUAL_YEARS",
        "series_kind": "PRODUCTION_INDEX",
        "sector_unit": "index_points",
    }
    return options, target, peers


class StubUI:
    def __init__(self, data=None, enabled=True):
        self.data = data or {}
        self.enabled = enabled
        self.calls = []

    def subheader(self, value):
        self.calls.append(("subheader", value))

    def checkbox(self, label, **kwargs):
        self.calls.append(("checkbox", label))
        return self.enabled

    def caption(self, value):
        self.calls.append(("caption", value))

    def text_input(self, label, **kwargs):
        return self.data.get(kwargs.get("key"), "")

    def selectbox(self, label, options, **kwargs):
        return options[0]

    def file_uploader(self, label, **kwargs):
        self.calls.append(("file_uploader", label))
        return self.data.get(kwargs.get("key"))

    def number_input(self, label, **kwargs):
        return self.data.get(kwargs.get("key"), 1)

    def info(self, value):
        self.calls.append(("info", value))

    def error(self, value):
        self.calls.append(("error", value))

    def success(self, value):
        self.calls.append(("success", value))

    def json(self, value):
        self.calls.append(("json", value))

    def warning(self, value):
        self.calls.append(("warning", value))

    def write(self, value):
        self.calls.append(("write", value))

    def table(self, value):
        self.calls.append(("table", value))


def widgets(options):
    cik, accession, name, upload = options["peer_uploads"][0]
    return {
        "kuodra_builder_target_name": options["target_name"],
        "kuodra_builder_industry_name": options["industry_name"],
        "kuodra_builder_series_name": options["series_name"],
        "kuodra_builder_sector_unit": options["sector_unit"],
        "kuodra_builder_sector_url": options["sector_url"],
        "kuodra_builder_sector_date": options["sector_published_at"],
        "kuodra_builder_sector_csv": options["sector_upload"],
        "kuodra_builder_peer_count": 1,
        "kuodra_builder_peer_cik_0": cik,
        "kuodra_builder_peer_accession_0": accession,
        "kuodra_builder_peer_name_0": name,
        "kuodra_builder_peer_upload_0": upload,
    }


class LocalSourceBuilderTests(unittest.TestCase):
    def test_build_existing_finance_engine_without_http_and_same_peer_handles(self):
        options, target, peers = case()
        target_sha = sha256(target[2]).hexdigest()
        peer_sha = sha256(peers[0][2]).hexdigest()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("PROVIDER_HTTP_FORBIDDEN")) as web:
            packet, handles = prepare_ui_industry_packet(**options)
            derived = analyze_industry_vision(parse_industry_vision_json(packet))
            peer_receipt = _verify_uploaded_peers(packet, handles)
            comparison = compare_peer_cash_conversion(
                packet, target_source=target, peer_sources=peers,
            )
        web.assert_not_called()
        self.assertEqual(handles[0][-1], options["peer_uploads"][0][-1])
        self.assertEqual(sha256(handles[0][-1].getvalue()).hexdigest(), peer_sha)
        self.assertEqual(derived["target"]["growth_pct_reported_input"], "100.00")
        self.assertEqual(derived["industry_series"]["growth_pct_reported_input"], "20.00")
        self.assertEqual(derived["sources"][0]["sha256"], target_sha)
        self.assertEqual(peer_receipt["peer_records"][0]["companyfacts_sha256"], peer_sha)
        self.assertEqual(comparison["cash_conversion_target_pct"], "33.33")
        self.assertEqual(comparison["cash_conversion_peer_median_pct"], "50.00")
        self.assertEqual(comparison["two_year_target_minus_peer_change_pp"], "-91.67")
        self.assertFalse(comparison["issuer_source_authenticated"])
        self.assertFalse(comparison["guard_policy_modified"])
        self.assertFalse(comparison["trade_executed"])

    def test_two_peers_both_present_in_source_bound_vision(self):
        options, _target, _peers = case(two_peers=True)
        packet, handles = prepare_ui_industry_packet(**options)
        data = parse_industry_vision_json(packet)
        self.assertEqual(len(data["peers"]), 2)
        self.assertEqual(len(handles), 2)
        self.assertEqual(data["sources"][0]["sha256"],
                         sha256(options["target_companyfacts"]).hexdigest())
        self.assertEqual(
            [record["cik"] for record in data["peers"]],
            [peer[0] for peer in options["peer_uploads"]],
        )

    def test_raw_upload_mutation_after_build_invalidates_later_guard_peer_receipt(self):
        options, _target, _peers = case()
        packet, handles = prepare_ui_industry_packet(**options)
        changed = json.loads(handles[0][-1].getvalue())
        first = changed["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ]["units"]["USD"][0]
        first["val"] += 1
        handles[0][-1].replace(json.dumps(changed).encode())
        with self.assertRaises(ValueError):
            _verify_uploaded_peers(packet, handles)

    def test_wrong_cik_time_and_sector_csv_fail_closed(self):
        options, _, _ = case()
        options["peer_uploads"][0] = (
            options["target_cik"], *options["peer_uploads"][0][1:],
        )
        with self.assertRaisesRegex(ValueError, "P96_DUPLICATE_OR_INVALID_PEER"):
            prepare_ui_industry_packet(**options)
        options, _, _ = case()
        options["sector_published_at"] = "2025-10-17"
        with self.assertRaises(ValueError):
            prepare_ui_industry_packet(**options)
        options, _, _ = case()
        options["sector_upload"] = Upload(
            b"period_end,value\n2024-09-30,200\n2024-09-30,240\n"
        )
        with self.assertRaises(ValueError):
            prepare_ui_industry_packet(**options)

    def test_bad_sizes_types_and_peer_limit_rejected_before_parsing(self):
        options, _, _ = case()
        options["peer_uploads"] = options["peer_uploads"] * 9
        with self.assertRaisesRegex(ValueError, "P96_PEER_COUNT_INVALID"):
            prepare_ui_industry_packet(**options)
        options, _, _ = case()
        options["sector_upload"] = Upload(CSV)
        options["sector_upload"].size += 1
        with self.assertRaisesRegex(ValueError, "P96_BAD_SECTOR_CSV_UPLOAD"):
            prepare_ui_industry_packet(**options)
        options, _, _ = case()
        options["target_companyfacts"] = b""
        with self.assertRaisesRegex(ValueError, "P96_TARGET_COMPANYFACTS_INVALID"):
            prepare_ui_industry_packet(**options)
        with self.assertRaises(ValueError):
            _uploaded_bytes(Upload(b""), 16, "BAD_INPUT")

    def test_builder_widget_normal_and_generated_vision_no_second_industry_upload(self):
        options, target, _ = case()
        ui = StubUI(widgets(options))
        request = {
            "cik": target[0], "accession": target[1],
            "as_of": options["as_of"], "collected_at": "2025-10-16T12:00:00Z",
            "prior_end": options["prior_end"], "current_end": options["current_end"],
        }
        manual = {
            "submissions": None, "companyfacts": None,
            "original_filing": None, "history_page": None,
        }
        calls = []
        def source_loader(files, zip_input, *, request):
            calls.append(request)
            return {"companyfacts": target[2]}
        raw, handles = render_local_industry_builder(
            ui, uploaded_target_sources=manual, operator_archive=None,
            request=request, source_loader=source_loader,
        )
        self.assertIsInstance(raw, bytes)
        self.assertEqual(len(handles), 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("success", [kind for kind, _ in ui.calls])
        review = StubUI(enabled=False)
        output = render_local_industry_vision(
            review, cik=target[0], as_of=options["as_of"], generated_raw=raw,
        )
        self.assertEqual(output, raw)
        self.assertNotIn("file_uploader", [kind for kind, _ in review.calls])
        self.assertIn("table", [kind for kind, _ in review.calls])
        self.assertNotIn("error", [kind for kind, _ in review.calls])

    def test_opt_out_missing_data_and_stale_owner_zip_never_reuses_derived_packet(self):
        options, target, _ = case()
        request = {
            "cik": target[0], "accession": target[1],
            "as_of": options["as_of"], "collected_at": "2025-10-16T12:00:00Z",
            "prior_end": options["prior_end"], "current_end": options["current_end"],
        }
        off = StubUI(enabled=False)
        called = []
        def loader(*args, **kwargs):
            called.append(True)
            return {"companyfacts": target[2]}
        result = render_local_industry_builder(
            off, uploaded_target_sources={}, operator_archive=None,
            request=request, source_loader=loader,
        )
        self.assertEqual(result, (None, []))
        self.assertEqual(called, [])
        incomplete = StubUI(data=widgets(options) | {
            "kuodra_builder_sector_csv": None,
        })
        result = render_local_industry_builder(
            incomplete, uploaded_target_sources={}, operator_archive=None,
            request=request, source_loader=loader,
        )
        self.assertEqual(result, (None, []))
        self.assertEqual(called, [])
        self.assertIn("info", [k for k, _ in incomplete.calls])
        receipt, sources = fixture()
        packed = make_operator_sec_zip_bytes(
            submissions=sources["submissions"],
            companyfacts=sources["companyfacts"],
            original_filing=sources["original_filing"],
            issuer_cik=receipt["issuer_cik"],
            accession=receipt["accession"],
            as_of=receipt["observed_utc_day"],
            collected_at=receipt["submissions_observed_at_utc"],
        )
        from tests.test_operator_sec_zip import Uploaded
        stale = StubUI(data=widgets(options))
        def real_loader(*args, **kwargs):
            return _selected_workspace_sources(*args, **kwargs)
        result = render_local_industry_builder(
            stale,
            uploaded_target_sources={
                "submissions": None, "companyfacts": None,
                "original_filing": None, "history_page": None,
            },
            operator_archive=Uploaded(packed),
            request=dict(request, as_of="2025-10-17"),
            source_loader=real_loader,
        )
        self.assertEqual(result, (None, []))
        self.assertIn("error", [k for k, _ in stale.calls])


if __name__ == "__main__":
    unittest.main()
