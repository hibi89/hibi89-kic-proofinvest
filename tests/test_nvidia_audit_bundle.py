"""P212: actual publisher-derived NVDA Guard audit -> portable local ZIP replay."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_STORED

from proofinvest import nvidia_audit_bundle as p
from proofinvest.nvidia_real_guard_audit import run_nvidia_guard_audit
from proofinvest.nvidia_real_issuer_review import actual_nvidia_issuer_receipt

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"


class P212RealNvidiaExportTests(unittest.TestCase):
    def setUp(self):
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.db = Path(d.name) / "audit.sqlite"
        self.out = Path(d.name) / "owner-nvda.zip"

    def real(self, *, consent=True, receipt=None):
        return run_nvidia_guard_audit(
            run_id="P212-nvda-human-review", audit_db_path=self.db,
            acknowledge_local_persistence=consent,
            source_receipt=actual_nvidia_issuer_receipt() if receipt is None else receipt,
        )

    def test_consent_guard_and_local_zip_three_files(self):
        denied = self.real(consent=False)
        self.assertFalse(self.db.exists())
        with self.assertRaises(ValueError):
            p.build_nvidia_audit_bundle(denied)
        audit = self.real()
        self.assertTrue(audit["audit_chain_valid"])
        blob, digest = p.build_nvidia_audit_bundle(audit)
        self.assertEqual(digest, sha256(blob).hexdigest())
        self.assertLess(len(blob), 80000)
        with ZipFile(BytesIO(blob)) as zipped:
            self.assertEqual(set(zipped.namelist()),
                             {"review.json", "review.html", "manifest.json"})
            report = json.loads(zipped.read("review.json"))
            html = zipped.read("review.html").decode()
            self.assertEqual(report["audit"]["guard_decision"], "HOLD")
            self.assertEqual(report["ticker"], "NVDA")
            self.assertEqual(report["metrics"]["revenue_growth_pct"], "65.47")
            self.assertIn("SEC original", html)
            self.assertNotIn("<script", html)
            self.assertNotIn("private_key", html)
            self.assertFalse(report["limitations"]["source_rights_verified"] if
                             "source_rights_verified" in report["limitations"]
                             else report["limitations"]["commercial_ai_rights_verified"])
        checked = p.verify_nvidia_audit_bundle(blob, expected_sha256=digest)
        self.assertEqual(checked["status"], "LOCAL_NVDA_BUNDLE_DIGEST_AND_REPLAY_PASS")
        self.assertFalse(checked["sec_original_authenticated"])
        self.assertFalse(checked["trade_executed"])

    def test_forged_source_audit_and_replay_not_accepted(self):
        invalid = actual_nvidia_issuer_receipt()
        invalid["source_sha256"] = "0" * 64
        self.assertEqual(self.real(receipt=invalid)["status"], "BLOCKED")
        self.assertFalse(self.db.exists())
        good = self.real()
        for field, value in (
            ("source_sha256", "0" * 64),
            ("financial_evidence_sha256", "0" * 64),
            ("source_rights_verified", True),
        ):
            bad = deepcopy(good)
            bad["report"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.build_nvidia_audit_bundle(bad)
        forged = deepcopy(good)
        forged["report"]["audit"]["event_hash"] = "f" * 64
        with self.assertRaises(ValueError):
            p.build_nvidia_audit_bundle(forged)

    def test_integrity_check_rejects_mutation_even_with_recomputed_zip_sha(self):
        blob, digest = p.build_nvidia_audit_bundle(self.real())
        with self.assertRaises(ValueError):
            p.verify_nvidia_audit_bundle(blob, expected_sha256="0" * 64)
        with ZipFile(BytesIO(blob), "r") as archived:
            parts = {x: archived.read(x) for x in archived.namelist()}
        data = json.loads(parts["review.json"])
        data["metrics"]["revenue_growth_pct"] = "999.99"
        parts["review.json"] = p._json(data)
        memory = BytesIO()
        with ZipFile(memory, "w", compression=ZIP_STORED) as modified:
            for name, value in parts.items():
                modified.writestr(name, value)
        changed = memory.getvalue()
        with self.assertRaises(ValueError):
            p.verify_nvidia_audit_bundle(changed,
                                         expected_sha256=sha256(changed).hexdigest())

    def test_noncanonical_zip_framing_rejected_even_with_matching_digest(self):
        blob, digest = p.build_nvidia_audit_bundle(self.real())
        self.assertEqual(p.verify_nvidia_audit_bundle(
            blob, expected_sha256=digest)["guard_decision"], "HOLD")
        for tampered in (blob + b"UNVERIFIED-TRAILER",
                         b"UNVERIFIED-PREFIX" + blob,
                         blob + blob):
            with self.subTest(length=len(tampered)):
                with self.assertRaisesRegex(ValueError, "NVDA_ZIP_NONCANONICAL_FRAMING"):
                    p.verify_nvidia_audit_bundle(
                        tampered, expected_sha256=sha256(tampered).hexdigest())

    def test_verification_cli_readonly_no_network_and_hash_required(self):
        blob, digest = p.build_nvidia_audit_bundle(self.real())
        self.out.write_bytes(blob)
        cmd = [sys.executable, "-B", "-m", "proofinvest.nvidia_audit_bundle",
               str(self.out), "--expected-sha256", digest]
        ok = subprocess.run(cmd, cwd=_APP.parent, text=True,
                            capture_output=True, timeout=20)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["guard_decision"], "HOLD")
        denied = subprocess.run(cmd[:-1]+["0"*64], cwd=_APP.parent, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(denied.returncode, 2, denied.stderr)

    def test_streamlit_download_only_after_actual_explicit_guard_click(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_APP)).run(timeout=25)
        at.selectbox[0].set_value(_MODE).run(timeout=25)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        consent = next(x for x in at.checkbox if x.key == "p211_nvda_local_audit_ack")
        consent.set_value(True).run(timeout=25)
        button = next(x for x in at.button if x.key == "p211_nvda_run_once")
        button.click().run(timeout=25)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("NVIDIA 실자료 Guard HOLD 감사 체인 검증 완료" in x.value
                            for x in at.success))
        self.assertTrue(any("ZIP SHA-256" in x.value for x in at.caption))


if __name__ == "__main__":
    unittest.main()
