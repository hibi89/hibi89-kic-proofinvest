"""P94 operator-held SEC ZIP intake: real source shape, synthetic fixtures only.

No SEC HTTP, original file persistence, archive extraction or automatic Guard.
"""
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
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED, ZipInfo
import stat
import warnings

from proofinvest.operator_sec_zip import (
    _MAX_ZIP_BYTES, make_operator_sec_zip_bytes, read_operator_sec_zip_bytes,
    read_operator_sec_zip_file, inspect_operator_sec_zip_bytes,
    save_new_operator_sec_zip,
)
from proofinvest.kuodra_local_workspace import (
    preview_uploaded_triplet, review_uploaded_triplet,
)
from proofinvest.kuodra_local_workspace_ui import _selected_workspace_sources
from proofinvest.real_data_preflight import inspect_offline_data_files
from tests.test_sec_bundle_replay import fixture
from tests.test_real_data_preflight_auto_industry import build_args
from proofinvest.kic_dl_original_demo import PHRASE


def inputs():
    receipt, raws = fixture()
    claims = {
        "issuer_cik": receipt["issuer_cik"],
        "accession": receipt["accession"],
        "as_of": receipt["observed_utc_day"],
        "collected_at": receipt["submissions_observed_at_utc"],
    }
    return raws, claims


def zipped():
    raw, claims = inputs()
    return make_operator_sec_zip_bytes(**raw, **claims)


def rebuild(data: bytes, *, replace=None, add=None, method=ZIP_STORED,
            symbolic=None):
    with ZipFile(BytesIO(data)) as saved:
        original = {name: saved.read(name) for name in saved.namelist()}
    if replace:
        original.update(replace)
    with BytesIO() as out:
        with ZipFile(out, "w") as archive:
            for name, payload in original.items():
                entry = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = method
                if name == symbolic:
                    entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, payload)
            if add is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(add[0], add[1])
        return out.getvalue()


class Uploaded:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.size = len(raw)

    def getvalue(self):
        return self.raw


class OperatorIntakeTests(unittest.TestCase):
    def test_4_exact_entries_roundtrip_deterministic_source_pins_no_io(self):
        sources, claims = inputs()
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_HTTP")) as web:
            first = make_operator_sec_zip_bytes(**sources, **claims)
            second = make_operator_sec_zip_bytes(**sources, **claims)
            replay, declared = read_operator_sec_zip_bytes(first)
            check = inspect_operator_sec_zip_bytes(first)
        web.assert_not_called()
        self.assertEqual(first, second)
        self.assertEqual(replay, sources)
        self.assertEqual(declared, claims)
        with ZipFile(BytesIO(first)) as archive:
            self.assertEqual(sorted(archive.namelist()), [
                "companyfacts.json", "manifest.json",
                "original_filing.bin", "submissions.json",
            ])
            self.assertTrue(all(i.compress_type == ZIP_STORED
                                for i in archive.infolist()))
        self.assertEqual(check["archive_sha256"], sha256(first).hexdigest())
        self.assertEqual(check["source_sha256"], {
            key: sha256(value).hexdigest() for key, value in sources.items()
        })
        self.assertFalse(check["transport_http_performed"])
        self.assertFalse(check["sec_origin_authenticated"])
        self.assertFalse(check["source_rights_verified"])
        self.assertFalse(check["audit_written"])
        self.assertFalse(check["official_submission"])
        self.assertNotIn(PHRASE, json.dumps(check))
        self.assertNotIn("synthetic10k", json.dumps(check))

    def test_existing_guard_receipt_preview_and_no_network_or_retention(self):
        raw, claims = inputs()
        archive = zipped()
        result, claim = read_operator_sec_zip_bytes(archive)
        request = {
            "cik": claim["issuer_cik"], "accession": claim["accession"],
            "as_of": claim["as_of"], "collected_at": claim["collected_at"],
            "current_end": "2025-09-30", "prior_end": "2024-09-30",
            "needle": PHRASE, "claimed_growth_pct": None,
        }
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("EXTERNAL_HTTP_FORBIDDEN")) as web:
            preview = preview_uploaded_triplet(result, request)
            with self.assertRaisesRegex(ValueError, "EXPLICIT_EPHEMERAL_AUDIT_CONSENT"):
                review_uploaded_triplet(
                    result, request, expected_preview=preview, consent=False)
            guard, html = review_uploaded_triplet(
                result, request, expected_preview=preview, consent=True)
        web.assert_not_called()
        self.assertEqual(preview["source_sha256"], {
            key: sha256(value).hexdigest() for key, value in raw.items()
        })
        self.assertEqual(guard["guard"]["decision"], "HOLD")
        self.assertTrue(html.lower().startswith(b"<!doctype html"))
        self.assertEqual(read_operator_sec_zip_bytes(archive)[0], raw)
        self.assertFalse(guard["limits"]["external_source_authenticated"])
        self.assertFalse(guard["limits"]["live_api_called"])
        self.assertFalse(guard["limits"]["trade_executed"])

    def test_owner_source_zip_integrates_real_preflight_a_b_c_without_http(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            opts, archive, market, sector, peer = build_args(root)
            operator_archive = root / "operator-sec-input.zip"
            operator_archive.write_bytes(zipped())
            before = {
                f.name: sha256(f.read_bytes()).hexdigest()
                for f in root.iterdir()
            }
            opts["sec_bundle"] = None
            opts["operator_sec_zip"] = operator_archive
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("NO_HTTP")) as web:
                report = inspect_offline_data_files(**opts)
            web.assert_not_called()
            self.assertEqual(report["status"],
                             "local_structure_pass_origin_unverified", report)
            self.assertEqual(report["sec_input_mode"],
                             "OPERATOR_LOCAL_ZIP_NO_HTTP_UNAUTHENTICATED")
            self.assertTrue(report["operator_sec_zip_integrity_matched"])
            self.assertFalse(report["sec_capture_digest_matched"])
            self.assertEqual(report["market_status"], "REPORTED_UNVERIFIED")
            self.assertTrue(report["all_three_inputs_present"])
            self.assertEqual(report["industry_input_mode"],
                             "LOCAL_ORIGINALS_DERIVED_NO_SAVE")
            self.assertEqual(report["peer_sec_companyfacts_check"]["peer_count"], 1)
            self.assertFalse(report["source_authenticated"])
            self.assertFalse(report["three_engine_real_world_validated"])
            self.assertFalse(report["data_rights_verified"])
            self.assertFalse(report["external_http_called"])
            self.assertFalse(report["audit_retained"])
            self.assertEqual(
                before,
                {f.name: sha256(f.read_bytes()).hexdigest()
                 for f in root.iterdir()},
            )

    def test_zip_exact_mode_required_no_mixed_source_paths(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            options, archive, *_ = build_args(root)
            own = root / "operator.zip"
            own.write_bytes(zipped())
            options["operator_sec_zip"] = own
            self.assertEqual(
                inspect_offline_data_files(**options)["reason_code"],
                "MIXED_SEC_INPUT_MODES_BLOCKED",
            )
            options["sec_bundle"] = None
            options["issuer_cik"] = inputs()[1]["issuer_cik"]
            self.assertEqual(
                inspect_offline_data_files(**options)["reason_code"],
                "MIXED_SEC_INPUT_MODES_BLOCKED",
            )

    def test_bad_manifest_SHA_mutation_trust_upgrade_and_duplicate_keys_block(self):
        base = zipped()
        with ZipFile(BytesIO(base)) as old:
            meta = json.loads(old.read("manifest.json"))
        for kind in ("sha", "authenticated", "clock", "duplicate"):
            changed = json.loads(json.dumps(meta))
            if kind == "sha":
                changed["entries"]["original_filing"]["sha256"] = "0" * 64
            elif kind == "authenticated":
                changed["origin_authenticated"] = True
            elif kind == "clock":
                changed["operator_claims"]["collected_at"] = "2025-10-17T00:00:00Z"
            raw = (b'{"schema":"x","schema":"y"}' if kind == "duplicate"
                   else json.dumps(changed).encode())
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                read_operator_sec_zip_bytes(
                    rebuild(base, replace={"manifest.json": raw})
                )

    def test_malicious_zip_entries_duplicate_traversal_compression_symlink_block(self):
        base = zipped()
        variants = {
            "duplicated": rebuild(
                base, add=("submissions.json", b"FORGED")),
            "traversal": rebuild(
                base, add=("../../private.txt", b"NEVER_WRITE")),
            "compressed": rebuild(base, method=ZIP_DEFLATED),
            "symlink": rebuild(base, symbolic="original_filing.bin"),
            "missing": rebuild(base, replace={"original_filing.bin": b""}),
        }
        for label, blob in variants.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                read_operator_sec_zip_bytes(blob)
        with self.assertRaises(ValueError):
            read_operator_sec_zip_bytes(b"PK\x03\x04" + b"X" * (_MAX_ZIP_BYTES + 1))

    def test_invalid_input_issuer_clock_and_wrong_json_rejected_before_pack(self):
        originals, claims = inputs()
        bad = dict(claims, as_of="2025-10-17")
        with self.assertRaises(ValueError):
            make_operator_sec_zip_bytes(**originals, **bad)
        bad = dict(claims, collected_at="2025-10-16T12:00:00")
        with self.assertRaises(ValueError):
            make_operator_sec_zip_bytes(**originals, **bad)
        invalid = dict(originals, companyfacts=b'{"cik":999999}')
        with self.assertRaises(ValueError):
            make_operator_sec_zip_bytes(**invalid, **claims)

    def test_ui_read_only_upload_mode_and_claim_change_guard(self):
        raw, claims = inputs()
        upload = Uploaded(zipped())
        manual = {
            "submissions": None, "companyfacts": None,
            "original_filing": None, "history_page": None,
        }
        request = {
            "cik": claims["issuer_cik"], "accession": claims["accession"],
            "as_of": claims["as_of"], "collected_at": claims["collected_at"],
        }
        self.assertEqual(_selected_workspace_sources(
            manual, upload, request=request), raw)
        tampered = dict(request, as_of="2025-10-17")
        with self.assertRaisesRegex(ValueError, "DECLARED_IDENTITY_OR_CLOCK_CHANGED"):
            _selected_workspace_sources(manual, upload, request=tampered)
        mixed = dict(manual, submissions=Uploaded(raw["submissions"]))
        with self.assertRaisesRegex(ValueError, "CANNOT_MIX"):
            _selected_workspace_sources(mixed, upload, request=request)

    def test_explicit_pack_cli_rejects_overwrite_and_keeps_originals(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            sources, claims = inputs()
            paths = {}
            for key, raw in sources.items():
                path = root / (key + ".input")
                path.write_bytes(raw)
                paths[key] = path
            before = {key: sha256(path.read_bytes()).hexdigest()
                      for key, path in paths.items()}
            dest = root / "operator.zip"
            cmd = [
                sys.executable, "-m", "proofinvest.operator_sec_zip", "pack",
                "--submissions", str(paths["submissions"]),
                "--companyfacts", str(paths["companyfacts"]),
                "--original-filing", str(paths["original_filing"]),
                "--issuer-cik", claims["issuer_cik"],
                "--accession", claims["accession"],
                "--as-of", claims["as_of"],
                "--collected-at", claims["collected_at"],
                "--output", str(dest),
            ]
            created = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            exported = json.loads(created.stdout)
            self.assertEqual(exported["status"], "operator_zip_created_origin_unverified")
            self.assertEqual(exported["output_sha256"], sha256(dest.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):
                save_new_operator_sec_zip(
                    dest, sources=sources, claims=claims)
            retry = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            self.assertEqual(retry.returncode, 2)
            self.assertEqual(json.loads(retry.stdout)["status"], "blocked")
            inspected = subprocess.run(
                [sys.executable, "-m", "proofinvest.operator_sec_zip",
                 "inspect", "--zip", str(dest)],
                capture_output=True, text=True, timeout=40,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout)["archive_sha256"],
                             exported["output_sha256"])
            self.assertNotIn(str(root), inspected.stdout)
            self.assertNotIn(PHRASE, inspected.stdout)
            self.assertEqual(before, {
                key: sha256(path.read_bytes()).hexdigest()
                for key, path in paths.items()
            })

    def test_input_zip_symlink_rejected_without_touching_target(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "owner.zip"
            original.write_bytes(zipped())
            alternate = root / "link.zip"
            try:
                alternate.symlink_to(original)
            except (OSError, NotImplementedError):
                self.skipTest("symlink unavailable")
            with self.assertRaises(ValueError):
                read_operator_sec_zip_file(alternate)
            self.assertEqual(original.read_bytes(), zipped())


if __name__ == "__main__":
    unittest.main()
