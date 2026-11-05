"""Read-only verifier for user-owned offline KUODRA report bundles.

Expected SHA-256 must be independently retained from original export receipt.
Matching bytes/HTML/manifest is NOT SEC publisher or data-rights authentication.
Does not extract, write, query external services or execute arbitrary scripts.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
from zipfile import ZipFile, BadZipFile, LargeZipFile

from .local_report_bundle import _MAX_ARCHIVE, _MAX_REPORT_PART
from .local_sec_html_report import render_local_sec_html

_NAMES = frozenset(("report.json", "report.html", "manifest.json"))
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_MANIFEST_MAX = 8192
_FALSE_FLAGS = (
    "source_authenticated", "data_rights_verified",
    "historical_market_vintage_authenticated", "real_data_verified",
    "audit_retained", "external_http_called", "trade_executed",
)


def _read_original_file(path: Path) -> bytes:
    if not isinstance(path, Path) or path.suffix.lower() != ".zip":
        raise ValueError("ZIP_PATH_REQUIRED")
    if path.is_symlink():
        raise ValueError("ZIP_SYMLINK_BLOCKED")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= _MAX_ARCHIVE:
            raise ValueError("ZIP_NOT_BOUNDED_REGULAR_FILE")
        data = stream.read(_MAX_ARCHIVE + 1)
        if not 0 < len(data) <= _MAX_ARCHIVE or len(data) != metadata.st_size:
            raise ValueError("ZIP_BOUNDED_READ_CONFLICT")
    return data


def verify_local_report_bundle(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Fail closed on identity, ZIP structure, canonical manifest and HTML."""
    if (type(expected_sha256) is not str
            or _SHA.fullmatch(expected_sha256) is None):
        raise ValueError("EXPECTED_RECEIPT_SHA256_REQUIRED")
    payload = _read_original_file(path)
    digest = sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise ValueError("ZIP_RECEIPT_SHA256_MISMATCH")
    # Reject prefixed/trailing payloads even when an attacker supplies a new
    # matching digest. Exporter writes an ordinary ZIP with no archive comment.
    if (not payload.startswith(b"PK\x03\x04")
            or len(payload) < 22
            or payload[-22:-18] != b"PK\x05\x06"
            or payload[-2:] != b"\x00\x00"):
        raise ValueError("ZIP_NONCANONICAL_ENVELOPE")
    with ZipFile(BytesIO(payload), mode="r") as archive:
        entries = archive.infolist()
        if (len(entries) != 3
                or set(x.filename for x in entries) != _NAMES
                or any(x.is_dir() or x.flag_bits & 1 or x.file_size <= 0
                       or x.file_size > (_MANIFEST_MAX if x.filename == "manifest.json"
                                         else _MAX_REPORT_PART)
                       for x in entries)):
            raise ValueError("ZIP_ENTRY_SET_OR_BOUNDS_INVALID")
        parts = {x.filename: archive.read(x) for x in entries}
    try:
        manifest = json.loads(parts["manifest.json"].decode("utf-8"))
        report = json.loads(parts["report.json"].decode("utf-8"))
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ValueError("ZIP_JSON_INVALID") from None
    if (type(manifest) is not dict or type(report) is not dict
            or manifest.get("schema") != "kuodra.offline-local-report-bundle.v1"
            or manifest.get("status") != "LOCAL_REPORT_EXPORTED_ORIGIN_UNVERIFIED"
            or set(manifest) != {"schema","status","guard_decision",
                                 "all_three_inputs_present",*_FALSE_FLAGS,"files"}
            or any(manifest.get(k) is not False for k in _FALSE_FLAGS)
            or type(manifest.get("all_three_inputs_present")) is not bool
            or manifest.get("guard_decision") not in ("HOLD", "REJECT")
            or type(manifest.get("files")) is not dict
            or set(manifest["files"]) != {"report.json", "report.html"}):
        raise ValueError("ZIP_MANIFEST_TRUST_OR_SCHEMA_INVALID")
    if (parts["manifest.json"] != json.dumps(
            manifest, ensure_ascii=True, sort_keys=True, indent=2
        ).encode("utf-8")
        or parts["report.json"] != json.dumps(
            report, ensure_ascii=True, sort_keys=True, indent=2,
            allow_nan=False,
        ).encode("utf-8")):
        raise ValueError("ZIP_NONCANONICAL_JSON_BLOCKED")
    guard, ledger = report.get("guard"), report.get("three_engine_summary")
    if (type(guard) is not dict or type(ledger) is not dict
            or guard.get("decision") != manifest["guard_decision"]
            or guard.get("source_authenticated") is not False
            or ledger.get("all_three_inputs_present")
                 is not manifest["all_three_inputs_present"]):
        raise ValueError("ZIP_GUARD_LEDGER_CONTRACT_INVALID")
    for name in ("report.json", "report.html"):
        meta = manifest["files"][name]
        if (type(meta) is not dict or set(meta) != {"sha256", "bytes"}
                or type(meta["bytes"]) is not int
                or meta["bytes"] != len(parts[name])
                or type(meta["sha256"]) is not str
                or meta["sha256"] != sha256(parts[name]).hexdigest()):
            raise ValueError("ZIP_PART_DIGEST_MISMATCH")
    if render_local_sec_html(report) != parts["report.html"]:
        raise ValueError("ZIP_HTML_REPLAY_MISMATCH")
    return {
        "schema": "kuodra.offline-report-bundle-verification.v1",
        "status": "LOCAL_ZIP_BYTES_MATCH_RECEIPT_ORIGIN_UNVERIFIED",
        "bundle_sha256": digest,
        "report_json_sha256": manifest["files"]["report.json"]["sha256"],
        "report_html_sha256": manifest["files"]["report.html"]["sha256"],
        "guard_decision": guard["decision"],
        "all_three_inputs_present": ledger["all_three_inputs_present"],
        "original_source_authenticated": False,
        "data_rights_verified": False,
        "point_in_time_authenticated": False,
        "real_world_three_engine_verified": False,
        "live_api_called": False,
        "audit_retained": False,
        "trade_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only, receipt-pinned KUODRA ZIP check")
    parser.add_argument("archive", type=Path, help="Owner-held report ZIP path")
    parser.add_argument("--expected-sha256", required=True,
                        help="SHA-256 saved separately from the original export receipt")
    args = parser.parse_args(argv)
    try:
        result = verify_local_report_bundle(args.archive, args.expected_sha256)
    except (OSError, ValueError, TypeError, BadZipFile, LargeZipFile,
            RuntimeError, OverflowError, UnicodeError):
        result = {
            "schema": "kuodra.offline-report-bundle-verification.v1",
            "status": "BLOCKED",
            "reason_code": "REPORT_ZIP_INTEGRITY_OR_TRUST_FAILED",
            "original_source_authenticated": False,
            "live_api_called": False,
            "trade_executed": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
