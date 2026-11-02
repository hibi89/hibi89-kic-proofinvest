"""P118 independently recompute local report against exact original bytes."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from proofinvest import ticker_sec_transport as transport
from proofinvest.ticker_local_sources import prepare_local_ticker_sources
from proofinvest.ticker_sec_financial_bridge import inspect_collected_annual_revenue
from proofinvest.ticker_sec_original_guard_preview import inspect_original_guard_preview
from proofinvest.ticker_market_industry_bridge import evaluate_ticker_a_c
from proofinvest.ticker_local_report import (
    main, make_local_report, report_json_bytes, verify_local_report,
)
from tests.test_ticker_sec_financial_bridge import valid_case
from tests.test_ticker_sec_original_guard_preview import valid_xhtml
from tests.test_ticker_market_industry_bridge import scenario


def report_case(*, market=None, industry=None, as_of="2025-10-16", raws=None):
    if raws is None:
        _, raws = valid_case()
        raws = dict(raws, original_10k=valid_xhtml())
    receipt = prepare_local_ticker_sources(
        ticker="NVDA", as_of=as_of, sources=raws)
    revenue = inspect_collected_annual_revenue(receipt, raws)
    original = inspect_original_guard_preview(
        receipt, raws, expected_revenue=revenue)
    ac = evaluate_ticker_a_c(
        receipt, raws, market_json=market, industry_json=industry)
    report = make_local_report(receipt, revenue, original, ac)
    return report, raws


def _reseal(report):
    fresh = {k: v for k, v in report.items() if k != "report_sha256"}
    data = (json.dumps(fresh, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()
    report["report_sha256"] = sha256(data).hexdigest()
    return report


class LocalReportReplayTests(unittest.TestCase):
    def test_valid_replay_without_http_and_with_source_hashes(self):
        report, raw = report_case()
        with patch.object(transport, "_open_once",
                          side_effect=AssertionError("SEC HTTP IS FORBIDDEN")) as net:
            verified = verify_local_report(report, sources=raw)
        net.assert_not_called()
        self.assertEqual(verified["status"], "PASS", verified)
        self.assertEqual(
            verified["reason_code"], "EXACT_LOCAL_BYTES_AND_CALCULATIONS_MATCH")
        self.assertFalse(verified["source_authenticated"])
        self.assertFalse(verified["source_rights_verified"])
        self.assertFalse(verified["trade_executed"])
        self.assertEqual(report["engine_a_input_sha256"], None)
        self.assertEqual(report["engine_c_input_sha256"], None)

    def test_rehashing_a_forged_growth_or_guard_does_not_validate(self):
        report, raw = report_case()
        for path, value in (
            (("verification", "growth_pct"), "500.00"),
            (("issuer", "accession"), "0000000000-00-000000"),
            (("guard_policy_preview",), "REJECT"),
            (("limits", "source_authenticated"), True),
            (("engine_a_status",), "REPORTED_UNVERIFIED"),
        ):
            with self.subTest(path=path):
                forged = deepcopy(report)
                if len(path) == 2:
                    forged[path[0]][path[1]] = value
                else:
                    forged[path[0]] = value
                forged = _reseal(forged)
                self.assertEqual(verify_local_report(forged, sources=raw)[
                    "reason_code"], "REPORT_SEMANTIC_REPLAY_MISMATCH")
        altered = deepcopy(report)
        altered["verification"]["growth_pct"] = "9999.00"
        self.assertEqual(verify_local_report(altered, sources=raw)[
            "reason_code"], "REPORT_DIGEST_MISMATCH")

    def test_changed_source_bytes_fail_even_if_benign_whitespace(self):
        report, raw = report_case()
        for k in raw:
            with self.subTest(k=k):
                changed = dict(raw, **{k: raw[k] + b" "})
                result = verify_local_report(report, sources=changed)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["reason_code"],
                                 "SOURCE_BYTES_OR_SHA_CHANGED")
        self.assertEqual(verify_local_report(report, sources={
            "ticker_map": raw["ticker_map"]})["status"], "FAIL")

    def test_optional_engine_a_c_sources_are_digest_pinned(self):
        receipt, raw, m, c = scenario()
        mbytes = json.dumps(m).encode()
        cbytes = json.dumps(c).encode()
        report, raw = report_case(
            market=mbytes, industry=cbytes, as_of="2026-02-01", raws=raw)
        self.assertEqual(report["engine_a_status"], "REPORTED_UNVERIFIED")
        self.assertEqual(report["engine_c_status"],
                         "OBSERVED_COMPARISON_UNVERIFIED")
        self.assertEqual(report["engine_a_input_sha256"],
                         sha256(mbytes).hexdigest())
        self.assertEqual(report["engine_c_input_sha256"],
                         sha256(cbytes).hexdigest())
        self.assertEqual(verify_local_report(
            report, sources=raw, market_json=mbytes,
            industry_json=cbytes)["status"], "PASS")
        self.assertEqual(verify_local_report(
            report, sources=raw)["status"], "FAIL")
        self.assertEqual(verify_local_report(
            report, sources=raw, market_json=mbytes + b" ",
            industry_json=cbytes)["status"], "FAIL")

    def test_cli_reads_local_exact_files_and_does_not_modify_them(self):
        report, raw = report_case()
        with tempfile.TemporaryDirectory(prefix="kuodra-p118-local-") as root:
            base = Path(root)
            paths = {}
            for k, value in raw.items():
                p = base / (k + ".json")
                p.write_bytes(value)
                paths[k] = p
            report_file = base / "report.json"
            report_file.write_bytes(report_json_bytes(report))
            input_files = [report_file, *paths.values()]
            before = {p.name: sha256(p.read_bytes()).hexdigest()
                      for p in input_files}
            args = ["--report", str(report_file)]
            for k, p in paths.items():
                args += ["--" + k.replace("_", "-"), str(p)]
            stdout = io.StringIO()
            with patch.object(transport, "_open_once",
                              side_effect=AssertionError("NO SEC")), redirect_stdout(stdout):
                exit_code = main(args)
            self.assertEqual(exit_code, 0)
            emitted = json.loads(stdout.getvalue())
            self.assertEqual(emitted["status"], "PASS")
            self.assertEqual(emitted["network_requests"], 0)
            self.assertEqual(before, {
                p.name: sha256(p.read_bytes()).hexdigest() for p in input_files})
            self.assertNotIn("raw_sources", stdout.getvalue())
            # Both malformed report and tampered source must yield a safe
            # nonzero code without showing the original file bytes.
            report_file.write_bytes(b'{"schema":"x","schema":"y"}')
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(args)
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["reason_code"],
                             "LOCAL_INPUT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
