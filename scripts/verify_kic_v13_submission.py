"""Offline, read-only byte-identity and layout preflight for frozen KUODRA V13.

Safe to publish: source code and expected digest only. The private PDF is never
bundled, copied, written, uploaded, or submitted by this tool. A PASS is NOT a
DAKER acceptance receipt, issuer authentication, or license clearance.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import unicodedata

EXPECTED_NAME = "KIC_KUODRA_V13_PRIVATE_GUARD_CONSISTENCY_20261101.pdf"
EXPECTED_BYTES = 562176
EXPECTED_SHA256 = "64810314b4fc8699f0c56087b8ad39c4da5658d243585e0500900f1b4b3f7ece"
REQUIRED = {
    2: ("Summary",),
    3: ("문제정의",),
    4: ("서비스제안",),
    5: ("AIAgent", "구성"),
    7: ("데이터활용계획",),
    8: ("MVP", "개발계획"),
    9: ("기대효과",),
}
EXPECTED_LINKS = frozenset({
    "https://daker.ai/public/hackathons/kic-ai-agent-competition",
    "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm",
    "https://www.sec.gov/about/developer-resources",
    "https://github.com/hibi89/hibi89-kic-proofinvest/tree/lead/kic",
    "https://github.com/hibi89/hibi89-kic-proofinvest/actions/runs/41236018194",
})


class PreflightBlocked(ValueError):
    """Only fixed non-private reason codes are returned to the caller."""


def _compact(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def verify(pdf: Path) -> dict[str, object]:
    """Validate an operator-selected existing file; never write or make HTTP calls."""
    if not isinstance(pdf, Path) or pdf.name != EXPECTED_NAME or pdf.is_symlink():
        raise PreflightBlocked("WRONG_PDF_FILENAME_OR_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(pdf, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != EXPECTED_BYTES:
            raise PreflightBlocked("PDF_SIZE_OR_TYPE_CHANGED")
        data = stream.read(EXPECTED_BYTES + 1)
    if len(data) != EXPECTED_BYTES or sha256(data).hexdigest() != EXPECTED_SHA256:
        raise PreflightBlocked("PDF_SHA256_MISMATCH")
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-256:]:
        raise PreflightBlocked("INVALID_PDF_MAGIC_OR_TRAILER")

    try:
        import fitz
    except ImportError:
        raise PreflightBlocked("PYMUPDF_REQUIRED_FOR_FULL_QA") from None
    with fitz.open(stream=data, filetype="pdf") as doc:
        if doc.is_encrypted or len(doc) != 10:
            raise PreflightBlocked("PDF_ENCRYPTED_OR_NOT_TEN_PAGES")
        for number, parts in REQUIRED.items():
            text = _compact(doc[number - 1].get_text())
            if not all(_compact(part) in text for part in parts):
                raise PreflightBlocked("MISSING_REQUIRED_SECTION_PAGE_" + str(number))
        links = []
        for page in doc:
            for word in page.get_text("words"):
                x0, y0, x1, y1 = word[:4]
                if (x0 < -1 or y0 < -1
                        or x1 > page.rect.width + 1
                        or y1 > page.rect.height + 1):
                    raise PreflightBlocked("PDF_TEXT_OUTSIDE_PAGE")
            links.extend(page.get_links())
        if (len(links) != 5 or {link.get("uri") for link in links} != EXPECTED_LINKS
                or any(link.get("kind") != fitz.LINK_URI for link in links)):
            raise PreflightBlocked("PDF_LINK_SET_CHANGED")
    return {
        "status": "EXACT_V13_OFFLINE_PREFLIGHT_PASS_NOT_SUBMITTED",
        "filename": EXPECTED_NAME, "sha256": EXPECTED_SHA256,
        "size_bytes": EXPECTED_BYTES, "page_count": 10,
        "required_sections": 7, "hyperlinks": 5,
        "owner_approved": False, "daker_submission_confirmed": False,
        "official_template_binary_verified": False,
        "sec_origin_verified": False, "rights_verified": False,
        "network_requests": 0, "original_file_modified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only KUODRA exact V13 PDF checker; no DAKER submission")
    parser.add_argument("--pdf", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.pdf)
    except PreflightBlocked as exc:
        result = {"status": "BLOCKED", "reason_code": str(exc),
                  "daker_submission_confirmed": False}
        code = 2
    except Exception:
        # No exception message: OS/PDF parser may otherwise disclose local paths.
        result = {"status": "BLOCKED", "reason_code": "PDF_OPEN_OR_PARSER_FAILED",
                  "daker_submission_confirmed": False}
        code = 2
    else:
        code = 0
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
