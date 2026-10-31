"""Safe HTML export of locally validated Engine C peer SEC facts."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from proofinvest.industry_peer_companyfacts import bind_peer_companyfacts_to_industry
from proofinvest.local_sec_guard_report import review_local_sec_with_guard
from proofinvest.local_sec_html_report import render_local_sec_html
from proofinvest.three_engine_research import bind_industry_to_sec, summarize_three_engines
from tests.test_local_sec_html_report import fixture
from tests.test_real_data_preflight_peer_companyfacts import setup_peer, CIK, ACC


class LocalPeerHtmlTests(unittest.TestCase):
    def make(self, root: Path):
        _, _, industry, peer = setup_peer(root)
        report = review_local_sec_with_guard(**fixture(root / "audit.sqlite"))
        industry_raw = industry.read_bytes()
        report["industry_vision"] = bind_industry_to_sec(report, industry_raw)
        report["peer_sec_companyfacts_check"] = bind_peer_companyfacts_to_industry(
            industry_raw, peer_sources=[(CIK, ACC, peer.read_bytes())],
        )
        report["three_engine_summary"] = summarize_three_engines(report)
        return report

    def test_real_report_html_contains_peer_digest_but_no_original_bytes(self):
        with TemporaryDirectory() as folder:
            report = self.make(Path(folder))
            rendered = render_local_sec_html(report).decode("utf-8")
        row = report["peer_sec_companyfacts_check"]["peer_records"][0]
        self.assertIn("경쟁사 CompanyFacts 로컬 검산", rendered)
        self.assertIn(row["companyfacts_sha256"], rendered)
        self.assertIn(row["accession"], rendered)
        self.assertIn("SEC 실제 원본 출처", rendered)
        self.assertNotIn("entityName", rendered)
        self.assertNotIn("<script", rendered)

    def test_forged_peer_receipt_cannot_escape_html_reverification(self):
        with TemporaryDirectory() as folder:
            report = self.make(Path(folder))
            changes = (
                ("source_authenticated", True),
                ("audit_written", True),
                ("peer_count", 2),
                ("peer_records", []),
            )
            for field, value in changes:
                broken = deepcopy(report)
                broken["peer_sec_companyfacts_check"][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    render_local_sec_html(broken)
            broken = deepcopy(report)
            broken["peer_sec_companyfacts_check"]["peer_records"][0]["growth_pct"] = "999.00"
            with self.assertRaisesRegex(ValueError, "PEER_ORIGINAL_REVENUE"):
                render_local_sec_html(broken)
            broken = deepcopy(report)
            broken["peer_sec_companyfacts_check"]["peer_records"][0]["companyfacts_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "PEER_ORIGINAL_SHA"):
                render_local_sec_html(broken)

    def test_peer_receipt_cannot_be_rendered_without_engine_c_evidence(self):
        with TemporaryDirectory() as folder:
            report = self.make(Path(folder))
            report.pop("industry_vision")
            report["three_engine_summary"] = summarize_three_engines(report)
            with self.assertRaisesRegex(ValueError, "PEER_ORIGINAL_TRUST"):
                render_local_sec_html(report)


if __name__ == "__main__":
    unittest.main()
