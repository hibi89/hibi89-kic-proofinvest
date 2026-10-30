"""Bounded offline SEC older-history page adapter for KUODRA.

This intentionally consumes a caller-provided manifest plus ONE selected
filings.files page. It does not fetch SEC, infer a source's authenticity,
rewrite recent records, or silently treat a page as the recent response.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from disclosure_lightning import core

_NAME = re.compile(r"CIK[0-9]{10}-submissions-[0-9]{3}\.json\Z", re.ASCII)
_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)


def index_pinned_history(
    *, base_raw: bytes, history_raw: bytes, page_name: str, cik: str,
    as_of: str, collected_at: str,
) -> dict:
    """Produce a real DL-compatible index using the HISTORY bytes/hash only.

    The base submissions raw SHA is retained separately; this is NOT a
    synthetic recent response and cannot masquerade as one. Only old
    eligible 10-K filings enter the index.
    """
    target = core.cik10(cik)
    cutoff = core.parse_day(as_of)
    observed = core._observation_time(collected_at, cutoff=cutoff)
    observed_at = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    base = core._validate_raw(base_raw)
    if type(base.get("cik")) not in (str, int) or str(base["cik"]).zfill(10) != target:
        raise ValueError("BASE_CIK_MISMATCH")
    filings = base.get("filings")
    if not isinstance(filings, dict) or not isinstance(filings.get("recent"), dict):
        raise ValueError("BASE_RECENT_MISSING")
    # Validate the original recent structure, but never rewrite or re-label it.
    indexed_recent = core.index_submissions(
        base_raw, cik=target, as_of=as_of,
        forms=frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"}),
        provenance="OFFLINE_UNVERIFIED", collected_at=collected_at,
    )
    if not isinstance(page_name, str) or _NAME.fullmatch(page_name) is None:
        raise ValueError("UNSAFE_HISTORY_FILENAME")
    if not page_name.startswith(f"CIK{target}-submissions-"):
        raise ValueError("HISTORY_CIK_NAME_MISMATCH")
    pages = filings.get("files")
    if not isinstance(pages, list) or len(pages) > 256:
        raise ValueError("INVALID_HISTORY_MANIFEST")
    matches = [x for x in pages if isinstance(x, dict) and x.get("name") == page_name]
    if len(matches) != 1:
        raise ValueError("UNPINNED_OR_DUPLICATE_HISTORY_PAGE")
    spec = matches[0]
    first = core.parse_day(spec.get("filingFrom"))
    last = core.parse_day(spec.get("filingTo"))
    count = spec.get("filingCount")
    if first > last or type(count) is not int or not 1 <= count <= 10000:
        raise ValueError("INVALID_HISTORY_MANIFEST_RANGE")
    history = core._validate_raw(history_raw)
    if any(k in history for k in ("cik", "filings")):
        raise ValueError("EXPECTED_UNWRAPPED_HISTORY_PAGE")
    accessions = history.get("accessionNumber")
    if not isinstance(accessions, list) or len(accessions) != count:
        raise ValueError("HISTORY_COUNT_MISMATCH")
    for field, values in history.items():
        if not isinstance(values, list) or len(values) != count:
            raise ValueError("HISTORY_COLUMN_MISMATCH:" + str(field)[:32])
    forms = core._column(history, "form", count)
    days = core._column(history, "filingDate", count)
    docs = core._column(history, "primaryDocument", count)
    accepted = history.get("acceptanceDateTime")
    seen: set[str] = set()
    records = []
    digest = hashlib.sha256(history_raw).hexdigest()
    uri = f"https://data.sec.gov/submissions/{page_name}"
    recent_ids = {x["accession"] for x in indexed_recent["filings"]}
    for i, accession in enumerate(accessions):
        if (not isinstance(accession, str) or _ACCESSION.fullmatch(accession) is None
                or not accession.startswith(target + "-") or accession in seen):
            raise ValueError("HISTORY_ACCESSION_INVALID_OR_DUPLICATE")
        seen.add(accession)
        filed = core.parse_day(days[i])
        if not first <= filed <= last:
            raise ValueError("HISTORY_DATE_OUTSIDE_PINNED_RANGE")
        form = forms[i]
        if form not in core.ALLOWED_FORMS:
            continue
        original_uri = core._source_uri(target, accession, docs[i])
        if original_uri is None:
            raise ValueError("INVALID_HISTORY_ORIGINAL_DOCUMENT")
        accepted_text = core._accepted(accepted[i]) if accepted is not None else None
        accepted_at = (datetime.fromisoformat(accepted_text).astimezone(timezone.utc)
                       if accepted_text is not None else None)
        # Date-only/naive same-day evidence may not be known at observation time.
        if filed > cutoff or filed > observed_at.date():
            continue
        if accepted_at is not None and accepted_at > observed_at:
            continue
        if filed == observed_at.date() and accepted_at is None:
            continue
        if accession in recent_ids:
            raise ValueError("HISTORY_DUPLICATES_RECENT_ACCESSION")
        if form != "10-K":
            continue
        records.append({
            "schema_version": "1.0", "provider": core.PROVIDER,
            "issuer_cik": target, "accession": accession, "form": form,
            "filed_at": filed.isoformat(), "accepted_at": accepted_text,
            "collected_at": observed, "source_uri": original_uri,
            "index_source_uri": uri, "index_raw_sha256": digest,
            "raw_sha256": None, "as_of_cutoff": cutoff.isoformat(),
            "amends_accession": None,
            "evidence_status": "OFFLINE_SOURCE_UNVERIFIED",
        })
    return {
        "schema_version": "1.0", "provider": core.PROVIDER,
        "issuer_cik": target,
        "issuer_name": str(base.get("name", ""))[:300],
        "source_sha256": digest, "source_bytes": len(history_raw),
        "source_uri": uri, "provenance": "OFFLINE_UNVERIFIED",
        "collected_at": observed, "as_of_cutoff": cutoff.isoformat(),
        "filings": records, "indexed_count": len(records),
        "base_manifest_sha256": hashlib.sha256(base_raw).hexdigest(),
        "history_page_name": page_name,
        "status": "PINNED_HISTORY_OFFLINE_UNVERIFIED",
    }


def assess_history_verdict(index: Any, verdict: Any) -> dict:
    """Bind the historical receipt to ONE original SEC CompanyFacts claim."""
    def deny(reason):
        return {"status": "unavailable", "reason_code": reason,
                "authenticated_external_source": False, "live_api_called": False}
    if not isinstance(index, Mapping) or not isinstance(verdict, Mapping):
        return deny("INVALID_HISTORY_LINK")
    target = index.get("issuer_cik")
    accession = verdict.get("accession")
    if (index.get("status") != "PINNED_HISTORY_OFFLINE_UNVERIFIED"
            or index.get("provenance") != "OFFLINE_UNVERIFIED"
            or index.get("provider") != "SEC_EDGAR"
            or verdict.get("cik") != target
            or verdict.get("as_of") != index.get("as_of_cutoff")
            or verdict.get("authenticated_external_source") is not False
            or verdict.get("live_api_called") is not False
            or verdict.get("source_rights_verified") is not False
            or verdict.get("status") not in ("calculated_unverified", "conflict")):
        return deny("HISTORY_VERDICT_CONTRACT_MISMATCH")
    matches = [f for f in index.get("filings", [])
               if isinstance(f, dict) and f.get("accession") == accession]
    if len(matches) != 1:
        return deny("HISTORY_FILING_MISSING_OR_AMBIGUOUS")
    rec = matches[0]
    if (rec.get("issuer_cik") != target or rec.get("form") != "10-K"
            or rec.get("index_source_uri") != index.get("source_uri")
            or rec.get("index_raw_sha256") != index.get("source_sha256")
            or rec.get("evidence_status") != "OFFLINE_SOURCE_UNVERIFIED"
            or rec.get("raw_sha256") is not None
            or rec.get("filed_at") != verdict.get("filing_date")):
        return deny("HISTORY_OR_NUMERIC_SOURCE_MISMATCH")
    return {
        "status": "linked_metadata_only", "trace_linked": True,
        "issuer_cik": target, "accession": accession,
        "filing_date": rec["filed_at"], "filing_source_uri": rec["source_uri"],
        "authenticated_external_source": False,
        "original_filing_downloaded": False,
        "live_api_called": False,
        "base_manifest_sha256": index["base_manifest_sha256"],
        "history_sha256": index["source_sha256"],
    }
