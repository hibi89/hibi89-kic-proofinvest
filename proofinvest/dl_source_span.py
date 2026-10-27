"""Read-only KIC byte-span reference for locally archived DL originals.

Stored HTML is always untrusted. This function never executes HTML, calls
HTTP, extracts SEC-verified financial facts, or certifies an issuer/source.
Byte offsets are over exact archived bytes; displayed context is escaped.
"""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Any

from disclosure_lightning.originals import (
    list_originals, locate_original, read_original_bytes,
)

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PROVENANCES = frozenset({"OFFLINE_FILE_UNVERIFIED", "SEC_HTTPS_RESPONSE_UNVERIFIED"})


def anchored_source_span(
    *, db_path: Path, cik: str, accession: str, sha256: str,
    needle: str, context_bytes: int = 64,
) -> dict[str, Any]:
    """Find exactly one literal ASCII phrase in hash-checked saved bytes.

    The caller chooses a phrase to locate. A successful match certifies only
    the exact local byte span and archived receipt linkage, never its truth.
    """
    if not isinstance(sha256, str) or _DIGEST.fullmatch(sha256) is None:
        raise ValueError("INVALID_ORIGINAL_DIGEST")
    if (not isinstance(needle, str) or not 4 <= len(needle) <= 128
            or not needle.isascii()
            or any(ord(ch) < 32 or ord(ch) > 126 for ch in needle)):
        raise ValueError("INVALID_LITERAL_PHRASE")
    if (type(context_bytes) is not int or
            not 0 <= context_bytes <= 160):
        raise ValueError("INVALID_CONTEXT_LIMIT")

    # This read path validates CIK, accession, pinned SEC archive URL,
    # source evidence state, selected digest and actual original bytes.
    source = locate_original(db_path, cik=cik, accession=accession)
    receipts = list_originals(db_path=db_path, cik=cik, accession=accession)
    matched = [item for item in receipts if item.get("filing_sha256") == sha256]
    if len(matched) != 1:
        raise ValueError("ORIGINAL_RECEIPT_UNAVAILABLE")
    receipt = matched[0]
    if (receipt.get("source_uri") != source.get("source_uri")
            or receipt.get("input_origin") not in _PROVENANCES):
        raise ValueError("ORIGINAL_PROVENANCE_CONFLICT")
    raw = read_original_bytes(
        db_path=db_path, cik=cik, accession=accession, sha256=sha256,
    )
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("ORIGINAL_INTEGRITY_MISMATCH")
    token = needle.encode("ascii")
    offset = raw.find(token)
    if offset < 0:
        raise ValueError("LITERAL_NOT_FOUND")
    if raw.find(token, offset + 1) >= 0:
        raise ValueError("AMBIGUOUS_LITERAL_OCCURRENCES")
    end = offset + len(token)
    start_preview = max(0, offset - context_bytes)
    end_preview = min(len(raw), end + context_bytes)
    # Never emit raw HTML in a UI-oriented snippet; no HTML execution.
    preview = html.escape(
        raw[start_preview:end_preview].decode("utf-8", "replace"), quote=True,
    )
    return {
        "schema": "proofinvest.dl-original-byte-span.v1",
        "status": "untrusted_original_span_for_review",
        "issuer_cik": source["issuer_cik"],
        "accession": source["accession"],
        "source_uri": source["source_uri"],
        "filing_sha256": sha256,
        "original_bytes_size": len(raw),
        "literal_ascii_phrase": needle,
        "start_byte": offset,
        "end_byte_exclusive": end,
        "context_start_byte": start_preview,
        "context_end_byte_exclusive": end_preview,
        "context_escaped_html": preview,
        "input_origin": receipt["input_origin"],
        "authenticated_external_source": False,
        "numerical_claim_verified": False,
        "investment_recommendation": False,
        "live_api_called": False,
        "note": ("Exact byte position in local original-file archive only. "
                 "HTML was escaped, no original filing or issuer truth attested."),
    }
