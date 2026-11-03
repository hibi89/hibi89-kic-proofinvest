"""P134: offline, read-only verifier for the exact P133 KUODRA V13 transfer ZIP.

This checks ZIP transport and inner PDF byte identity, NOT PDF page/layout,
external provenance, user approval, DAKER account state, or official submission.
Never extracts, saves, uploads, calls HTTP, or changes source archives.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import sys
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZIP_STORED

ARCHIVE_NAME = "KIC_P133_VERIFIED_V13_EXACT_ORIGINAL.zip"
ARCHIVE_BYTES = 562604
ARCHIVE_SHA256 = "743d22f28a77343f83d2d3a56f7882318b277d86cc8bf47a35858e4b3bea596d"
PDF_NAME = "KIC_KUODRA_V13_PRIVATE_GUARD_CONSISTENCY_20261101.pdf"
PDF_BYTES = 562176
PDF_SHA256 = "64810314b4fc8699f0c56087b8ad39c4da5658d243585e0500900f1b4b3f7ece"
SUM_NAME = "SHA256SUMS.txt"


class TransferBlocked(ValueError):
    """Only fixed safe reason codes are used."""


def verify(archive_path: Path) -> dict[str, object]:
    """Fail closed on exact outer ZIP and embedded PDF, without extraction."""
    if (not isinstance(archive_path, Path) or archive_path.name != ARCHIVE_NAME
            or archive_path.is_symlink()):
        raise TransferBlocked("WRONG_ZIP_NAME_OR_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(archive_path, flags), "rb") as fh:
        stat_info = os.fstat(fh.fileno())
        if (not stat.S_ISREG(stat_info.st_mode)
                or stat_info.st_size != ARCHIVE_BYTES):
            raise TransferBlocked("ZIP_SIZE_OR_TYPE_CHANGED")
        archive = fh.read(ARCHIVE_BYTES + 1)
    if len(archive) != ARCHIVE_BYTES or sha256(archive).hexdigest() != ARCHIVE_SHA256:
        raise TransferBlocked("ZIP_SHA256_MISMATCH")
    try:
        with ZipFile(BytesIO(archive), mode="r") as zip_file:
            entries = zip_file.infolist()
            if (len(entries) != 2
                    or {entry.filename for entry in entries} != {PDF_NAME, SUM_NAME}
                    or any(entry.is_dir() or entry.flag_bits & 1
                           or entry.compress_type != ZIP_STORED
                           or entry.file_size <= 0
                           for entry in entries)):
                raise TransferBlocked("ZIP_MEMBERS_UNEXPECTED")
            by_name = {entry.filename: entry for entry in entries}
            if (by_name[PDF_NAME].file_size != PDF_BYTES
                    or by_name[SUM_NAME].file_size != len(
                        (PDF_SHA256 + "  " + PDF_NAME + "\n").encode("utf-8"))):
                raise TransferBlocked("ZIP_INNER_SIZE_CHANGED")
            original = zip_file.read(PDF_NAME)
            checksum_file = zip_file.read(SUM_NAME)
    except (BadZipFile, LargeZipFile, OSError, EOFError, RuntimeError):
        raise TransferBlocked("ZIP_UNREADABLE") from None
    if len(original) != PDF_BYTES or sha256(original).hexdigest() != PDF_SHA256:
        raise TransferBlocked("ZIP_INNER_PDF_HASH_MISMATCH")
    if checksum_file != (PDF_SHA256 + "  " + PDF_NAME + "\n").encode("utf-8"):
        raise TransferBlocked("ZIP_CHECKSUM_MANIFEST_MISMATCH")
    if not original.startswith(b"%PDF-") or b"%%EOF" not in original[-256:]:
        raise TransferBlocked("ZIP_INNER_PDF_SIGNATURE_INVALID")
    return {
        "status": "EXACT_P133_V13_ZIP_AND_PDF_BYTES_PASS_NOT_SUBMITTED",
        "archive_sha256": ARCHIVE_SHA256,
        "archive_bytes": ARCHIVE_BYTES,
        "pdf_sha256": PDF_SHA256,
        "pdf_bytes": PDF_BYTES,
        "zip_members_verified": 2,
        "owner_approved": False,
        "daker_submission_confirmed": False,
        "pdf_layout_verified_by_zip_checker": False,
        "issuer_origin_authenticated": False,
        "source_rights_verified": False,
        "network_requests": 0,
        "disk_writes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify pinned KIC V13 ZIP without extraction or upload")
    parser.add_argument("--zip", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.zip)
    except TransferBlocked as exc:
        result = {"status": "BLOCKED", "reason_code": str(exc),
                  "daker_submission_confirmed": False}
        exit_code = 2
    except Exception:
        result = {"status": "BLOCKED", "reason_code": "ZIP_READ_FAILED",
                  "daker_submission_confirmed": False}
        exit_code = 2
    else:
        exit_code = 0
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
