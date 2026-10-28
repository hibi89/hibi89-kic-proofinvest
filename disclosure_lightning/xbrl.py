"""Read-only, untrusted Inline XBRL evidence candidates from saved filings.

This module preserves XBRL names, context/unit metadata and source line hints.
It does not normalize values, infer amendment relationships, or certify facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from . import extract
from .originals import MAX_FILING_BYTES, list_originals, read_original_bytes

SUPPORTED_FACT_NAMES = frozenset({"nonfraction", "nonnumeric"})
INLINE_XBRL_NAMESPACE = "http://www.xbrl.org/2013/inlineXBRL"
XBRLI_NAMESPACE = "http://www.xbrl.org/2003/instance"
MAX_CANDIDATES = 10_000
MAX_TREE_NODES = 20_000
MAX_LEXICAL_CHARS = 10_000
HTML_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/xml", "application/xml"})
HTML_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


def _local(tag: str) -> str:
    return tag.rsplit(":", 1)[-1].lower()


def _attrs(items: list[tuple[str, str | None]]) -> dict[str, str | None]:
    return {str(key).lower(): value for key, value in items}


def _expanded_name(tag: str, namespaces: dict[str, str]) -> tuple[str, str]:
    prefix, separator, local = tag.lower().partition(":")
    namespace = namespaces.get(prefix, "") if separator else namespaces.get("", "")
    return namespace, local


class _InlineXbrlParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.contexts: list[dict] = []
        self.units: list[dict] = []
        self.facts: list[dict] = []
        self.fact_stack: list[dict] = []
        self.tree_stack: list[dict] = []
        self.tree_roots: list[dict] = []
        self.tree_nodes = 0
        self.fact_starts = 0
        self.unsupported_fact_count = 0
        self.exclude_depth = 0
        self.truncated = False
        self.namespaces: dict[str, str] = {}
        self.namespace_stack: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        attr_map = _attrs(attrs)
        previous = self.namespaces
        scoped = dict(previous)
        for key, value in attr_map.items():
            if isinstance(value, str):
                if key == "xmlns":
                    scoped[""] = value
                elif key.startswith("xmlns:"):
                    scoped[key[6:]] = value
        self.namespaces = scoped
        if tag not in HTML_VOID_ELEMENTS:
            self.namespace_stack.append((tag, scoped))
        line, _ = self.getpos()

        try:
            namespace, local_name = _expanded_name(tag, scoped)
            if self.exclude_depth:
                if namespace == INLINE_XBRL_NAMESPACE and local_name == "exclude":
                    self.exclude_depth += 1
                return
            if namespace == INLINE_XBRL_NAMESPACE and local_name == "exclude":
                self.exclude_depth = 1
                return
            if (namespace == XBRLI_NAMESPACE and local_name in {"context", "unit"}):
                if self.tree_stack:
                    self.truncated = True
                self.tree_nodes += 1
                if self.tree_nodes > MAX_TREE_NODES:
                    self.truncated = True
                    return
                node = {"tag": tag, "attributes": attr_map, "text": "", "children": [],
                        "source_line": line}
                self.tree_roots.append(node)
                self.tree_stack.append(node)
                return
            if self.tree_stack:
                self.tree_nodes += 1
                if self.tree_nodes > MAX_TREE_NODES:
                    self.truncated = True
                    return
                node = {"tag": tag, "attributes": attr_map, "text": "", "children": [],
                        "source_line": line}
                self.tree_stack[-1]["children"].append(node)
                self.tree_stack.append(node)
                return
            if namespace == INLINE_XBRL_NAMESPACE and local_name in SUPPORTED_FACT_NAMES:
                if self.fact_starts >= MAX_CANDIDATES:
                    self.truncated = True
                    return
                self.fact_starts += 1
                self.fact_stack.append({
                    "tag": tag,
                    "attributes": attr_map,
                    "text": "",
                    "source_start_line": line,
                    "source_end_line": line,
                })
            elif namespace == INLINE_XBRL_NAMESPACE and local_name not in {
                    "header", "references", "resources", "exclude"}:
                self.unsupported_fact_count += 1
        finally:
            if tag in HTML_VOID_ELEMENTS:
                self.namespaces = previous

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        try:
            namespace, local_name = _expanded_name(tag, self.namespaces)
            if self.exclude_depth:
                if namespace == INLINE_XBRL_NAMESPACE and local_name == "exclude":
                    self.exclude_depth -= 1
                return
            if self.tree_stack:
                matched = False
                for index in range(len(self.tree_stack) - 1, -1, -1):
                    if self.tree_stack[index]["tag"] == tag:
                        if index != len(self.tree_stack) - 1:
                            self.truncated = True
                        del self.tree_stack[index:]
                        matched = True
                        break
                if not matched:
                    self.truncated = True
                if not self.tree_stack and self.tree_roots:
                    root = self.tree_roots[-1]
                    root_namespace, root_name = _expanded_name(root["tag"], self.namespaces)
                    if root_namespace == XBRLI_NAMESPACE and root_name == "context":
                        self.contexts.append(root)
                    elif root_namespace == XBRLI_NAMESPACE and root_name == "unit":
                        self.units.append(root)
                return
            if self.fact_stack and self.fact_stack[-1]["tag"] == tag:
                fact = self.fact_stack.pop()
                fact["source_end_line"] = self.getpos()[0]
                self.facts.append(fact)
        finally:
            for index in range(len(self.namespace_stack) - 1, -1, -1):
                if self.namespace_stack[index][0] == tag:
                    del self.namespace_stack[index:]
                    self.namespaces = (
                        self.namespace_stack[-1][1] if self.namespace_stack else {}
                    )
                    break

    def handle_data(self, data: str):
        if self.exclude_depth:
            return
        if self.tree_stack:
            node = self.tree_stack[-1]
            remaining = MAX_LEXICAL_CHARS - len(node["text"])
            node["text"] += data[:remaining]
            if len(data) > remaining:
                self.truncated = True
        elif self.fact_stack:
            fact = self.fact_stack[-1]
            remaining = MAX_LEXICAL_CHARS - len(fact["text"])
            fact["text"] += data[:remaining]
            if len(data) > remaining:
                self.truncated = True


def _index_by_id(nodes: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for node in nodes:
        key = node["attributes"].get("id")
        if isinstance(key, str) and key:
            result.setdefault(key, []).append(node)
    return result


def _period(context: dict | None) -> dict | None:
    if context is None:
        return None
    period_nodes = [child for child in context["children"] if _local(child["tag"]) == "period"]
    if len(period_nodes) != 1:
        return None
    fields: dict[str, list[str]] = {}
    for child in period_nodes[0]["children"]:
        name = _local(child["tag"])
        if name in {"instant", "startdate", "enddate", "forever"}:
            fields.setdefault(name, []).append(child["text"].strip())
    return {key: values[0] if len(values) == 1 else values
            for key, values in fields.items()}


def _fact_record(fact: dict, contexts: dict[str, list[dict]],
                 units: dict[str, list[dict]]) -> dict:
    attrs = fact["attributes"]
    context_ref = attrs.get("contextref")
    unit_ref = attrs.get("unitref")
    context_matches = contexts.get(context_ref, []) if isinstance(context_ref, str) else []
    unit_matches = units.get(unit_ref, []) if isinstance(unit_ref, str) else []
    context = context_matches[0] if len(context_matches) == 1 else None
    unit = unit_matches[0] if len(unit_matches) == 1 else None
    value = fact["text"]
    return {
        "name": attrs.get("name"),
        "fact_kind": _local(fact["tag"]),
        "lexical_value": value,
        "value_truncated": len(value) >= MAX_LEXICAL_CHARS,
        "context_ref": context_ref,
        "context_ref_status": "RESOLVED_UNVERIFIED" if context is not None else "UNKNOWN_OR_AMBIGUOUS",
        "context_source": context,
        "context_period_fields": _period(context),
        "unit_ref": unit_ref,
        "unit_ref_status": "RESOLVED_UNVERIFIED" if unit is not None else (
            "NOT_APPLICABLE" if unit_ref is None else "UNKNOWN_OR_AMBIGUOUS"
        ),
        "unit_source": unit,
        "scale": attrs.get("scale"),
        "sign": attrs.get("sign"),
        "format": attrs.get("format"),
        "decimals": attrs.get("decimals"),
        "nil": attrs.get("xsi:nil"),
        "continued_at": attrs.get("continuedat"),
        "continued_text_complete": attrs.get("continuedat") is None,
        "source_locator": {
            "type": "HTML_LINE_HINT_NEEDS_REVIEW",
            "start_line": fact["source_start_line"],
            "end_line": fact["source_end_line"],
            "exact_raw_byte_range_verified": False,
        },
        "financial_claim_verified": False,
        "source_authenticity_verified": False,
    }


def extract_inline_facts(raw: bytes, *, content_type: str, filing_sha256: str,
                         issuer_cik: str, accession: str, source_uri: str,
                         input_origin: str) -> dict[str, Any]:
    """Extract conservative Inline XBRL fact candidates from bounded saved HTML."""
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_FILING_BYTES
            or not isinstance(filing_sha256, str)
            or len(filing_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in filing_sha256)
            or hashlib.sha256(raw).hexdigest() != filing_sha256):
        raise ValueError("INLINE_XBRL_SOURCE_INTEGRITY_FAILED")
    if not isinstance(content_type, str) or content_type not in HTML_TYPES:
        raise ValueError("UNSUPPORTED_INLINE_XBRL_CONTENT_TYPE")
    text, encoding, declared = extract._decode_local_text(raw, content_type)
    parser = _InlineXbrlParser()
    parser.feed(text)
    parser.close()
    if parser.fact_stack or parser.tree_stack or parser.exclude_depth:
        parser.truncated = True
    contexts = _index_by_id(parser.contexts)
    units = _index_by_id(parser.units)
    facts = [_fact_record(fact, contexts, units) for fact in parser.facts]
    return {
        "schema": "disclosure-lightning.inline-xbrl-candidates.v1",
        "issuer_cik": issuer_cik,
        "accession": accession,
        "source_uri": source_uri,
        "filing_sha256": filing_sha256,
        "input_origin": input_origin,
        "decoded_encoding": encoding,
        "html_meta_declared_charset": declared,
        "candidate_count": len(facts),
        "unsupported_inline_xbrl_element_count": parser.unsupported_fact_count,
        "truncated": parser.truncated,
        "complete_candidate_extraction": (
            not parser.truncated and parser.unsupported_fact_count == 0
            and all(fact["continued_text_complete"] for fact in facts)
        ),
        "normalization_performed": False,
        "financial_claim_verified": False,
        "source_authenticity_verified": False,
        "facts": facts,
    }


def from_saved_original(*, db_path: Path, cik: str, accession: str, sha256: str,
                        as_of: str | None = None) -> dict[str, Any]:
    records = list_originals(db_path=db_path, cik=cik, accession=accession, as_of=as_of)
    matches = [row for row in records if row.get("filing_sha256") == sha256]
    if len(matches) != 1:
        raise ValueError("SAVED_ORIGINAL_RECEIPT_NOT_FOUND_OR_AMBIGUOUS")
    record = matches[0]
    raw = read_original_bytes(db_path=db_path, cik=cik, accession=accession,
                              sha256=sha256, as_of=as_of)
    result = extract_inline_facts(
        raw, content_type=record["content_type"], filing_sha256=sha256,
        issuer_cik=cik, accession=accession, source_uri=record["source_uri"],
        input_origin=record["input_origin"],
    )
    if as_of is not None:
        result["as_of"] = as_of
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only untrusted Inline XBRL candidate extractor from saved bytes"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args(argv)
    try:
        result = from_saved_original(
            db_path=args.db, cik=args.cik, accession=args.accession,
            sha256=args.sha256, as_of=args.as_of,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "DL_XBRL_FAILED", "reason": str(exc)[:400]},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
