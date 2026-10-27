"""Offline local audit ZIP tests: real-byte retention only after two approvals."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from proofinvest.sec_capture_bundle import (
    preflight_local_bundle_path, save_local_capture_bundle,
    verify_local_capture_bundle,
)
from proofinvest import sec_three_source as capture
from tests.test_sec_three_source import ARGS, FIXED, CONTACT, _Opener
from proofinvest.kic_dl_demo import (
    synthetic_companyfacts, synthetic_submissions, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
)
from proofinvest.kic_dl_original_demo import SYNTHETIC_HTML


class CaptureBundleTests(unittest.TestCase):
    def fixture(self):
        raw1 = synthetic_submissions()
        raw2 = json.dumps(synthetic_companyfacts()).encode()
        raw3 = SYNTHETIC_HTML
        return ({
            "schema": "proofinvest.sec-3source-explicit-transport.v1",
            "status": "three_sec_https_responses_captured_unverified",
            "http_requests_attempted": 3,
            "live_sec_http_called": True,
            "issuer_cik": SYNTHETIC_CIK,
            "accession": SYNTHETIC_ACCESSION,
            "source_uris": {
                "submissions": f"https://data.sec.gov/submissions/CIK{SYNTHETIC_CIK}.json",
                "companyfacts": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SYNTHETIC_CIK}.json",
                "original_filing": "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/synthetic10k.htm",
            },
            "raw_response_sha256": {
                "submissions": hashlib.sha256(raw1).hexdigest(),
                "companyfacts": hashlib.sha256(raw2).hexdigest(),
                "original_filing": hashlib.sha256(raw3).hexdigest(),
            },
            "capture_bytes_persisted": False,
            "source_authenticated": False,
            "financial_facts_authenticated": False,
            "source_rights_verified": False,
            "official_contest_submission": False,
        }, dict(submissions=raw1,companyfacts=raw2,original_filing=raw3))

    def test_write_and_verify_all_three_original_bytes_offline(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"evidence.zip"
            report,raws=self.fixture()
            save_local_capture_bundle(path,receipt=report,**raws)
            read=verify_local_capture_bundle(path)
            self.assertEqual(read["status"],"bundle_integrity_pass_origin_unverified")
            self.assertTrue(read["local_bytes_and_manifest_match"])
            self.assertFalse(read["sec_origin_authenticated"])
            with zipfile.ZipFile(path) as z:
                self.assertEqual(z.read("original_filing.bin"),SYNTHETIC_HTML)
                self.assertEqual(z.read("submissions.json"),synthetic_submissions())
                self.assertNotIn(CONTACT,z.read("manifest.json").decode())
            self.assertEqual([p.name for p in Path(d).iterdir()],["evidence.zip"])

    def test_existing_output_not_overwritten_or_trashed(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"evidence.zip"
            dest.write_bytes(b"original-not-for-overwrite")
            report,raws=self.fixture()
            with self.assertRaises(FileExistsError):
                save_local_capture_bundle(dest,receipt=report,**raws)
            self.assertEqual(dest.read_bytes(),b"original-not-for-overwrite")
            self.assertEqual(list(Path(d).iterdir()),[dest])

    def test_refuses_forged_source_auth_or_tampered_response_hash(self):
        report,raws=self.fixture()
        for mutate in (
            {"source_authenticated":True},
            {"raw_response_sha256":report["raw_response_sha256"]|{"submissions":"0"*64}},
            {"http_requests_attempted":True},
        ):
            with tempfile.TemporaryDirectory() as d:
                with self.subTest(mutate=mutate):
                    with self.assertRaisesRegex(ValueError,"UNTRUSTED_BUNDLE"):
                        save_local_capture_bundle(Path(d)/"x.zip",
                                                  receipt=report|mutate,**raws)
                    self.assertEqual(list(Path(d).iterdir()),[])

    def test_missing_or_modified_zip_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"evidence.zip"
            self.assertEqual(verify_local_capture_bundle(path)["status"],"unavailable")
            report,raws=self.fixture()
            save_local_capture_bundle(path,receipt=report,**raws)
            data=bytearray(path.read_bytes())
            idx=data.find(SYNTHETIC_HTML)
            self.assertGreaterEqual(idx,0)
            data[idx+2] ^= 1
            path.write_bytes(data)
            self.assertEqual(verify_local_capture_bundle(path)["status"],"unavailable")

    def test_atomic_link_failure_cleans_temp_and_never_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"my-archive.zip"
            report,raws=self.fixture()
            with patch("proofinvest.sec_capture_bundle.os.link",
                       side_effect=OSError("unsupported")):
                with self.assertRaisesRegex(OSError,"unsupported"):
                    save_local_capture_bundle(target,receipt=report,**raws)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_declining_retention_aborts_before_any_network(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(capture,"fetch_submissions",
                              side_effect=AssertionError("NETWORK_FORBIDDEN")) as fetch:
                response=capture.run_sec_three_source_review(
                    **(ARGS|{"output_bundle":Path(d)/"e.zip",
                              "acknowledge_local_retention":False}))
            self.assertEqual(response["http_requests_attempted"],0)
            self.assertEqual(response["reason_code"],
                             "EXPLICIT_LOCAL_RETENTION_APPROVAL_REQUIRED")
            fetch.assert_not_called()

    def test_invalid_target_or_existing_symlink_blocks_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/"old.zip"
            old.write_text("old")
            for path in (old,Path(d)/"wrong.txt"):
                with patch.object(capture,"fetch_submissions",
                                  side_effect=AssertionError("NO NETWORK")) as fetch:
                    resp=capture.run_sec_three_source_review(
                        **(ARGS|{"output_bundle":path,
                                 "acknowledge_local_retention":True}))
                self.assertEqual(resp["reason_code"],"LOCAL_BUNDLE_TARGET_UNAVAILABLE")
                fetch.assert_not_called()
            self.assertEqual(old.read_text(),"old")

    def test_mocked_three_source_capture_saves_bundle_only_with_permission(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/"source.zip"
            raws=json.dumps(synthetic_companyfacts()).encode()
            with (patch.object(capture,"_utcnow",return_value=FIXED),
                  patch.object(capture.time,"sleep"),
                  patch.object(capture,"fetch_submissions",return_value=synthetic_submissions()),
                  patch.object(capture,"fetch_original",return_value=(SYNTHETIC_HTML,"text/html")),
                  patch.object(capture.urllib.request,"build_opener",return_value=_Opener(raws))):
                result=capture.run_sec_three_source_review(
                    **(ARGS|{"output_bundle":archive,"acknowledge_local_retention":True}))
            self.assertEqual(result["status"],"three_sec_https_responses_captured_unverified")
            self.assertTrue(result["capture_bytes_persisted"])
            self.assertEqual(verify_local_capture_bundle(archive)["status"],
                             "bundle_integrity_pass_origin_unverified")
            self.assertFalse(result["source_authenticated"])

    def test_symlink_bundle_is_rejected_without_reading_content(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"real.zip"
            src.write_bytes(b"secret")
            link=Path(d)/"linked.zip"
            try:
                link.symlink_to(src)
            except OSError:
                self.skipTest("symlink not available")
            self.assertEqual(verify_local_capture_bundle(link)["status"],"unavailable")
            with self.assertRaises(FileExistsError):
                preflight_local_bundle_path(link)


if __name__=="__main__":
    unittest.main()
