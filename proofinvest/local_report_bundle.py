"""Explicit opt-in local ZIP export of a completed KUODRA offline report.

No HTTP/API or provider attestation. Never creates a report by default.
One user-chosen new ZIP only; refuses overwrite; immutable synthetic evidence
claims are never promoted to real issuer/source/market authentication.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from typing import Any

_MAX_REPORT_PART = 12_000_000
_MAX_ARCHIVE = 24_000_000


def _pack(name: str, payload: bytes, zipfile: ZipFile) -> None:
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o600 << 16
    zipfile.writestr(entry, payload)


def write_new_local_report_bundle(
    path: Path, report: dict[str, Any], html: bytes,
) -> str:
    """Create one ZIP if and only if the Guard/UI report is consistent.

    Returns SHA-256 of exact ZIP bytes. Refuses pre-existing file/symlink.
    Never writes a second file or a real persistent SQLite audit.
    """
    if not isinstance(path, Path) or path.suffix.lower() != ".zip":
        raise ValueError("REPORT_ZIP_SUFFIX_REQUIRED")
    if type(report) is not dict or type(html) is not bytes:
        raise ValueError("INVALID_REPORT_TYPES")
    guard = report.get("guard")
    ledger = report.get("three_engine_summary")
    if (type(guard) is not dict or type(ledger) is not dict
            or guard.get("decision") not in ("HOLD", "REJECT")
            or guard.get("source_authenticated") is not False
            or ledger.get("all_three_inputs_present") is None
            or not html.startswith(b"<!DOCTYPE html")):
        raise ValueError("REPORT_GUARD_OR_HTML_INVALID")
    try:
        json_bytes = json.dumps(
            report, ensure_ascii=True, sort_keys=True, indent=2,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValueError("REPORT_JSON_SERIALIZATION_BLOCKED") from None
    if (not 0 < len(json_bytes) <= _MAX_REPORT_PART
            or not 0 < len(html) <= _MAX_REPORT_PART):
        raise ValueError("REPORT_PART_SIZE_INVALID")
    summary = {
        "schema": "kuodra.offline-local-report-bundle.v1",
        "status": "LOCAL_REPORT_EXPORTED_ORIGIN_UNVERIFIED",
        "guard_decision": guard["decision"],
        "all_three_inputs_present": ledger["all_three_inputs_present"],
        "source_authenticated": False,
        "data_rights_verified": False,
        "historical_market_vintage_authenticated": False,
        "real_data_verified": False,
        "audit_retained": False,
        "external_http_called": False,
        "trade_executed": False,
        "files": {
            "report.json": {
                "sha256": sha256(json_bytes).hexdigest(),
                "bytes": len(json_bytes),
            },
            "report.html": {
                "sha256": sha256(html).hexdigest(),
                "bytes": len(html),
            },
        },
    }
    manifest = json.dumps(summary, ensure_ascii=True,
                          sort_keys=True, indent=2).encode("utf-8")
    buffer = BytesIO()
    with ZipFile(buffer, mode="w") as zf:
        _pack("report.json", json_bytes, zf)
        _pack("report.html", html, zf)
        _pack("manifest.json", manifest, zf)
    archive = buffer.getvalue()
    if not 0 < len(archive) <= _MAX_ARCHIVE:
        raise ValueError("REPORT_ZIP_SIZE_INVALID")
    if path.is_symlink():
        raise ValueError("REPORT_ZIP_SYMLINK_REJECTED")
    # O_EXCL refuses an existing original, report or symlink, including a
    # concurrently created destination. No other filesystem path is changed.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    created = True
    try:
        with os.fdopen(fd, "wb") as dest:
            dest.write(archive)
            dest.flush()
            os.fsync(dest.fileno())
    except BaseException:
        # Only delete the newly created output if it is still the same inode.
        # Never delete a preexisting or concurrently replaced original file.
        if created:
            try:
                if os.stat(path, follow_symlinks=False).st_ino == os.fstat(fd).st_ino:
                    os.unlink(path)
            except (OSError, ValueError):
                pass
        raise
    return sha256(archive).hexdigest()
