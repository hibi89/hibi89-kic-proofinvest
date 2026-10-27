"""Conservative local extraction of saved SEC primary-file text fragments.

Only previously stored, SHA-256-checked bytes are processed; zero network.
Source *line* hints from HTMLParser are NOT character/byte-accurate citations.
Do not treat extracted text as SEC-authenticated facts or HTML as safe to render.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import sys
from typing import Any

from .originals import list_originals, read_original_bytes

MAX_BLOCKS = 1200
MAX_CHARS = 250_000
MAX_FRAGMENT_CHARS = 1200
MAX_LINE_CHARS = 15_000
SKIP_TAGS = frozenset({
    "script", "style", "head", "template", "svg", "noscript"
})
WS = re.compile(r"\s+")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str) -> str:
    return WS.sub(" ", CTRL.sub(" ", value)).strip()


# Only locally archived HTML may use explicitly declared, bounded legacy
# charsets. Never guess an encoding from arbitrary undecodable bytes.
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_META_TAG = re.compile(rb"<meta\b[^>]{0,512}>", re.IGNORECASE)
_META_CHARSET = re.compile(
    rb"\bcharset\s*=\s*['\"]?\s*([a-zA-Z0-9_-]+)", re.IGNORECASE
)
_HTML_CODECS = {
    "utf-8": ("utf-8", "utf-8"),
    "utf8": ("utf-8", "utf-8"),
    "windows-1252": ("cp1252", "windows-1252"),
    # HTML treats ISO-8859-1 declarations as Windows-1252 for 0x80..0x9F.
    # This mapping is for HTML only, not for XML or raw text.
    "iso-8859-1": ("cp1252", "windows-1252"),
}


def _decode_local_text(raw: bytes, kind: str) -> tuple[str, str, str | None]:
    declared = None
    if kind in _HTML_TYPES:
        for tag in _META_TAG.finditer(raw[:4096]):
            match = _META_CHARSET.search(tag.group())
            if match is not None:
                declared = match.group(1).decode("ascii").lower()
                break
    if raw.startswith(b"\xef\xbb\xbf"):
        if declared is not None and declared not in ("utf-8", "utf8"):
            raise ValueError("CONFLICTING_UTF8_BOM_AND_HTML_CHARSET")
        codec, applied = "utf-8-sig", "utf-8"
    elif declared is not None:
        if declared not in _HTML_CODECS:
            raise ValueError("UNSUPPORTED_DECLARED_HTML_CHARSET")
        codec, applied = _HTML_CODECS[declared]
    else:
        codec, applied = "utf-8", "utf-8"
    try:
        content = raw.decode(codec, errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("UNSUPPORTED_ENCODING_OR_INVALID_TEXT_BYTES") from exc
    return content, applied, declared


def _fragment(text: str, line: int, kind: str) -> dict:
    return {
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_locator": {"type": kind, "line": line},
        "exact_raw_byte_range_verified": False,
    }


class _SafeVisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skipped: list[str] = []
        self.fragments: list[dict] = []
        self.total_chars = 0
        self.truncated = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        if self.skipped:
            if tag in SKIP_TAGS:
                self.skipped.append(tag)
        elif tag in SKIP_TAGS:
            self.skipped.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        # A void/self-closing hidden element must not suppress later content.
        return None

    def handle_endtag(self, tag: str):
        if self.skipped and tag.lower() == self.skipped[-1]:
            self.skipped.pop()

    def handle_data(self, data: str):
        if self.skipped:
            return
        chunk = _clean(data)
        if not chunk:
            return
        # Never label fragments longer than the accepted per-fragment budget
        # as if they were completely extracted.
        if (len(chunk) > MAX_FRAGMENT_CHARS
                or len(self.fragments) >= MAX_BLOCKS
                or self.total_chars + len(chunk) > MAX_CHARS):
            self.truncated = True
            return
        self.fragments.append(_fragment(chunk, self.getpos()[0], "HTML_PARSER_LINE_HINT"))
        self.total_chars += len(chunk)

    def handle_entityref(self, name: str):
        # HTMLParser with convert_charrefs=True handles normal text entities.
        return None


def extract_bytes(raw: bytes, *, content_type: str,
                  filing_sha256: str, issuer_cik: str,
                  accession: str, source_uri: str,
                  input_origin: str) -> dict[str, Any]:
    """Deterministic text receipt; no content model, claim or URL fetch."""
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 25_000_000
            or not isinstance(filing_sha256, str)
            or hashlib.sha256(raw).hexdigest() != filing_sha256):
        raise ValueError("RAW_FILING_DIGEST_MISMATCH_OR_INVALID_BYTES")
    if content_type not in {
        "text/html", "application/xhtml+xml", "text/plain", "text/xml",
        "application/xml", "application/octet-stream",
    }:
        raise ValueError("UNSUPPORTED_TEXT_CONTENT_TYPE")
    # An offline file recorded as opaque bytes has no asserted MIME type.
    # Restrict it to a local-only UTF-8 plain-text parse (not HTML inference).
    if content_type == "application/octet-stream" and input_origin != "OFFLINE_FILE_UNVERIFIED":
        raise ValueError("OPAQUE_LIVE_CONTENT_NOT_PARSABLE")
    content, applied_encoding, declared_encoding = _decode_local_text(raw, content_type)
    if len(content) > 25_000_000:
        raise ValueError("TEXT_DECODE_LIMIT")
    fragments: list[dict] = []
    truncated = False
    if content_type in {"text/html", "application/xhtml+xml", "text/xml", "application/xml"}:
        parser = _SafeVisibleText()
        try:
            parser.feed(content)
            parser.close()
        except (ValueError, AssertionError) as exc:
            raise ValueError("HTML_TEXT_PARSE_FAILED") from exc
        if parser.skipped:
            # Incomplete script/style blocks are not trustworthy for citation.
            truncated = True
        fragments = parser.fragments
        truncated = truncated or parser.truncated
        accuracy = "LINE_HINT_ONLY_NO_RAW_BYTE_SPANS"
    else:
        used = 0
        # UTF-8 decoded text re-encodes byte-for-byte. A UTF-8 BOM is outside
        # the first decoded line; do not misreport its offset as text evidence.
        byte_cursor = len(raw) - len(content.encode("utf-8"))
        for line, item in enumerate(content.splitlines(keepends=True), 1):
            raw_line = item.encode("utf-8")
            start_byte, end_byte = byte_cursor, byte_cursor + len(raw_line)
            if raw[start_byte:end_byte] != raw_line:
                raise ValueError("RAW_TEXT_SPAN_INTEGRITY_FAILED")
            byte_cursor = end_byte
            text = _clean(item)
            if not text:
                continue
            if (len(text) > MAX_LINE_CHARS or len(text) > MAX_FRAGMENT_CHARS
                    or len(fragments) >= MAX_BLOCKS
                    or used + len(text) > MAX_CHARS):
                truncated = True
                continue
            block = _fragment(text, line, "UTF8_RAW_LINE_BYTE_SPAN")
            block["source_locator"] = {
                "type": "UTF8_RAW_LINE_BYTE_SPAN", "line": line,
                "start_byte": start_byte, "end_byte_exclusive": end_byte,
            }
            block["raw_span_sha256"] = hashlib.sha256(raw_line).hexdigest()
            # The exact RAW line span is verified, but cleaned 'text' is
            # normalized and NO financial or issuer authenticity is verified.
            block["exact_raw_byte_range_verified"] = True
            fragments.append(block)
            used += len(text)
        if byte_cursor != len(raw):
            raise ValueError("RAW_TEXT_SPAN_INTEGRITY_FAILED")
        accuracy = "EXACT_RAW_LINE_BYTE_SPANS_UNVERIFIED_SOURCE"
    receipt = {
        "schema": "disclosure-lightning.extracted-text.v1",
        "issuer_cik": issuer_cik,
        "accession": accession,
        "source_uri": source_uri,
        "filing_sha256": filing_sha256,
        "raw_source_bytes": len(raw),
        "input_origin": input_origin,
        "source_authenticity_verified": False,
        "content_type": content_type,
        "decoded_encoding": applied_encoding,
        "html_meta_declared_charset": declared_encoding,
        "charset_claim_verified": False,
        "extraction_method": "stdlib-htmlparser" if accuracy.startswith("LINE_HINT") else "utf8-lines",
        "source_locator_accuracy": accuracy,
        "block_count": len(fragments),
        "truncated": truncated,
        "complete_text_extracted": not truncated,
        "suitable_for_automatic_financial_facts": False,
        "blocks": fragments,
    }
    return receipt


def from_saved_original(*, db_path, cik: str, accession: str, sha256: str) -> dict:
    receipts = list_originals(db_path=db_path, cik=cik, accession=accession)
    matched = [entry for entry in receipts if entry["filing_sha256"] == sha256]
    if len(matched) != 1:
        raise ValueError("SAVED_ORIGINAL_RECEIPT_NOT_FOUND_OR_AMBIGUOUS")
    meta = matched[0]
    raw = read_original_bytes(
        db_path=db_path, cik=cik, accession=accession, sha256=sha256
    )
    return extract_bytes(
        raw, content_type=meta["content_type"], filing_sha256=sha256,
        issuer_cik=cik, accession=accession, source_uri=meta["source_uri"],
        input_origin=meta["input_origin"],
    )



def find_evidence_candidates(receipt: dict, *, term: str,
                             max_results: int = 20) -> dict:
    """Literal case-insensitive search of unverified extraction fragments.

    The result is a *candidate* for human/source-document verification,
    not an asserted financial fact, period, currency or exact byte span.
    """
    if (not isinstance(receipt, dict)
            or receipt.get("schema") != "disclosure-lightning.extracted-text.v1"
            or not isinstance(receipt.get("blocks"), list)):
        raise ValueError("INVALID_EXTRACTION_RECEIPT")
    if (not isinstance(term, str) or not 2 <= len(term) <= 80
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in term)
            or not term.strip()):
        raise ValueError("SEARCH_TERM_INVALID")
    if type(max_results) is not int or not 1 <= max_results <= 50:
        raise ValueError("RESULT_LIMIT_INVALID")
    key = term.casefold()
    found = []
    for block in receipt["blocks"]:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            raise ValueError("EXTRACTION_BLOCK_INVALID")
        if key in block["text"].casefold():
            found.append({
                **block, "citation_status": "SOURCE_LINE_HINT_NEEDS_REVIEW",
                "financial_claim_verified": False,
            })
        if len(found) >= max_results:
            break
    return {
        "schema": "disclosure-lightning.evidence-candidates.v1",
        "issuer_cik": receipt["issuer_cik"],
        "accession": receipt["accession"],
        "filing_sha256": receipt["filing_sha256"],
        "source_uri": receipt["source_uri"],
        "search_term": term,
        "max_results": max_results,
        "returned": len(found),
        "search_scope_truncated": receipt["truncated"],
        "source_authenticity_verified": False,
        "financial_claim_verified": False,
        "candidates": found,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline DL original byte → conservative bounded text receipt"
    )
    parser.add_argument("--db", required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--sha256", required=True, help="Known original-filing digest")
    parser.add_argument("--summary-only", action="store_true",
                        help="Return status and digests, not extracted text blocks")
    parser.add_argument("--find", help="Search extracted fragments for one literal keyword")
    args = parser.parse_args(argv)
    try:
        result = from_saved_original(
            db_path=args.db, cik=args.cik,
            accession=args.accession, sha256=args.sha256
        )
        truncated = result["truncated"]
        if args.find is not None:
            if args.summary_only:
                raise ValueError("--find cannot be combined with --summary-only")
            result = find_evidence_candidates(result, term=args.find)
        elif args.summary_only:
            result.pop("blocks")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if not truncated else 2
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({
            "status": "TEXT_EXTRACTION_UNAVAILABLE",
            "reason": str(exc)[:350],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
