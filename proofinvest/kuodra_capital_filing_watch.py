"""Issuer SEC Submissions metadata-only capital/ownership follow-up queue.

No additional HTTP, historical pagination, ownership determination, dilution
inference, document downloading or source authentication. In particular, Forms
13D/13G and insider Forms 3/4/5 often live under the FILER's own CIK, not the
target issuer's Submissions. Their absence here never establishes absence.
"""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime, timezone
import re
from typing import Any, Mapping

from disclosure_lightning.core import MAX_JSON_BYTES, MAX_RECORDS, _observation_time, parse_day
from .local_sec_packet import _json_object

_CIK = re.compile(r"[0-9]{10}\Z", re.ASCII)
_ACC = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
# These are only candidate review forms. A form's presence is not proof that
# shares were issued or a person owns more than any particular threshold.
_FORMS = {
    "8-K": "EVENT_REPORT_NEEDS_ITEM_INSPECTION",
    "8-K/A": "EVENT_REPORT_AMENDMENT_NEEDS_INSPECTION",
    "S-3": "REGISTRATION_NOT_ISSUANCE_PROOF",
    "S-3/A": "REGISTRATION_AMENDMENT_NOT_ISSUANCE_PROOF",
    "S-1": "REGISTRATION_NOT_ISSUANCE_PROOF",
    "S-1/A": "REGISTRATION_AMENDMENT_NOT_ISSUANCE_PROOF",
    "424B2": "PROSPECTUS_NOT_FINAL_ALLOTMENT_PROOF",
    "424B3": "PROSPECTUS_NOT_FINAL_ALLOTMENT_PROOF",
    "424B4": "PROSPECTUS_NOT_FINAL_ALLOTMENT_PROOF",
    "424B5": "PROSPECTUS_NOT_FINAL_ALLOTMENT_PROOF",
    "DEF 14A": "PROXY_NOT_OWNERSHIP_PROOF",
    "SC 13D": "HOLDER_FILING_METADATA_ONLY",
    "SC 13D/A": "HOLDER_AMENDMENT_METADATA_ONLY",
    "SC 13G": "HOLDER_FILING_METADATA_ONLY",
    "SC 13G/A": "HOLDER_AMENDMENT_METADATA_ONLY",
    "3": "INSIDER_FILING_METADATA_ONLY",
    "4": "INSIDER_FILING_METADATA_ONLY",
    "5": "INSIDER_FILING_METADATA_ONLY",
}
_MAX_SHOW = 8


def _acceptance_availability(raw: Any, observation: datetime) -> str:
    """Compare a filing acceptance instant only if its timezone is explicit.

    SEC date-times without a timezone cannot safely be interpreted as UTC.
    """
    if raw is None or raw == "":
        return "time_unavailable"
    if type(raw) is not str or not 10 <= len(raw) <= 50 or not raw.isascii():
        raise ValueError("ACCEPTANCE_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("ACCEPTANCE_TIME_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if parsed.date() > observation.date():
            return "after_observation"
        return "time_unavailable"
    return ("known_before_observation" if parsed.astimezone(timezone.utc) <= observation
            else "after_observation")


def _out(reason: str, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "schema": "kuodra.issuer-capital-filing-watch.v1",
        "status": "unavailable",
        "reason_code": reason,
        "candidates": [],
        "total_matching_recent_metadata": 0,
        "display_truncated": False,
        "same_day_without_comparable_acceptance_omitted": 0,
        "accepted_after_observation_omitted": 0,
        "accepted_time_comparison_is_self_reported": True,
        "issuer_recent_window_only": True,
        "issuer_recent_window_may_omit_history": True,
        "other_filers_cik_not_queried": True,
        "absence_does_not_establish_no_issuance_or_ownership_change": True,
        "filing_contents_verified": False,
        "capital_change_verified": False,
        "beneficial_ownership_verified": False,
        "source_authenticated": False,
        "source_rights_verified": False,
        "guard_policy_modified": False,
        "live_api_called": False,
        "trade_executed": False,
        "submissions_sha256": sha256(raw).hexdigest() if type(raw) is bytes else None,
    }


def review_issuer_capital_filing_watch(
    submissions_json: bytes, *, cik: str, as_of: str, collected_at: str,
) -> dict[str, Any]:
    """Inspect existing local *issuer* submissions metadata, nothing else."""
    result = _out("INVALID_ISSUER_CAPITAL_WATCH_INPUT", submissions_json)
    if type(cik) is not str or _CIK.fullmatch(cik) is None or cik == "0000000000":
        return result
    try:
        cutoff = parse_day(as_of)
        observation = _observation_time(collected_at, cutoff=cutoff)
        doc = _json_object(submissions_json, limit=MAX_JSON_BYTES)
    except (ValueError, TypeError, RecursionError, OverflowError):
        result["reason_code"] = "SUBMISSIONS_OR_AS_OF_INVALID"
        return result
    issuer = doc.get("cik")
    if (type(issuer) not in (str, int) or isinstance(issuer, bool)
            or not str(issuer).isascii() or not str(issuer).isdecimal()
            or len(str(issuer)) > 10 or str(int(issuer)).zfill(10) != cik):
        result["reason_code"] = "SUBMISSIONS_ISSUER_MISMATCH"
        return result
    filings = doc.get("filings")
    recent = filings.get("recent") if isinstance(filings, Mapping) else None
    if not isinstance(recent, Mapping):
        result["reason_code"] = "RECENT_FILING_WINDOW_UNAVAILABLE"
        return result
    names = ("accessionNumber", "form", "filingDate", "primaryDocument")
    columns = [recent.get(k) for k in names]
    if (any(type(x) is not list for x in columns)
            or len(columns[0]) > MAX_RECORDS
            or any(len(x) != len(columns[0]) for x in columns)):
        result["reason_code"] = "RECENT_FILING_COLUMNS_INVALID"
        return result
    a, forms, days, docs = columns
    accepted = recent.get("acceptanceDateTime")
    if accepted is not None and (
            type(accepted) is not list or len(accepted) != len(a)):
        result["reason_code"] = "RECENT_ACCEPTANCE_COLUMNS_INVALID"
        return result
    seen: set[str] = set()
    matches: list[dict[str, str]] = []
    observed_day = parse_day(observation[:10])
    observed_instant = datetime.fromisoformat(observation.replace("Z", "+00:00"))
    unresolved_same_day = 0
    later_acceptance = 0
    for i, form in enumerate(forms):
        if form not in _FORMS:
            continue
        accession, day, docname = a[i], days[i], docs[i]
        if (type(accession) is not str or _ACC.fullmatch(accession) is None
                or accession in seen or type(docname) is not str
                or not 1 <= len(docname) <= 256):
            result["reason_code"] = "MALFORMED_CAPITAL_FILING_METADATA"
            return result
        seen.add(accession)
        try:
            filed = parse_day(day)
        except ValueError:
            result["reason_code"] = "MALFORMED_CAPITAL_FILING_DATE"
            return result
        if filed > cutoff or filed > observed_day:
            continue
        try:
            availability = _acceptance_availability(
                accepted[i] if accepted is not None else None,
                observed_instant,
            )
        except ValueError:
            result["reason_code"] = "RECENT_ACCEPTANCE_TIME_INVALID"
            return result
        if availability == "after_observation":
            later_acceptance += 1
            continue
        if availability == "time_unavailable" and filed == observed_day:
            unresolved_same_day += 1
            continue
        matches.append({
            "form": form, "accession": accession,
            "filed_at": filed.isoformat(),
            "review_class": _FORMS[form],
            "document_not_fetched": "true",
            "availability_basis": (
                "EXPLICIT_ACCEPTANCE_NOT_LATER_THAN_REPORTED_COLLECTION"
                if availability == "known_before_observation"
                else "PRIOR_FILING_DAY_ONLY_ACCEPTANCE_INSTANT_UNVERIFIED"
            ),
        })
    matches.sort(key=lambda x: (x["filed_at"], x["accession"]), reverse=True)
    result.update(
        status="metadata_candidates_unverified" if matches
               else "no_candidates_in_limited_issuer_index",
        reason_code="DOCUMENT_CONTENT_AND_CROSS_FILER_SEARCH_REQUIRED" if matches
                    else "NO_CANDIDATES_IS_NOT_NEGATIVE_EVIDENCE",
        candidates=matches[:_MAX_SHOW],
        total_matching_recent_metadata=len(matches),
        display_truncated=len(matches) > _MAX_SHOW,
        same_day_without_comparable_acceptance_omitted=unresolved_same_day,
        accepted_after_observation_omitted=later_acceptance,
    )
    return result
