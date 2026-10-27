"""Conservative local HTML text-node numerical literal locator.

The result proves only that exact ASCII digits occur in a decoded HTML text
node of supplied bytes. It is NOT an XBRL fact parser, SEC authentication,
period/scale/units check, or support for the financial statement claim.
No network, script execution, HTML rendering or disclosure of raw HTML.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any

# Reject partial numbers, decimal fragments, thousands separators, identifiers.
_INTEGER = re.compile(r"(?:0|[1-9][0-9]{0,17})\Z", re.ASCII)
_SUPPRESS = frozenset({
    "script", "style", "head", "template", "noscript", "svg",
})
_BOUNDARY = r"[0-9A-Za-z_.,+-]"
_MAX_BYTES = 25_000_000


class _TextNumberScanner(HTMLParser):
    def __init__(self, document: str, labels: tuple[str, str]):
        super().__init__(convert_charrefs=False)
        self._lines = document.split("\n")
        self._line_byte_offsets: list[int] = []
        cumul = 0
        for line in self._lines:
            self._line_byte_offsets.append(cumul)
            cumul += len(line.encode("utf-8")) + 1
        self._patterns = {
            label: re.compile(r"(?<!" + _BOUNDARY + r")" + re.escape(label)
                              + r"(?!" + _BOUNDARY + r")", re.ASCII)
            for label in labels
        }
        self.found: dict[str, list[dict[str, int]]] = {label: [] for label in labels}
        self._suppress: list[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _SUPPRESS:
            self._suppress.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SUPPRESS and tag in self._suppress:
            # Handle mildly malformed nesting; no skipped node is trusted.
            pos = len(self._suppress) - 1 - self._suppress[::-1].index(tag)
            del self._suppress[pos:]

    def handle_data(self, data: str) -> None:
        if self._suppress:
            return
        line, col = self.getpos()
        if line < 1 or line > len(self._lines):
            return
        begin = self._line_byte_offsets[line - 1] + len(
            self._lines[line - 1][:col].encode("utf-8")
        )
        for number, pattern in self._patterns.items():
            for match in pattern.finditer(data):
                if len(self.found[number]) >= 2:
                    break
                start = begin + len(data[:match.start()].encode("utf-8"))
                self.found[number].append({
                    "start_byte": start, "end_byte_exclusive": start + len(number)
                })


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_code": reason,
        "method": "EXACT_ASCII_IN_HTML_TEXT_NODES_ONLY",
        "prior_span": None,
        "current_span": None,
        "financial_facts_authenticated": False,
        "xbrl_context_verified": False,
        "accounting_units_or_scale_verified": False,
        "period_semantics_verified": False,
    }


def find_numeric_literals_in_html_text(
    original: bytes, *, prior_amount: str, current_amount: str,
) -> dict[str, Any]:
    """Find unique integer-looking USD values without inferring financial facts.

    Non-HTML or invalid UTF-8 is unavailable; numeric values in script, tag
    attributes, comments and CSS do not count. Malformed HTML is not repaired
    or interpreted as issuer data, and no result is labeled financial proof.
    """
    if (type(original) is not bytes or not 0 < len(original) <= _MAX_BYTES
            or not isinstance(prior_amount, str)
            or not isinstance(current_amount, str)
            or _INTEGER.fullmatch(prior_amount) is None
            or _INTEGER.fullmatch(current_amount) is None):
        return _unavailable("INVALID_INPUT")
    if prior_amount == current_amount:
        return _unavailable("IDENTICAL_NUMERIC_LITERALS_AMBIGUOUS")
    try:
        document = original.decode("utf-8")
    except UnicodeDecodeError:
        return _unavailable("NOT_STRICT_UTF8_HTML")
    # This checks plain HTML text nodes only; no source file MIME claim.
    parser = _TextNumberScanner(document, (prior_amount, current_amount))
    try:
        parser.feed(document)
        parser.close()
    except (ValueError, OverflowError, RecursionError):
        return _unavailable("MALFORMED_HTML_FOR_LITERAL_REVIEW")
    prior = parser.found[prior_amount]
    current = parser.found[current_amount]
    if not prior or not current:
        return _unavailable("NUMERIC_LITERAL_NOT_IN_HTML_TEXT")
    if len(prior) != 1 or len(current) != 1:
        return _unavailable("AMBIGUOUS_NUMERIC_LITERAL_OCCURRENCES")
    for number, position in ((prior_amount, prior[0]), (current_amount, current[0])):
        if original[position["start_byte"]:position["end_byte_exclusive"]] != number.encode():
            return _unavailable("BYTE_OFFSET_TEXT_MISMATCH")
    return {
        **_unavailable("LITERAL_LOCATIONS_ONLY_NOT_FACTS"),
        "status": "untrusted_numeric_literals_located",
        "prior_span": prior[0],
        "current_span": current[0],
    }
