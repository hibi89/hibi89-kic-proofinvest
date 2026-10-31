"""Read-only ProofInvest gate for canonical DL submissions metadata.

This does NOT import the DL implementation, fetch external services, or
independently authenticate SEC files. External index and verifier verdict
inputs are caller-supplied, structurally checked, and always unverified.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping
import re


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "proofinvest.dl-metadata-bridge.v1",
        "status": "unavailable", "reason_code": reason,
        "trace_linked": False, "numeric_verdict_state": None,
        "authenticated_external_source": False,
        "original_filing_downloaded": False,
        "investment_recommendation": False,
        "live_api_called": False,
        "official_contest_submission": False,
    }


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant.astimezone(timezone.utc) if instant.tzinfo is not None else None
    except ValueError:
        return None


def filing_available_at_observation(index: Any, record: Any) -> bool:
    """One 10-K must exist by the stated collection INSTANT, not just its day.

    Same-day unknown/naive SEC acceptance timestamps are withheld. Prior-day
    missing zone remains date-only evidence, never a verified receipt.
    These are caller-supplied metadata, not independently authenticated clocks.
    """
    if not isinstance(index, Mapping) or not isinstance(record, Mapping):
        return False
    cutoff = _day(index.get("as_of_cutoff"))
    observed = _instant(index.get("collected_at"))
    filed = _day(record.get("filed_at"))
    if (cutoff is None or observed is None or filed is None
            or observed.date() > cutoff or filed > cutoff
            or filed > observed.date()):
        return False
    accepted = _instant(record.get("accepted_at"))
    if accepted is not None:
        return accepted <= observed
    # No timezone inference for naive/missing/invalid SEC acceptance clocks.
    return filed < observed.date()


def assess_dl_sec_handoff(index: Any, numeric_verdict: Any) -> dict[str, Any]:
    """Link ONE DL 10-K metadata record to a matching KIC SEC numeric verdict.

    All evidence remains unverified; this operation does not re-run financial
    arithmetic or claim that the two caller-supplied records are genuine.
    """
    if not isinstance(index, Mapping) or not isinstance(numeric_verdict, Mapping):
        return _blocked("MALFORMED_HANDOFF")
    cik = index.get("issuer_cik")
    cutoff = _day(index.get("as_of_cutoff"))
    collected = _instant(index.get("collected_at"))
    origin = index.get("provenance")
    digest = index.get("source_sha256")
    expected_status = {
        "OFFLINE_UNVERIFIED": "OFFLINE_SOURCE_UNVERIFIED",
        "SEC_HTTPS_RESPONSE": "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED",
    }.get(origin if isinstance(origin, str) else "")
    if (index.get("provider") != "SEC_EDGAR"
            or not isinstance(cik, str) or re.fullmatch(r"[0-9]{10}", cik) is None
            or not cik.strip("0") or cutoff is None or collected is None
            or not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None
            or expected_status is None
            or index.get("source_uri") != f"https://data.sec.gov/submissions/CIK{cik}.json"):
        return _blocked("INVALID_DL_METADATA_CONTRACT")
    # Source retrieved after an as-of date may be retrospectively helpful,
    # but cannot support a contemporaneous as-of evidence assertion.
    if collected.date() > cutoff:
        return _blocked("DL_COLLECTION_AFTER_AS_OF")

    filings = index.get("filings")
    if not isinstance(filings, list) or not filings:
        return _blocked("MISSING_DL_FILINGS")
    accession = numeric_verdict.get("accession")
    if (not isinstance(accession, str)
            or re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession) is None
            or numeric_verdict.get("cik") != cik
            or numeric_verdict.get("as_of") != cutoff.isoformat()):
        return _blocked("MISMATCHED_SEC_VERDICT")
    matches = [row for row in filings if isinstance(row, Mapping)
               and row.get("accession") == accession]
    if len(matches) != 1:
        return _blocked("MISSING_OR_AMBIGUOUS_FILING")
    record = matches[0]
    if not filing_available_at_observation(index, record):
        return _blocked("FILING_NOT_AVAILABLE_AT_OBSERVATION")
    filed = _day(record.get("filed_at"))
    url = record.get("source_uri")
    prefix = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
              f"{accession.replace('-', '')}/")
    file_name = url[len(prefix):] if isinstance(url, str) and url.startswith(prefix) else ""
    if (record.get("provider") != "SEC_EDGAR" or record.get("issuer_cik") != cik
            or record.get("form") != "10-K"
            or record.get("index_source_uri") != index.get("source_uri")
            or record.get("index_raw_sha256") != digest
            or record.get("raw_sha256") is not None
            or record.get("evidence_status") != expected_status
            or filed is None or filed > cutoff or filed > collected.date()
            or numeric_verdict.get("filing_date") != filed.isoformat()
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", file_name)
            or ".." in file_name):
        return _blocked("INVALID_OR_UNLINKED_DL_RECORD")
    if (numeric_verdict.get("status") not in ("calculated_unverified", "conflict")
            or numeric_verdict.get("authenticated_external_source") is not False
            or numeric_verdict.get("live_api_called") is not False
            or numeric_verdict.get("source_rights_verified") is not False):
        return _blocked("UNTRUSTED_NUMERIC_VERDICT")

    return {
        **_blocked("STRUCTURAL_LINK_NOT_AUTHENTICATION"),
        "status": "linked_metadata_only",
        "trace_linked": True,
        "numeric_verdict_state": numeric_verdict["status"],
        "issuer_cik": cik,
        "accession": accession,
        "filing_date": filed.isoformat(),
        "submissions_sha256": digest,
        "filing_source_uri": url,
        "note": ("DL metadata and ProofInvest numeric verdict share CIK/accession/date "
                 "and UTC as-of eligibility. Neither SEC original filing nor "
                 "financial values have been independently authenticated."),
    }


def _original_blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": "proofinvest.dl-original-crosslink.v1",
        "status": "unavailable", "reason_code": reason,
        "span_metadata_linked": False,
        "authenticated_external_source": False,
        "numeric_facts_authenticated": False,
        "archived_bytes_rechecked": False,
        "live_api_called": False,
        "official_contest_submission": False,
    }


def assess_dl_original_handoff(link: Any, span: Any) -> dict[str, Any]:
    """Correlate validated KIC/DL metadata and a caller-supplied local byte span.

    This checks cross-document identity and plausible byte metadata. It does
    NOT re-read the archive, authenticate SEC, verify passage semantics, or
    trust escaped HTML supplied by an external caller. Use anchored_source_span
    first to read and hash-check an actual local archive.
    """
    if not isinstance(link, Mapping) or not isinstance(span, Mapping):
        return _original_blocked("MALFORMED_ORIGINAL_HANDOFF")
    if (link.get("status") != "linked_metadata_only"
            or link.get("trace_linked") is not True
            or link.get("authenticated_external_source") is not False
            or link.get("original_filing_downloaded") is not False
            or link.get("live_api_called") is not False
            or span.get("status") != "untrusted_original_span_for_review"
            or span.get("authenticated_external_source") is not False
            or span.get("numerical_claim_verified") is not False
            or span.get("live_api_called") is not False):
        return _original_blocked("UNTRUSTED_ORIGINAL_HANDOFF")

    if (span.get("issuer_cik") != link.get("issuer_cik")
            or span.get("accession") != link.get("accession")
            or not isinstance(link.get("filing_source_uri"), str)
            or span.get("source_uri") != link.get("filing_source_uri")
            or span.get("input_origin") not in (
                "OFFLINE_FILE_UNVERIFIED", "SEC_HTTPS_RESPONSE_UNVERIFIED"
            )):
        return _original_blocked("ORIGINAL_FILING_IDENTITY_MISMATCH")

    digest = span.get("filing_sha256")
    phrase = span.get("literal_ascii_phrase")
    if (not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(phrase, str) or not 4 <= len(phrase) <= 128
            or not phrase.isascii()
            or any(ord(ch) < 32 or ord(ch) > 126 for ch in phrase)):
        return _original_blocked("INVALID_ORIGINAL_SPAN_METADATA")
    fields = ("original_bytes_size", "start_byte", "end_byte_exclusive",
              "context_start_byte", "context_end_byte_exclusive")
    if any(type(span.get(field)) is not int for field in fields):
        return _original_blocked("INVALID_ORIGINAL_SPAN_METADATA")
    size, start, end, ctx_start, ctx_end = (span[field] for field in fields)
    if not (0 <= ctx_start <= start < end <= ctx_end <= size
            and end - start == len(phrase)):
        return _original_blocked("INVALID_ORIGINAL_SPAN_METADATA")

    return {
        **_original_blocked("STRUCTURAL_CROSSLINK_NOT_AUTHENTICATION"),
        "status": "linked_untrusted_original_span_for_review",
        "span_metadata_linked": True,
        "issuer_cik": link["issuer_cik"],
        "accession": link["accession"],
        "source_uri": link["filing_source_uri"],
        "original_filing_sha256": digest,
        "start_byte": start,
        "end_byte_exclusive": end,
        "note": ("CIK/accession/archive URL and byte-offset metadata match "
                 "caller-supplied records. SEC identity and facts are not verified."),
    }
