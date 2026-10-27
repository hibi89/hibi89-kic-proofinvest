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
    try:
        content = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("UNSUPPORTED_ENCODING_NOT_UTF8") from exc
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
        for line, item in enumerate(content.splitlines(), 1):
            text = _clean(item)
            if not text:
                continue
            if (len(text) > MAX_LINE_CHARS or len(text) > MAX_FRAGMENT_CHARS
                    or len(fragments) >= MAX_BLOCKS
                    or used + len(text) > MAX_CHARS):
                truncated = True
                continue
            fragments.append(_fragment(text, line, "DECODED_TEXT_LINE"))
            used += len(text)
        accuracy = "DECODED_LINE_ONLY_NO_BYTE_SPANS"
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
    args = parser.parse_args(argv)
    try:
        result = from_saved_original(
            db_path=args.db, cik=args.cik,
            accession=args.accession, sha256=args.sha256
        )
        if args.summary_only:
            result.pop("blocks")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if not result["truncated"] else 2
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({
            "status": "TEXT_EXTRACTION_UNAVAILABLE",
            "reason": str(exc)[:350],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
