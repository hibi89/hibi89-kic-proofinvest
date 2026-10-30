"""Read-only KIC review of exact literal bytes inside HTML text nodes.

Adapted conceptually from Disclosure Lightning's conservative extract module,
without importing its divergent historical/DB contracts. Local caller bytes
are not authenticated SEC filings. This is not browser visibility, taxonomy
validation, numeric verification, or a financial recommendation.
"""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

MAX_BYTES = 25_000_000
MAX_IGNORED_DEPTH = 128
IGNORED = frozenset({
    "script", "style", "head", "template", "noscript", "svg",
    "iframe", "object", "canvas", "audio", "video",
    "noembed", "noframes",
})


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_code": reason,
        "start_byte": None,
        "end_byte_exclusive": None,
        "exact_raw_byte_span_verified": False,
        "rendered_visibility_verified": False,
        "source_authenticated": False,
        "financial_fact_verified": False,
    }


class _LiteralTextNodes(HTMLParser):
    def __init__(self, raw: bytes, document: str, literal: str):
        super().__init__(convert_charrefs=False)
        self.raw = raw
        self.literal = literal
        self.lines = document.split("\n")
        self.line_starts: list[int] = []
        cursor = 0
        for i, line in enumerate(self.lines):
            self.line_starts.append(cursor)
            cursor += len(line.encode("utf-8"))
            if i + 1 < len(self.lines):
                cursor += 1
        self.ignored: list[str] = []
        self.unsafe = False
        self.matches: list[tuple[int, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in IGNORED:
            if len(self.ignored) >= MAX_IGNORED_DEPTH:
                self.unsafe = True
            else:
                self.ignored.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Treat self-closing hidden HTML tags conservatively, including
        # malformed script/style. An unclosed tag yields unavailable.
        if tag in IGNORED and tag != "svg":
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()

    def handle_data(self, data: str) -> None:
        if self.unsafe or self.ignored or not data:
            return
        line, column = self.getpos()
        if line < 1 or line > len(self.lines):
            self.unsafe = True
            return
        original_line = self.lines[line - 1]
        if column < 0 or column > len(original_line):
            self.unsafe = True
            return
        start = self.line_starts[line - 1] + len(original_line[:column].encode("utf-8"))
        encoded = data.encode("utf-8")
        if self.raw[start:start + len(encoded)] != encoded:
            # A parser transformation cannot supply an exact raw-byte cite.
            self.unsafe = True
            return
        offset = 0
        while len(self.matches) < 2:
            index = data.find(self.literal, offset)
            if index < 0:
                break
            pos = start + len(data[:index].encode("utf-8"))
            self.matches.append((pos, pos + len(self.literal.encode("ascii"))))
            offset = index + 1


def confirm_html_text_node_literal(
    original: bytes, *, needle: str, expected_start: int, expected_end: int,
) -> dict[str, Any]:
    """Validate exact pinned literal in a text node, not script/attribute/comment.

    This check cannot establish actual rendered CSS visibility: an HTML node
    with a 'hidden' attribute may still be parsed as a text node.
    """
    if (type(original) is not bytes or not 0 < len(original) <= MAX_BYTES
            or not isinstance(needle, str)
            or not 4 <= len(needle) <= 128 or not needle.isascii()
            or any(ord(ch) < 32 or ord(ch) > 126 for ch in needle)
            or type(expected_start) is not int or type(expected_end) is not int
            or not 0 <= expected_start < expected_end <= len(original)):
        return _unavailable("INVALID_TEXT_NODE_INPUT")
    if original[expected_start:expected_end] != needle.encode("ascii"):
        return _unavailable("PINNED_LITERAL_BYTE_SPAN_MISMATCH")
    try:
        document = original.decode("utf-8")
    except UnicodeDecodeError:
        return _unavailable("HTML_NOT_STRICT_UTF8")
    scanner = _LiteralTextNodes(original, document, needle)
    try:
        scanner.feed(document)
        scanner.close()
    except (ValueError, RecursionError, OverflowError, AssertionError):
        return _unavailable("HTML_TEXT_NODE_PARSE_FAILED")
    if scanner.unsafe or scanner.ignored:
        return _unavailable("HTML_TEXT_NODE_PARSE_UNCERTAIN")
    if not scanner.matches:
        return _unavailable("LITERAL_NOT_IN_ELIGIBLE_HTML_TEXT_NODE")
    if len(scanner.matches) != 1:
        return _unavailable("AMBIGUOUS_HTML_TEXT_NODE_LITERAL")
    if scanner.matches[0] != (expected_start, expected_end):
        return _unavailable("HTML_TEXT_NODE_OFFSET_MISMATCH")
    return {
        **_unavailable("TEXT_NODE_ONLY_NO_FACT_AUTHENTICATION"),
        "status": "untrusted_html_text_node_literal_located",
        "start_byte": expected_start,
        "end_byte_exclusive": expected_end,
        "exact_raw_byte_span_verified": True,
    }
