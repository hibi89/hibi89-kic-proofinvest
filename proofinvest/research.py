"""Offline, deterministic evidence normalization for ProofInvest Research.

Checks traceability and timestamps, not factual truth or license legality.
No I/O, remote calls, LLM use, or external dependencies.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit
import re


def _day(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        if "T" not in value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _instant(value: Any) -> datetime | None:
    """Parse an offset-aware timestamp only; date-only records have day precision.

    Compare in UTC to prevent same-day or cross-offset ordering errors.
    An invalid timestamp is still rejected by the existing _day guard.
    """
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _known_day(value: Any) -> date | None:
    """UTC calendar day for offset-aware moments, legacy day otherwise.

    The request's date-only as_of is treated as the end of that UTC day.
    Avoid mistaking a late -12:00 release for evidence available yesterday.
    """
    instant = _instant(value)
    return instant.date() if instant is not None else _day(value)


def _https_url(value: Any) -> bool:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        url = urlsplit(value)
        return (
            url.scheme == "https" and url.hostname is not None
            and "." in url.hostname and not url.username and not url.password
            and url.port != 0
        )
    except ValueError:
        return False


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_research(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize pre-supplied records without inventing or fetching evidence.

    The internal (not cross-module approved) input is:
      target_name: str, target_id?: str, as_of: ISO date,
      sources: [{id,title,url,published_at,collected_at,license}],
      findings: [{claim,source_ids,as_of}].

    Rejected records remain visible only as warning codes, never as evidence.
    Two distinct IDs that claim the same exact HTTPS URL are both removed;
    URL aliases/tracking parameters are NOT normalized or authenticated.
    An input license label is untrusted, NOT legal rights evidence.
    Accepted source metadata always marks redistribution as unestablished
    until a distinct human/legal permission check (not implemented here).
    """
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    result: dict[str, Any] = {
        "status": "unavailable",
        "source_kind": "PROVIDED_OFFLINE_RECORDS",
        "target": {"name": payload.get("target_name"), "id": payload.get("target_id")},
        "as_of": payload.get("as_of"),
        "sources": [],
        "findings": [],
        "warnings": [],
    }

    def warn(code: str, detail: str) -> None:
        result["warnings"].append({"code": code, "detail": detail})

    name = payload.get("target_name")
    target_id = payload.get("target_id")
    as_of = _day(payload.get("as_of"))
    if not _text(name) or (target_id is not None and not _text(target_id)) or as_of is None:
        warn("invalid_request", "target_name, optional target_id or as_of invalid")
        return result
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", payload["as_of"]):
        warn("invalid_request", "as_of must be an ISO calendar date")
        return result
    sources = payload.get("sources", [])
    findings = payload.get("findings", [])
    if not isinstance(sources, list) or not isinstance(findings, list):
        warn("invalid_collection", "sources and findings must be lists")
        return result

    seen: dict[str, dict[str, Any]] = {}
    accepted: dict[str, dict[str, Any]] = {}
    conflicted: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            warn("invalid_source", f"source[{index}] is not a record")
            continue
        sid = source.get("id")
        if not _text(sid):
            warn("invalid_source", f"source[{index}] has no id")
            continue
        if sid in seen:
            if source != seen[sid]:
                conflicted.add(sid)
                warn("source_id_conflict", f"source id {sid!r} has divergent records")
            continue
        seen[sid] = source
        required = ("id", "title", "url", "published_at", "collected_at", "license")
        if not all(_text(source.get(key)) for key in required):
            warn("invalid_source", f"source id {sid!r} has missing required fields")
            continue
        if not _https_url(source["url"]):
            warn("invalid_source_url", f"source id {sid!r} has no valid HTTPS URL")
            continue
        published = _day(source["published_at"])
        collected = _day(source["collected_at"])
        if published is None or collected is None:
            warn("invalid_source_date", f"source id {sid!r} has invalid chronology")
            continue
        # Explicit-offset timestamps must be ordered by the same UTC clock.
        # A valid collection can have an EARLIER local calendar date when the
        # source/collector use different offsets (e.g. +14:00 versus UTC).
        # Fall back to local day comparison if either value is date-only;
        # its unknown time of day cannot be reliably compared as an instant.
        published_at = _instant(source["published_at"])
        collected_at = _instant(source["collected_at"])
        if published_at is not None and collected_at is not None:
            collected_too_early = collected_at < published_at
        else:
            collected_too_early = collected < published
        if collected_too_early:
            warn("invalid_source_date", f"source id {sid!r} has invalid publication/collection chronology")
            continue
        if _known_day(source["published_at"]) > as_of:
            warn("future_published", f"source id {sid!r} was published after requested as_of")
            continue
        # A past as_of snapshot cannot rely on evidence collected later.
        # Publication alone does not prove the analyst had acquired it.
        if _known_day(source["collected_at"]) > as_of:
            warn("future_collected", f"source id {sid!r} was collected after requested as_of")
            continue
        # A caller's license label is merely metadata: it is not evidence
        # that the publisher granted republication or commercial re-use.
        # Keep citation usability separate from legal redistribution clearance.
        accepted[sid] = {
            **{key: source[key] for key in required},
            "rights_review_status": "not_verified",
            "redistribution_clearance": "not_established",
        }

    for sid in conflicted:
        accepted.pop(sid, None)

    # Source IDs are caller-assigned labels, not proof of independent sources.
    # Distinct IDs pointing at the exact same URL cannot count as two
    # references, especially when their metadata or licenses disagree.
    url_to_ids: dict[str, list[str]] = {}
    for sid, source in accepted.items():
        url_to_ids.setdefault(source["url"], []).append(sid)
    for ids in url_to_ids.values():
        if len(ids) > 1:
            warn("duplicate_source_url", f"one URL assigned multiple source IDs: {ids!r}")
            for sid in ids:
                accepted.pop(sid, None)
    result["sources"] = list(accepted.values())

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or not _text(finding.get("claim")):
            warn("invalid_claim", f"finding[{index}] has no claim")
            continue
        finding_day = _known_day(finding.get("as_of"))
        if finding_day is None or finding_day > as_of:
            warn("invalid_finding_date", f"finding[{index}] has invalid or future as_of")
            continue
        ids = finding.get("source_ids")
        if not isinstance(ids, list) or not ids or any(not _text(sid) for sid in ids):
            warn("missing_source_ids", f"finding[{index}] has no usable source_ids")
            continue
        deduped = list(dict.fromkeys(ids))
        missing = [sid for sid in deduped if sid not in accepted]
        if missing:
            warn("unavailable_evidence", f"finding[{index}] references unavailable ids: {missing!r}")
            continue
        if any(_known_day(accepted[sid]["published_at"]) > finding_day for sid in deduped):
            warn("finding_precedes_source", f"finding[{index}] predates its cited source")
            continue
        if any(_known_day(accepted[sid]["collected_at"]) > finding_day for sid in deduped):
            warn("finding_precedes_collection", f"finding[{index}] predates collection of cited evidence")
            continue
        result["findings"].append({
            "claim": finding["claim"].strip(),
            "source_ids": deduped,
            "as_of": finding["as_of"],
        })

    if not result["findings"]:
        warn("no_supported_findings", "no claim has complete, time-valid linked evidence")
    result["status"] = (
        "unavailable" if not result["findings"]
        else "partial" if result["warnings"] else "success"
    )
    return result
