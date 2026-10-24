"""Offline byte-identity guard for the privately frozen KIC preliminary PDF.

This check never uploads, rewrites, parses, or prints the PDF or its local path.
It confirms a PDF-eligible filename, conservative size bound, and exact
byte identity with the privately reviewed candidate. It cannot prove actual
DAKER upload permissions, backend acceptance, or a final submission receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

FROZEN_SHA256 = "0bdbbf04f374a7ccb39cd15e1aa700a006514278b094d32bb05ac7db610e034e"
FROZEN_BYTES = 513_113
FROZEN_PAGE_COUNT_FROM_PRIOR_AUDIT = 10
# DAKER form says PDF uploads only, max 20 MB. Decimal MB is the
# conservative bound when the site's exact MB interpretation is unknown.
DAKER_MAX_UPLOAD_BYTES = 20_000_000


def verify_candidate(
    path: Path,
    *,
    expected_sha256: str = FROZEN_SHA256,
    expected_bytes: int = FROZEN_BYTES,
) -> dict[str, object]:
    """Verify bytes against a pinned receipt, without reading PDF page contents.

    Optional expected values exist for synthetic unit tests only. The public
    CLI always uses the unmodified pinned values above.
    """
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Invalid expected digest")
    if expected_bytes <= 0:
        raise ValueError("Invalid expected byte count")
    path = Path(path).expanduser()
    if path.is_symlink():
        raise ValueError("Symlinked PDF not allowed")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError("PDF unavailable or inaccessible") from exc
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError("PDF must be an ordinary file")
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        if path.suffix.lower() != ".pdf":
            return _result(False, "PDF_EXTENSION_REQUIRED")
        if meta.st_size > DAKER_MAX_UPLOAD_BYTES:
            return _result(False, "DAKER_PDF_SIZE_LIMIT_EXCEEDED")
        if meta.st_size != expected_bytes:
            return _result(False, "BYTE_SIZE_MISMATCH")
        first = stream.read(5)
        if first != b"%PDF-":
            return _result(False, "INVALID_PDF_HEADER")
        digest = hashlib.sha256()
        digest.update(first)
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            return _result(False, "CHECKSUM_MISMATCH")
    return _result(True, "PINNED_FROZEN_PDF_MATCH")


def _result(ok: bool, reason: str) -> dict[str, object]:
    return {
        "decision": "READY_FOR_USER_REVIEW_NOT_SUBMITTED" if ok else "DO_NOT_UPLOAD",
        "reason": reason,
        "matched_pinned_byte_identity": ok,
        "page_count_rechecked_in_this_run": False,
        "prior_private_audit_page_count": FROZEN_PAGE_COUNT_FROM_PRIOR_AUDIT,
        "daker_upload_authority_verified": False,
        "officially_submitted": False,
        "receipt_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only offline KIC frozen PDF byte-identity preflight")
    parser.add_argument("pdf", type=Path, help="Local private PDF path (not uploaded or logged)")
    args = parser.parse_args()
    try:
        verdict = verify_candidate(args.pdf)
    except ValueError as exc:
        verdict = _result(False, str(exc))
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["matched_pinned_byte_identity"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
