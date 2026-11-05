"""P73 owner-held report ZIP verification, wholly synthetic source integration."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from proofinvest.real_data_preflight import inspect_offline_data_files
from proofinvest.local_report_bundle_verify import verify_local_report_bundle
from proofinvest.kic_dl_original_demo import PHRASE
from tests.test_real_data_preflight_auto_industry import build_args


class ReportBundleVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        opts, *_ = build_args(self.home)
        self.dest = self.home / "report.zip"
        opts["output_report_zip"] = self.dest
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as net:
            self.export_receipt = inspect_offline_data_files(**opts)
        net.assert_not_called()
        self.assertEqual(self.export_receipt["status"],
                         "local_structure_pass_origin_unverified",
                         self.export_receipt)
        self.sha = self.export_receipt["report_bundle_sha256"]

    def test_owner_receipt_zip_fully_replays_json_html_without_writes(self):
        before = {p.name: sha256(p.read_bytes()).hexdigest()
                  for p in self.home.iterdir()}
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NETWORK_FORBIDDEN")) as net:
            proof = verify_local_report_bundle(self.dest, self.sha)
        net.assert_not_called()
        self.assertEqual(proof["status"],
                         "LOCAL_ZIP_BYTES_MATCH_RECEIPT_ORIGIN_UNVERIFIED")
        self.assertEqual(proof["bundle_sha256"], self.sha)
        self.assertEqual(proof["guard_decision"],
                         self.export_receipt["guard_decision_unchanged"])
        self.assertTrue(proof["all_three_inputs_present"])
        for field in ("original_source_authenticated", "data_rights_verified",
                      "point_in_time_authenticated", "real_world_three_engine_verified",
                      "live_api_called", "audit_retained", "trade_executed"):
            self.assertFalse(proof[field])
        self.assertEqual(before, {p.name: sha256(p.read_bytes()).hexdigest()
                                 for p in self.home.iterdir()})

    def test_invalid_receipt_or_one_bit_tamper_denied(self):
        with self.assertRaisesRegex(ValueError,"EXPECTED_RECEIPT_SHA256_REQUIRED"):
            verify_local_report_bundle(self.dest, "")
        with self.assertRaisesRegex(ValueError,"ZIP_RECEIPT_SHA256_MISMATCH"):
            verify_local_report_bundle(self.dest, "0"*64)
        contents = bytearray(self.dest.read_bytes())
        contents[len(contents)//2] ^= 1
        self.dest.write_bytes(contents)
        with self.assertRaisesRegex(ValueError,"ZIP_RECEIPT_SHA256_MISMATCH"):
            verify_local_report_bundle(self.dest, self.sha)

    def _rewrite_bundle(self, transform):
        with ZipFile(self.dest) as zf:
            parts={name:zf.read(name) for name in zf.namelist()}
        transform(parts)
        with ZipFile(self.dest,"w",compression=ZIP_DEFLATED) as zf:
            for name,data in parts.items():
                zf.writestr(name,data)
        return sha256(self.dest.read_bytes()).hexdigest()

    def test_even_newly_pinned_digest_rejects_forged_origin(self):
        def forge(parts):
            m=json.loads(parts["manifest.json"])
            m["source_authenticated"]=True
            parts["manifest.json"]=json.dumps(m,sort_keys=True,indent=2).encode()
        new_sha=self._rewrite_bundle(forge)
        with self.assertRaisesRegex(ValueError,"ZIP_MANIFEST_TRUST"):
            verify_local_report_bundle(self.dest,new_sha)

    def test_even_newly_pinned_digest_rejects_html_change(self):
        def forge(parts):
            data=parts["report.html"] + b"<!--extra-->"
            parts["report.html"]=data
            m=json.loads(parts["manifest.json"])
            m["files"]["report.html"]={"sha256":sha256(data).hexdigest(),"bytes":len(data)}
            parts["manifest.json"]=json.dumps(m,sort_keys=True,indent=2).encode()
        new_sha=self._rewrite_bundle(forge)
        with self.assertRaisesRegex(ValueError,"ZIP_HTML_REPLAY_MISMATCH"):
            verify_local_report_bundle(self.dest,new_sha)

    def test_duplicate_unexpected_and_symlink_archive_rejected(self):
        self._rewrite_bundle(lambda p: p.update({"other.txt":b"invalid"}))
        with self.assertRaisesRegex(ValueError,"ZIP_ENTRY_SET"):
            verify_local_report_bundle(self.dest,sha256(self.dest.read_bytes()).hexdigest())
        target=self.home/"target.zip"
        target.write_bytes(self.dest.read_bytes())
        symlink=self.home/"linked.zip"
        try:
            symlink.symlink_to(target)
        except (OSError,NotImplementedError):
            return
        with self.assertRaisesRegex(ValueError,"ZIP_SYMLINK_BLOCKED"):
            verify_local_report_bundle(symlink,sha256(target.read_bytes()).hexdigest())

    def test_recomputed_digest_cannot_authorize_zip_prefix_or_trailer(self):
        original = self.dest.read_bytes()
        for modified in (b"PREFIX" + original, original + b"TRAILER"):
            with self.subTest(length=len(modified)):
                self.dest.write_bytes(modified)
                with self.assertRaisesRegex(ValueError, "ZIP_NONCANONICAL_ENVELOPE"):
                    verify_local_report_bundle(
                        self.dest, sha256(modified).hexdigest())
        self.dest.write_bytes(original)
        self.assertEqual(
            verify_local_report_bundle(self.dest, self.sha)["bundle_sha256"],
            self.sha)

    def test_cli_success_and_fail_are_sanitized_and_read_only(self):
        cmd=[sys.executable,"-B","-m","proofinvest.local_report_bundle_verify",
             str(self.dest),"--expected-sha256",self.sha]
        ok=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        self.assertEqual(ok.returncode,0,ok.stderr+ok.stdout)
        self.assertEqual(json.loads(ok.stdout)["bundle_sha256"],self.sha)
        self.assertNotIn(str(self.home),ok.stdout)
        bad=subprocess.run(cmd[:-1]+["0"*64],capture_output=True,text=True,timeout=30)
        self.assertEqual(bad.returncode,2)
        self.assertEqual(json.loads(bad.stdout)["reason_code"],
                         "REPORT_ZIP_INTEGRITY_OR_TRUST_FAILED")
        self.assertNotIn(str(self.home),bad.stdout)


if __name__ == "__main__":
    unittest.main()
