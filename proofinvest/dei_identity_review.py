"""Optional issuer/document self-claims embedded in an untrusted SEC-shaped HTML.

DEI Inline XBRL claims can corroborate a declared CIK and form, but cannot
authenticate an issuer, source URL, original-to-accession association or rights.
A present mismatch/ambiguous claim fails closed. Missing DEI claims are NOT
grounds to allege a false filing; mark unavailable rather than fabricate data.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any

MAX_BYTES = 25_000_000
_CIK = re.compile(r"[0-9]{1,10}\Z", re.ASCII)
_NAME_TO_KIND = {
    "dei:EntityCentralIndexKey": "cik",
    "dei:DocumentType": "form",
}
_LIMIT_FACTS = 64


class _ClaimScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.active: str | None = None
        self.text_parts: list[str] = []
        self.values: dict[str, set[str]] = {"cik": set(), "form": set()}
        self.ambiguous = False
        self.seen = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.active is not None:
            # Nested markup prevents exact literal DEI value interpretation.
            self.ambiguous = True
            return
        if tag != "ix:nonnumeric":
            return
        name_values = [value for key, value in attrs if key == "name"]
        kinds = [_NAME_TO_KIND[value] for value in name_values
                 if value in _NAME_TO_KIND]
        if not kinds:
            return
        if len(kinds) != 1 or len(name_values) != 1 or self.seen >= _LIMIT_FACTS:
            self.ambiguous = True
            return
        self.active = kinds[0]
        self.text_parts = []
        self.seen += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.active is not None:
            self.ambiguous = True
            self.active = None

    def handle_endtag(self, tag: str) -> None:
        if self.active is None:
            if tag == "ix:nonnumeric":
                self.ambiguous = True
            return
        if tag != "ix:nonnumeric":
            self.ambiguous = True
            return
        self.values[self.active].add("".join(self.text_parts).strip())
        self.active = None
        self.text_parts = []

    def handle_data(self, data: str) -> None:
        if self.active is not None:
            if len(self.text_parts) > 16 or sum(map(len, self.text_parts)) + len(data) > 128:
                self.ambiguous = True
            else:
                self.text_parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.active is not None:
            self.ambiguous = True

    def handle_charref(self, name: str) -> None:
        if self.active is not None:
            self.ambiguous = True


def review_embedded_dei_identity(
    original: bytes, *, cik: str, expected_form: str = "10-K",
) -> dict[str, Any]:
    """Conservatively inspect Inline XBRL self-claims; no SEC authentication."""
    report: dict[str, Any] = {
        "schema": "kuodra.dei-identity-self-claim.v1",
        "status": "unavailable",
        "reason_code": "DEI_MARKUP_CLAIMS_NOT_PRESENT",
        "cik_self_claim_present": False,
        "form_self_claim_present": False,
        "cik_self_claim_matches_operator": False,
        "form_self_claim_matches_operator": False,
        "full_original_to_accession_link_verified": False,
        "issuer_authenticated": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "external_network_called": False,
    }
    if (type(original) is not bytes or not 0 < len(original) <= MAX_BYTES
            or type(cik) is not str
            or re.fullmatch(r"[0-9]{10}", cik, re.ASCII) is None
            or cik == "0000000000" or expected_form != "10-K"):
        report["reason_code"] = "INVALID_DEI_REVIEW_INPUT"
        return report
    try:
        decoded = original.decode("utf-8")
    except UnicodeDecodeError:
        report["reason_code"] = "DEI_HTML_NOT_STRICT_UTF8"
        return report
    scanner = _ClaimScanner()
    try:
        scanner.feed(decoded)
        scanner.close()
    except (ValueError, AssertionError, RecursionError, OverflowError):
        report["status"] = "ambiguous"
        report["reason_code"] = "DEI_HTML_PARSER_UNCERTAIN"
        return report
    values = scanner.values
    report["cik_self_claim_present"] = bool(values["cik"])
    report["form_self_claim_present"] = bool(values["form"])
    if scanner.ambiguous or scanner.active is not None:
        report["status"] = "ambiguous"
        report["reason_code"] = "DEI_FACT_MARKUP_AMBIGUOUS"
        return report
    if len(values["cik"]) > 1 or len(values["form"]) > 1:
        report["status"] = "conflict"
        report["reason_code"] = "DEI_DUPLICATE_CONFLICTING_CLAIMS"
        return report
    if values["cik"]:
        value = next(iter(values["cik"]))
        report["cik_self_claim_matches_operator"] = (
            _CIK.fullmatch(value) is not None and value.zfill(10) == cik
        )
    if values["form"]:
        report["form_self_claim_matches_operator"] = (
            next(iter(values["form"])) == expected_form
        )
    if ((values["cik"] and not report["cik_self_claim_matches_operator"])
            or (values["form"] and not report["form_self_claim_matches_operator"])):
        report["status"] = "conflict"
        report["reason_code"] = "DEI_ISSUER_OR_DOCUMENT_TYPE_MISMATCH"
        return report
    if values["cik"] and values["form"]:
        report["status"] = "self_claims_consistent_unverified"
        report["reason_code"] = "DEI_SELF_CLAIMS_MATCH_NOT_AUTHENTICATED"
    elif values["cik"] or values["form"]:
        report["status"] = "partial_self_claims_consistent_unverified"
        report["reason_code"] = "ONLY_ONE_DEI_SELF_CLAIM_PRESENT"
    return report
