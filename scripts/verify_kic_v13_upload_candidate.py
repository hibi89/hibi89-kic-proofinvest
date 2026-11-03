"""KIC KUODRA V13 pre-upload byte validator (Python 3.11+, stdlib only).

Read-only. Never changes, transmits, uploads, or submits the PDF. A PASS means
local file bytes match the approved frozen PDF, NOT a DAKER receipt.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys

EXPECTED_NAME = "KIC_KUODRA_V13_PRIVATE_GUARD_CONSISTENCY_20261101.pdf"
EXPECTED_SIZE = 562176
EXPECTED_SHA256 = "64810314b4fc8699f0c56087b8ad39c4da5658d243585e0500900f1b4b3f7ece"


class Blocked(ValueError):
    """Safe fixed failure reason code; does not disclose a path or document."""


def verify(path: Path) -> dict[str, object]:
    if not isinstance(path, Path) or path.name != EXPECTED_NAME:
        raise Blocked("WRONG_FILE_NAME")
    try:
        meta = path.lstat()
    except OSError:
        raise Blocked("FILE_NOT_ACCESSIBLE") from None
    if (not stat.S_ISREG(meta.st_mode)
            or bool(getattr(meta, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))):
        raise Blocked("FILE_LINK_OR_NOT_REGULAR")
    if meta.st_size != EXPECTED_SIZE:
        raise Blocked("FILE_SIZE_MISMATCH")
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as src:
            opened = os.fstat(src.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size != EXPECTED_SIZE:
                raise Blocked("FILE_SIZE_OR_TYPE_CHANGED")
            raw = src.read(EXPECTED_SIZE + 1)
    except Blocked:
        raise
    except (OSError, PermissionError):
        raise Blocked("FILE_READ_FAILED") from None
    if len(raw) != EXPECTED_SIZE or sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise Blocked("FILE_SHA256_MISMATCH")
    if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-256:]:
        raise Blocked("PDF_SIGNATURE_INVALID")
    return {
        "status": "EXACT_APPROVED_V13_BYTES_PASS_NOT_SUBMITTED",
        "filename": EXPECTED_NAME,
        "bytes": EXPECTED_SIZE,
        "sha256": EXPECTED_SHA256,
        "daker_submitted": False,
        "owner_document_approval_recorded": True,
        "pdf_layout_tested_here": False,
        "file_changed": False,
        "network_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify exact approved V13 PDF before DAKER upload, offline")
    parser.add_argument("--pdf", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.pdf)
    except Blocked as err:
        result = {"status": "BLOCKED", "reason_code": str(err), "daker_submitted": False}
        code = 2
    except Exception:
        result = {"status": "BLOCKED", "reason_code": "UNEXPECTED_LOCAL_ERROR", "daker_submitted": False}
        code = 2
    else:
        code = 0
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
