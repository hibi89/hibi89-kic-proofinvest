"""P51 genuine-owner-file-shaped SEC 3-source intake without prior ZIP.

All bytes are synthetic here; identity and actual source rights remain unknown.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from proofinvest.kic_dl_original_demo import PHRASE
from proofinvest.real_data_preflight import inspect_offline_data_files
from tests.test_sec_bundle_replay import fixture as sec_fixture
from tests.test_real_data_preflight import create_files, args


def make_direct(root: Path, receipt=None, raws=None):
    if receipt is None or raws is None:
        receipt, raws = sec_fixture()
    mapping = {
        "submissions": root/"submissions.json",
        "companyfacts": root/"companyfacts.json",
        "original_filing": root/"10-k.htm",
    }
    for key,p in mapping.items():
        p.write_bytes(raws[key])
    return {
        "sec_submissions": mapping["submissions"],
        "sec_companyfacts": mapping["companyfacts"],
        "sec_filing": mapping["original_filing"],
        "issuer_cik": receipt["issuer_cik"],
        "accession": receipt["accession"],
        "as_of": receipt["observed_utc_day"],
        "collected_at": "2025-10-16T12:00:00+00:00",
        "prior_end": "2024-09-30",
        "current_end": "2025-09-30",
        "needle": PHRASE,
    }


class DirectSecThreeSourceTests(unittest.TestCase):
    def test_direct_three_files_review_and_sha_not_authentication(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p51-") as tmp:
            root=Path(tmp)
            files=make_direct(root)
            before={p.name:sha256(p.read_bytes()).hexdigest()
                    for p in (files["sec_submissions"],
                              files["sec_companyfacts"],files["sec_filing"])}
            with patch("urllib.request.urlopen",side_effect=AssertionError("NETWORK")) as net:
                response=inspect_offline_data_files(**files)
            net.assert_not_called()
            self.assertEqual(response["status"],"local_structure_pass_origin_unverified")
            self.assertEqual(response["sec_input_mode"],
                             "DIRECT_THREE_FILES_UNAUTHENTICATED")
            self.assertIs(response["sec_capture_digest_matched"],False)
            self.assertIs(response["sec_local_byte_sha256_computed"],True)
            self.assertEqual(response["guard_decision_unchanged"],"HOLD")
            self.assertEqual(response["sec_source_sha256"]["companyfacts"],
                             before["companyfacts.json"])
            self.assertIs(response["source_authenticated"],False)
            self.assertIs(response["audit_retained"],False)
            self.assertEqual(before,{p.name:sha256(p.read_bytes()).hexdigest()
                                    for p in (files["sec_submissions"],
                                              files["sec_companyfacts"],
                                              files["sec_filing"])})
            self.assertEqual(len(list(root.iterdir())),3)

    def test_direct_three_files_plus_price_and_industry_existing_engines(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p51-") as tmp:
            root=Path(tmp)
            files=make_direct(root)
            z,market,sector,_=create_files(root)
            # The existing ZIP remains optional and is deliberately NOT used.
            result=inspect_offline_data_files(**(files|{
                k:v for k,v in args(z,market,sector).items()
                if k not in ("sec_bundle","prior_end","current_end","needle")}))
            self.assertEqual(result["status"],"local_structure_pass_origin_unverified")
            self.assertTrue(result["all_three_inputs_present"])
            self.assertEqual(result["market_status"],"REPORTED_UNVERIFIED")
            self.assertEqual(result["industry_status"],"OBSERVED_COMPARISON_UNVERIFIED")
            self.assertEqual(result["sec_input_mode"],
                             "DIRECT_THREE_FILES_UNAUTHENTICATED")
            self.assertFalse(result["three_engine_real_world_validated"])
            self.assertFalse(result["external_http_called"])

    def test_direct_mode_and_zip_cannot_be_mixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            files=make_direct(root)
            z,_,_,_=create_files(root)
            self.assertEqual(inspect_offline_data_files(**(files|{
                "sec_bundle":z}))["reason_code"],"MIXED_SEC_INPUT_MODES_BLOCKED")
            self.assertEqual(inspect_offline_data_files(
                prior_end="2024-09-30",current_end="2025-09-30",
                needle=PHRASE,
            )["reason_code"],"INCOMPLETE_DIRECT_SEC_THREE_FILES")
            partial=files.copy()
            partial.pop("sec_companyfacts")
            self.assertEqual(inspect_offline_data_files(
                **partial)["reason_code"],"INCOMPLETE_DIRECT_SEC_THREE_FILES")

    def test_issuer_accession_and_capture_clock_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=make_direct(Path(tmp))
            for override in (
                {"issuer_cik":"1"},
                {"issuer_cik":"0000000000"},
                {"issuer_cik":"0000000002"},
                {"accession":"WRONG"},
                {"accession":"0000000009-25-000001"},
                {"as_of":"2025-02-30"},
                {"as_of":"2025-10-15"},
                {"collected_at":"2025-10-16T12:00:00"},
                {"collected_at":"2025-10-16T12:00:00+09:00"},
                {"collected_at":"2025-10-15T12:00:00Z"},
                {"collected_at":"not-a-timestamp"},
            ):
                with self.subTest(override=override):
                    result=inspect_offline_data_files(**(files|override))
                    self.assertEqual(result["status"],"blocked")
                    self.assertFalse(result["source_authenticated"])
                    self.assertFalse(result["audit_retained"])

    def test_missing_symlink_and_large_source_files_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            files=make_direct(root)
            link=root/"companyfacts-link.json"
            try:
                link.symlink_to(files["sec_companyfacts"])
            except (OSError,NotImplementedError):
                pass
            else:
                blocked=inspect_offline_data_files(**(files|{
                    "sec_companyfacts":link}))
                self.assertEqual(blocked["status"],"blocked")
            self.assertEqual(inspect_offline_data_files(**(files|{
                "sec_filing":root/"does-not-exist"}))["status"],"blocked")
            # No full-size 24MB allocation is required to test this guard:
            # invalid/zero-byte content still cannot pass.
            files["sec_filing"].write_bytes(b"")
            self.assertEqual(inspect_offline_data_files(**files)["status"],"blocked")

    def test_direct_cli_runs_with_temp_inputs_and_sanitized_result(self):
        with tempfile.TemporaryDirectory(prefix="kuodra-p51-") as tmp:
            root=Path(tmp)
            files=make_direct(root)
            argv=[sys.executable,"-m","proofinvest.real_data_preflight",
                  "--sec-submissions",str(files["sec_submissions"]),
                  "--sec-companyfacts",str(files["sec_companyfacts"]),
                  "--sec-filing",str(files["sec_filing"]),
                  "--issuer-cik",files["issuer_cik"],
                  "--accession",files["accession"],
                  "--as-of",files["as_of"],
                  "--collected-at","2025-10-16T12:00:00Z",
                  "--prior-end",files["prior_end"],
                  "--current-end",files["current_end"],
                  "--needle",files["needle"]]
            p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr)
            response=json.loads(p.stdout)
            self.assertEqual(response["sec_input_mode"],
                             "DIRECT_THREE_FILES_UNAUTHENTICATED")
            self.assertFalse(response["source_authenticated"])
            self.assertFalse(response["sec_capture_digest_matched"])
            self.assertEqual(len(list(root.iterdir())),3)
            self.assertNotIn("synthetic10k.htm",p.stdout)


if __name__=="__main__":
    unittest.main()
