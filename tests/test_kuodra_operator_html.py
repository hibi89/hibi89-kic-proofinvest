"""P11 offline three-intent operator report is safe, opt-in and non-overwriting."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proofinvest.kic_dl_demo import (
    SYNTHETIC_ACCESSION, SYNTHETIC_CIK, synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML
from proofinvest.kuodra_operator_replay import main, run_offline_proposal_replay
from proofinvest.kuodra_operator_html import render_kuodra_operator_html
from proofinvest.sec_capture_bundle import save_local_capture_bundle
from proofinvest.guard_audit import GuardAuditStore
from proofinvest.sec_companyfacts import TAG


def _fixture(root: Path, *, with_balance: bool = True, conflict: bool = False,
             revenue_concept: str = TAG):
    original = synthetic_companyfacts()
    if revenue_concept != TAG:
        original["facts"]["us-gaap"][revenue_concept] = (
            original["facts"]["us-gaap"].pop(TAG)
        )
    if with_balance:
        for name, value in (
            ("Assets", 300), ("Liabilities", 200), ("StockholdersEquity", 100)
        ):
            original["facts"]["us-gaap"][name] = {"units": {"USD": [{
                "accn": SYNTHETIC_ACCESSION, "form": "10-K",
                "end": "2025-09-30", "filed": "2025-10-15", "val": value,
            }]}}
    raw = {
        "submissions": synthetic_submissions(),
        "companyfacts": json.dumps(original).encode(),
        "original_filing": SYNTHETIC_HTML,
    }
    rec = {
        "schema": "proofinvest.sec-3source-explicit-transport.v1",
        "status": "three_sec_https_responses_captured_unverified",
        "http_requests_attempted": 3, "live_sec_http_called": True,
        "issuer_cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
        "source_uris": {
            "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
            "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
            "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
        },
        "raw_response_sha256": {
            k: hashlib.sha256(v).hexdigest() for k, v in raw.items()
        },
        "observed_utc_day": "2025-10-16",
        "submissions_observed_at_utc": "2025-10-16T12:00:00Z",
        "companyfacts_observed_at_utc": "2025-10-16T12:00:01Z",
        "original_observed_at_utc": "2025-10-16T12:00:02Z",
        "capture_bytes_persisted": False,
        "source_authenticated": False,
        "financial_facts_authenticated": False,
        "source_rights_verified": False,
        "official_contest_submission": False,
    }
    src = root / "evidence.zip"
    save_local_capture_bundle(src, receipt=rec, **raw)
    db = root / "audit.sqlite"
    request = {
        "issuer_cik": SYNTHETIC_CIK, "accession": SYNTHETIC_ACCESSION,
        "as_of": "2025-10-16", "requested_intent": "GROWTH_CHECK",
        "capture_zip": str(src), "audit_db": str(db), "run_id": "p11-review",
        "current_end": "2025-09-30", "prior_end": "2024-09-30",
        "needle": PHRASE,
        **({"claimed_growth_pct": "300.00"} if conflict else {}),
    }
    return src, db, request


class OperatorHtmlReportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="kuodra-report-")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.src, self.db, self.req = _fixture(self.root)

    def _report(self, request=None, *, intent="GROWTH_CHECK"):
        request = self.req if request is None else request
        request = dict(request, requested_intent=intent)
        return run_offline_proposal_replay(
            request, {"action": "RUN", "intent": intent},
            acknowledge_local_audit_persistence=True,
        )

    def _cli(self, *, report_html=None, consent=True, req=None, proposal=None):
        request = req if req is not None else self.req
        proposal = proposal if proposal is not None else {
            "action": "RUN", "intent": request["requested_intent"]
        }
        rp, pp = self.root / "request.json", self.root / "proposal.json"
        rp.write_text(json.dumps(request), encoding="utf-8")
        pp.write_text(json.dumps(proposal), encoding="utf-8")
        args = ["--operator-request-json", str(rp),
                "--proposal-json", str(pp)]
        if consent:
            args.append("--acknowledge-local-audit-persistence")
        if report_html is not None:
            args += ["--report-html", str(report_html)]
        with redirect_stdout(io.StringIO()) as out:
            status = main(args)
        return status, json.loads(out.getvalue())

    def test_real_guard_receipt_to_static_html(self):
        with patch("urllib.request.build_opener", side_effect=AssertionError("NO_HTTP")) as n:
            result = self._report()
            page = render_kuodra_operator_html(result).decode("utf-8")
        n.assert_not_called()
        self.assertIn("KUODRA — Offline Evidence Review", page)
        self.assertIn(SYNTHETIC_CIK, page)
        self.assertIn(result["audit"]["event_hash"], page)
        self.assertIn(result["source_review"]["companyfacts_sha256"], page)
        self.assertIn("UNVERIFIED LOCAL SOURCE", page)
        self.assertNotIn("<script", page.lower())
        self.assertNotIn("https://", page)
        self.assertNotIn(str(self.src), page)
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_alt_revenues_taxonomy_reaches_operator_html_from_original_zip(self):
        place = self.root / "alt-revenue"
        place.mkdir()
        source, db, request = _fixture(place, revenue_concept="Revenues")
        with patch("urllib.request.build_opener",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
            out = self._report(request)
            page = render_kuodra_operator_html(out).decode("utf-8")
        network.assert_not_called()
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["verification"]["revenue_concept"], "Revenues")
        self.assertEqual(out["verification"]["annual_period_starts"],
                         ["2023-10-01", "2024-10-01"])
        self.assertIn("<th>Revenue concept</th><td>Revenues</td>", page)
        self.assertIn("100.00%", page)
        self.assertFalse(out["source_authenticated"])
        self.assertTrue(GuardAuditStore(db).verify_chain())
        self.assertTrue(source.is_file())

    def test_risk_check_and_source_review_reports_are_distinct(self):
        for intent in ("SOURCE_REVIEW", "RISK_CHECK"):
            with self.subTest(intent=intent):
                req = dict(self.req, run_id="p11-" + intent)
                result = self._report(req, intent=intent)
                self.assertEqual(result["status"], "completed")
                page = render_kuodra_operator_html(result).decode()
                self.assertIn(intent, page)
                self.assertIn("200.00%", page)
                self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_reject_report_does_not_claim_trade_authorization(self):
        self.req["claimed_growth_pct"] = "300.00"
        result = self._report()
        page = render_kuodra_operator_html(result).decode()
        self.assertEqual(result["guard"]["decision"], "REJECT")
        self.assertIn("REJECT", page)
        self.assertNotIn("trade authorized", page.lower())

    def test_html_escapes_untrusted_guard_reasons(self):
        result = self._report()
        inject = '<img src=x onerror="alert(1)">'
        result["guard"]["reason_codes"].append(inject)
        page = render_kuodra_operator_html(result).decode()
        self.assertIn("&lt;img", page)
        self.assertNotIn(inject, page)

    def test_renderer_refuses_trust_upgrade_and_fake_audit(self):
        original = self._report()
        for node, key, value in (
            (original, "source_authenticated", True),
            (original, "audit_written", False),
            (original["balance_sheet"], "risk_authenticated", True),
            (original["source_review"], "source_rights_verified", True),
            (original["guard"], "decision", "APPROVE"),
        ):
            with self.subTest(key=key):
                copy = json.loads(json.dumps(original))
                # Reapply corruption to a genuinely independent copy.
                if node is original:
                    copy[key] = value
                elif node is original["balance_sheet"]:
                    copy["balance_sheet"][key] = value
                elif node is original["source_review"]:
                    copy["source_review"][key] = value
                else:
                    copy["guard"][key] = value
                with self.assertRaises(ValueError):
                    render_kuodra_operator_html(copy)

    def test_cli_generates_report_once_and_never_overwrites(self):
        target = self.root / "review.html"
        initial = self.src.read_bytes()
        status, body = self._cli(report_html=target)
        self.assertEqual(status, 0)
        self.assertEqual(body["html_report_status"], "written")
        self.assertTrue(body["audit_written"])
        self.assertIn("KUODRA", target.read_text())
        original = target.read_bytes()
        status, body = self._cli(report_html=target)
        self.assertEqual(status, 2)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(self.src.read_bytes(), initial)
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_cli_consent_denial_never_creates_html_or_audit(self):
        target = self.root / "review.html"
        status, body = self._cli(report_html=target, consent=False)
        self.assertEqual(status, 2)
        self.assertEqual(body["html_report_status"], "not_written")
        self.assertFalse(target.exists())
        self.assertFalse(self.db.exists())

    def test_cli_rejects_path_collisions_before_guard(self):
        for target in (
            self.db, self.src, self.root / "request.json",
            self.root / "proposal.json",
        ):
            with self.subTest(target=target.name):
                status, body = self._cli(report_html=target)
                self.assertEqual(status, 2)
                self.assertEqual(body["html_report_status"], "not_written")
                self.assertFalse(self.db.exists())

    def test_cli_blocked_ask_never_writes_html(self):
        target = self.root / "review.html"
        status, body = self._cli(
            report_html=target, proposal={"action": "ASK", "intent": None}
        )
        self.assertEqual(status, 0)
        self.assertEqual(body["status"], "needs_clarification")
        self.assertEqual(body["html_report_status"], "not_written")
        self.assertFalse(target.exists())
        self.assertFalse(self.db.exists())

    def test_legacy_cli_without_html_option_remains_compatible(self):
        status, body = self._cli()
        self.assertEqual(status, 0)
        self.assertNotIn("html_report_status", body)
        self.assertEqual(body["guard"]["decision"], "HOLD")
        self.assertTrue(GuardAuditStore(self.db).verify_chain())

    def test_failure_during_file_write_reports_audit_may_be_present(self):
        target = self.root / "review.html"
        original_open = Path.open

        def fail_open(path, mode="r", *args, **kwargs):
            if path == target and mode == "xb":
                raise OSError("simulated report failure")
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, "open", autospec=True, side_effect=fail_open):
            status, body = self._cli(report_html=target)
        self.assertEqual(status, 2)
        self.assertEqual(body["status"], "report_export_failed")
        self.assertEqual(body["html_report_status"], "failed_check_target")
        self.assertTrue(body["audit_written"])
        self.assertTrue(GuardAuditStore(self.db).verify_chain())


if __name__ == "__main__":
    unittest.main()
