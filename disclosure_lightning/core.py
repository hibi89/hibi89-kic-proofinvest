"""Disclosure Lightning MVP: bounded SEC submissions → immutable local evidence.

No implicit network. No finance claims. Standard-library only. Public-source
metadata alone is NOT verification of original filing document content.
"""
from __future__ import annotations

import argparse
from email.utils import parsedate_to_datetime
import hashlib
import http.client
import json
import os
import re
import sqlite3
import stat
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROVIDER = "SEC_EDGAR"
MAX_JSON_BYTES = 8_000_000
MAX_RECORDS = 1000
MAX_HISTORY_RECORDS = 10_000
MAX_HTTP_ATTEMPTS = 3
MAX_RETRY_DELAY_SECONDS = 30
MIN_RETRY_DELAY_SECONDS = 0.2
RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
ETAG_PATTERN = re.compile(r'(?:W/)?"[\x21\x23-\x7e]*"\Z', re.ASCII)
ALLOWED_FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"})
CONTACT_PATTERN = re.compile(r"[A-Za-z0-9_.+%-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}")


def cik10(raw: str) -> str:
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{1,10}", raw, flags=re.ASCII) or not int(raw):
        raise ValueError("CIK must be a positive 1-to-10 digit ASCII number")
    return raw.zfill(10)


def parse_day(raw: str) -> date:
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        raise ValueError("Date must use YYYY-MM-DD")
    try:
        result = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc
    if result.isoformat() != raw:
        raise ValueError("Invalid calendar date")
    return result


def parse_forms(raw: str) -> frozenset[str]:
    parts = raw.split(",") if isinstance(raw, str) else []
    forms = frozenset(piece.strip() for piece in parts)
    if not forms or "" in forms or not forms.issubset(ALLOWED_FORMS):
        raise ValueError("Only supported SEC form types may be requested")
    return forms


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _valid_etag(value: Any) -> bool:
    return (isinstance(value, str) and len(value) <= 512
            and ETAG_PATTERN.fullmatch(value) is not None)


def _retry_after_delay(value: str | None, *, attempt: int,
                       now: datetime | None = None) -> float | None:
    """Return a bounded Retry-After delay, or None when its wait is excessive."""
    fallback = 0.5 * (2 ** attempt)
    if not isinstance(value, str) or not value.strip():
        return fallback
    value = value.strip()
    if value.isascii() and value.isdecimal():
        normalized = value.lstrip("0") or "0"
        if len(normalized) > len(str(MAX_RETRY_DELAY_SECONDS)):
            return None
        delay = float(int(normalized))
    else:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None or retry_at.utcoffset() is None:
                return fallback
            reference = now or datetime.now(timezone.utc)
            if reference.tzinfo is None or reference.utcoffset() is None:
                return fallback
            delay = max(0.0, (retry_at.astimezone(timezone.utc)
                              - reference.astimezone(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return fallback
    if delay > MAX_RETRY_DELAY_SECONDS:
        return None
    return max(MIN_RETRY_DELAY_SECONDS, delay)


def _bounded_sec_get(opener, request, read_response, *, read_not_modified=None):
    """Retry only transient, safe SEC GET failures within a fixed time budget."""
    for attempt in range(MAX_HTTP_ATTEMPTS):
        try:
            with opener.open(request, timeout=15) as response:
                return read_response(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and read_not_modified is not None:
                try:
                    return read_not_modified(exc)
                finally:
                    exc.close()
            if exc.code not in RETRYABLE_HTTP_STATUSES:
                exc.close()
                raise
            if attempt + 1 >= MAX_HTTP_ATTEMPTS:
                exc.close()
                raise ValueError(
                    f"SEC transient HTTP status {exc.code} after {MAX_HTTP_ATTEMPTS} attempts"
                ) from exc
            delay = _retry_after_delay(exc.headers.get("Retry-After"), attempt=attempt)
            if delay is None:
                exc.close()
                raise ValueError(
                    "SEC Retry-After exceeds the 30-second retry wait budget"
                ) from exc
            exc.close()
            time.sleep(delay)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError):
            if attempt + 1 >= MAX_HTTP_ATTEMPTS:
                raise
            time.sleep(_retry_after_delay(None, attempt=attempt))
    raise AssertionError("bounded SEC GET exhausted without a result or exception")


def _observation_time(raw: str, *, cutoff: date) -> str:
    """Require a real UTC instant no later than the historical as-of date.

    Caller-supplied offline times are NOT independently authenticated.
    """
    if (not isinstance(raw, str) or len(raw) > 50 or
            "T" not in raw or not raw.isascii()):
        raise ValueError("UTC observation timestamp with offset required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observation timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Observation timestamp must contain a timezone")
    utc = parsed.astimezone(timezone.utc)
    if utc.date() > cutoff:
        raise ValueError("COLLECTION_AFTER_AS_OF: later retrieval is not historical evidence")
    return utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def _valid_user_agent(raw: str) -> bool:
    if (not isinstance(raw, str) or not 12 <= len(raw) <= 160
            or not raw.isascii() or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw)):
        return False
    found = CONTACT_PATTERN.search(raw)
    if found is None:
        return False
    domain = found.group().rsplit("@", 1)[1].lower()
    labels = domain.split(".")
    return not (
        domain in {"example.com", "example.org", "example.net", "test.com",
                   "test.org", "test.net", "localhost"}
        or labels[-1] in {"test", "invalid", "local", "example", "tld"}
        or any(part.startswith(("example", "placeholder", "your-")) for part in labels)
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str):
    raise ValueError(f"Non-standard JSON numeric constant: {value}")


def _validate_raw(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise ValueError("SEC submissions JSON must be 1..8MB")
    try:
        payload = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 SEC submissions JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Submissions root must be a JSON object")
    return payload


def _read_local_json(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Read one bounded regular offline input without following symlinks."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("Offline JSON size limit must be a positive integer")
    source = Path(path).expanduser()
    if source.is_symlink():
        raise ValueError("Offline JSON symlink input is forbidden")
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= max_bytes:
            raise ValueError("Offline JSON must be a bounded regular file")
        raw = handle.read(max_bytes + 1)
    if not 0 < len(raw) <= max_bytes:
        limit_label = f"{max_bytes // 1_000_000}MB" if max_bytes % 1_000_000 == 0 else str(max_bytes)
        raise ValueError(f"Offline JSON must be 1..{limit_label}")
    return raw


def _column(recent: dict, key: str, n: int) -> list:
    column = recent.get(key)
    if not isinstance(column, list) or len(column) != n:
        raise ValueError(f"SEC filings.recent.{key} must be an aligned array")
    return column


def _source_uri(cik: str, accession: str, primary: str) -> str | None:
    if (not isinstance(primary, str) or len(primary) > 200 or
            not re.fullmatch(r"[A-Za-z0-9_.-]+", primary, flags=re.ASCII) or
            primary.startswith(".") or ".." in primary):
        return None
    return ("https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession.replace('-', '')}/{primary}")


def _accepted(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    # SEC returns e.g. 2025-10-31T18:20:01.000Z or no zone; don't
    # convert a naive clock to UTC or imply availability-at was verified.
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat() if parsed.tzinfo else None


def index_submissions(
    raw: bytes, *, cik: str, as_of: str, forms: frozenset[str],
    provenance: str = "OFFLINE_UNVERIFIED", collected_at: str | None = None,
) -> dict:
    """Index a bounded recent-filings window, rejecting malformed source shape.

    A filing index has original SEC-submissions response bytes but not its
    full HTML/XBRL filing content. Source authentication is caller-specific.
    """
    target = cik10(cik)
    cutoff = parse_day(as_of)
    if not forms or not forms.issubset(ALLOWED_FORMS):
        raise ValueError("Unsupported SEC forms")
    if provenance not in ("OFFLINE_UNVERIFIED", "SEC_HTTPS_RESPONSE"):
        raise ValueError("Invalid provenance level")
    payload = _validate_raw(raw)
    observed = payload.get("cik")
    if (type(observed) not in (int, str) or not str(observed).isascii()
            or not str(observed).isdecimal() or not int(str(observed))
            or str(int(str(observed))).zfill(10) != target):
        raise ValueError("SEC issuer CIK differs from requested CIK")
    recent = payload.get("filings")
    recent = recent.get("recent") if isinstance(recent, dict) else None
    if not isinstance(recent, dict):
        raise ValueError("Expected SEC filings.recent column arrays")
    accessions = recent.get("accessionNumber")
    if not isinstance(accessions, list) or len(accessions) > MAX_RECORDS:
        raise ValueError("SEC recent accession array missing or excessive")
    n = len(accessions)
    kinds = _column(recent, "form", n)
    days = _column(recent, "filingDate", n)
    docs = _column(recent, "primaryDocument", n)
    accepted = recent.get("acceptanceDateTime")
    if accepted is not None and (not isinstance(accepted, list) or len(accepted) != n):
        raise ValueError("SEC acceptance timestamps have mismatched count")
    observation_time = _observation_time(collected_at or _timestamp(), cutoff=cutoff)
    observation_day = date.fromisoformat(observation_time[:10])
    observed_instant = datetime.fromisoformat(observation_time.replace("Z", "+00:00"))
    digest = hashlib.sha256(raw).hexdigest()
    entries = []
    seen = set()
    for i, accession in enumerate(accessions):
        form = kinds[i]
        if form not in forms:
            continue
        if not isinstance(accession, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
            raise ValueError(f"Invalid SEC accession at row {i}")
        if accession in seen:
            raise ValueError("Duplicate accession in one SEC submissions response")
        seen.add(accession)
        filed = parse_day(days[i])
        if filed > cutoff or filed > observation_day:
            continue
        accepted_at = _accepted(accepted[i]) if accepted is not None else None
        if accepted_at is None and filed == observation_day:
            # A same-day filing without an offset-aware acceptance instant
            # cannot be shown to exist at this particular UTC time.
            continue
        if (accepted_at is not None
                and datetime.fromisoformat(accepted_at).astimezone(timezone.utc) > observed_instant):
            # A timestamp that occurs after the local observation could not
            # have been observed then; skip rather than backdate availability.
            continue
        uri = _source_uri(target, accession, docs[i])
        entries.append({
            "schema_version": "1.0", "provider": PROVIDER, "issuer_cik": target,
            "accession": accession, "form": form, "filed_at": filed.isoformat(),
            "accepted_at": accepted_at,
            "collected_at": observation_time, "source_uri": uri,
            "index_source_uri": f"https://data.sec.gov/submissions/CIK{target}.json",
            "index_raw_sha256": digest, "raw_sha256": None,
            "as_of_cutoff": cutoff.isoformat(), "amends_accession": None,
            "evidence_status": "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED"
                               if provenance == "SEC_HTTPS_RESPONSE"
                               else "OFFLINE_SOURCE_UNVERIFIED",
        })
    return {
        "schema_version": "1.0", "provider": PROVIDER,
        "issuer_cik": target,
        "issuer_name": str(payload.get("name", ""))[:300],
        "source_sha256": digest, "source_bytes": len(raw),
        "source_uri": f"https://data.sec.gov/submissions/CIK{target}.json",
        "provenance": provenance, "collected_at": observation_time,
        "as_of_cutoff": cutoff.isoformat(),
        "filings": entries, "indexed_count": len(entries),
        "note": "RECENT_ONLY; paginated historical SEC submission files not fetched. "
                "Amendment relationships not independently established.",
    }


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS observations(
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    issuer_cik TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    response BLOB NOT NULL,
    seen_at TEXT NOT NULL,
    provenance TEXT NOT NULL,
    UNIQUE(provider,issuer_cik,sha256)
);
CREATE TABLE IF NOT EXISTS observation_checks(
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    checked_at TEXT NOT NULL,
    provenance TEXT NOT NULL,
    PRIMARY KEY(observation_id,checked_at,provenance)
);
CREATE TABLE IF NOT EXISTS http_validators(
    provider TEXT NOT NULL,
    issuer_cik TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    etag TEXT NOT NULL,
    response_sha256 TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(provider,issuer_cik,source_uri),
    FOREIGN KEY(provider,issuer_cik,response_sha256)
      REFERENCES observations(provider,issuer_cik,sha256)
);
CREATE TABLE IF NOT EXISTS filings(
    provider TEXT NOT NULL,
    issuer_cik TEXT NOT NULL,
    accession TEXT NOT NULL,
    filing_json TEXT NOT NULL,
    first_observation_id INTEGER NOT NULL REFERENCES observations(id),
    PRIMARY KEY(provider,issuer_cik,accession)
);
CREATE TABLE IF NOT EXISTS filing_observations(
    filing_cik TEXT NOT NULL,
    accession TEXT NOT NULL,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    PRIMARY KEY(filing_cik,accession,observation_id)
);
CREATE TABLE IF NOT EXISTS history_page_receipts(
    issuer_cik TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    page_name TEXT NOT NULL,
    page_sha256 TEXT NOT NULL,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    record_count INTEGER NOT NULL,
    PRIMARY KEY(issuer_cik,manifest_sha256,page_name)
);
CREATE TABLE IF NOT EXISTS history_page_receipt_versions(
    issuer_cik TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    page_name TEXT NOT NULL,
    page_sha256 TEXT NOT NULL,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    record_count INTEGER NOT NULL,
    PRIMARY KEY(issuer_cik,manifest_sha256,page_name,page_sha256)
);
"""


def _validate_index_for_save(raw: bytes, indexed: dict, db_path: Path) -> None:
    """Reject caller-edited index metadata that is not supported by raw bytes."""
    digest = hashlib.sha256(raw).hexdigest()
    if (indexed.get("schema_version") != "1.0"
            or indexed.get("source_sha256") != digest
            or indexed.get("source_bytes") != len(raw)
            or indexed.get("provider") != PROVIDER):
        raise ValueError("Index source digest, size, or schema does not match bytes")
    target = cik10(indexed.get("issuer_cik"))
    cutoff = parse_day(indexed.get("as_of_cutoff"))
    observed = _observation_time(indexed.get("collected_at"), cutoff=cutoff)
    if observed != indexed.get("collected_at"):
        raise ValueError("Index observation timestamp is not canonical")
    provenance = indexed.get("provenance")
    if provenance not in ("OFFLINE_UNVERIFIED", "SEC_HTTPS_RESPONSE"):
        raise ValueError("Invalid index provenance")

    payload = _validate_raw(raw)
    if "cik" in payload:
        source_cik = payload.get("cik")
        if (type(source_cik) not in (int, str) or not str(source_cik).isascii()
                or not str(source_cik).isdecimal() or not int(str(source_cik))
                or cik10(str(int(str(source_cik)))) != target):
            raise ValueError("Index issuer CIK does not match source bytes")
        recent = payload.get("filings")
        recent = recent.get("recent") if isinstance(recent, dict) else None
        expected_uri = f"https://data.sec.gov/submissions/CIK{target}.json"
        history = False
    else:
        # Historical continuation files are unwrapped arrays whose name was
        # already constrained by the pinned manifest during indexing.
        recent = payload
        source_uri = indexed.get("source_uri")
        if (not isinstance(source_uri, str) or re.fullmatch(
                rf"https://data\.sec\.gov/submissions/CIK{target}-submissions-[0-9]{{3}}\.json",
                source_uri, flags=re.ASCII) is None
                or not isinstance(indexed.get("history_manifest_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", indexed["history_manifest_sha256"],
                                flags=re.ASCII) is None
                or provenance != "OFFLINE_UNVERIFIED"):
            raise ValueError("Historical index source is not bound to a pinned page")
        expected_uri = source_uri
        history = True
    if not isinstance(recent, dict):
        raise ValueError("Index source filing arrays are missing")
    accessions = recent.get("accessionNumber")
    if not isinstance(accessions, list):
        raise ValueError("Index source accession array is missing")
    n = len(accessions)
    if n > (MAX_HISTORY_RECORDS if history else MAX_RECORDS):
        raise ValueError("Index source row limit exceeded")
    page_spec = None
    manifest_first_seen = None
    if history:
        from .history import _stored_manifest

        _, authority = _stored_manifest(
            db_path, target, indexed["history_manifest_sha256"]
        )
        page_name = expected_uri.rsplit("/", 1)[-1]
        page_spec = authority["pages"].get(page_name)
        if page_spec is None or page_spec["count"] != n:
            raise ValueError("Historical page is not listed with this row count in pinned manifest")
        manifest_first_seen = authority["first_seen"]
    forms = _column(recent, "form", n)
    days = _column(recent, "filingDate", n)
    documents = _column(recent, "primaryDocument", n)
    accepted = recent.get("acceptanceDateTime")
    if accepted is not None and (not isinstance(accepted, list) or len(accepted) != n):
        raise ValueError("Index source acceptance timestamps are misaligned")
    by_accession: dict[str, int] = {}
    for i, accession in enumerate(accessions):
        if isinstance(accession, str):
            if accession in by_accession:
                raise ValueError("Duplicate source accession prevents safe index save")
            by_accession[accession] = i

    records = indexed.get("filings")
    if (not isinstance(records, list) or type(indexed.get("indexed_count")) is not int
            or indexed["indexed_count"] != len(records)
            or indexed.get("source_uri") != expected_uri):
        raise ValueError("Index summary does not match source bytes")
    observed_day = date.fromisoformat(observed[:10])
    observed_instant = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    if manifest_first_seen is not None and observed_instant < manifest_first_seen:
        raise ValueError("Historical page observation predates its pinned manifest")
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Indexed filing record must be an object")
        accession = record.get("accession")
        if (not isinstance(accession, str) or accession not in by_accession
                or accession in seen):
            raise ValueError("Indexed accession is absent or duplicated in source bytes")
        seen.add(accession)
        i = by_accession[accession]
        filed = parse_day(days[i])
        if page_spec is not None and (filed < page_spec["first"] or filed > page_spec["last"]):
            raise ValueError("Historical filing is outside pinned manifest date range")
        accepted_at = _accepted(accepted[i]) if accepted is not None else None
        if (record.get("schema_version") != "1.0"
                or record.get("provider") != PROVIDER
                or record.get("issuer_cik") != target
                or not isinstance(record.get("form"), str)
                or record.get("form") != forms[i]
                or record.get("form") not in ALLOWED_FORMS
                or record.get("filed_at") != filed.isoformat()
                or record.get("accepted_at") != accepted_at
                or record.get("collected_at") != observed
                or record.get("source_uri") != _source_uri(target, accession, documents[i])
                or record.get("index_source_uri") != expected_uri
                or record.get("index_raw_sha256") != digest
                or record.get("raw_sha256") is not None
                or record.get("as_of_cutoff") != cutoff.isoformat()
                or record.get("amends_accession") is not None):
            raise ValueError("Indexed filing metadata does not match source row")
        status = ("OFFLINE_SOURCE_UNVERIFIED" if history or provenance == "OFFLINE_UNVERIFIED"
                  else "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED")
        if record.get("evidence_status") != status:
            raise ValueError("Indexed filing evidence status does not match provenance")
        if filed > cutoff or filed > observed_day:
            raise ValueError("Indexed filing is later than the as-of observation")
        if accepted_at is None and filed == observed_day:
            raise ValueError("Same-day filing lacks an offset-aware acceptance time")
        if (accepted_at is not None
                and datetime.fromisoformat(accepted_at).astimezone(timezone.utc) > observed_instant):
            raise ValueError("Indexed filing acceptance follows its observation time")


def save_index(db_path: Path, raw: bytes, indexed: dict, *,
               store_http_validator: bool = False, etag: str | None = None,
               check_provenance: str | None = None) -> dict:
    """Atomic, repeatable ingestion with original response bytes preserved."""
    candidate = Path(db_path).expanduser()
    if candidate.is_symlink():
        raise ValueError("DB path cannot be a symbolic link")
    path = candidate.resolve()
    if path.exists() and not path.is_file():
        raise ValueError("DB path must be a regular file")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_JSON_BYTES:
        raise ValueError("Original SEC JSON bytes required")
    if not isinstance(indexed, dict):
        raise ValueError("Index evidence must be an object")
    source_provenance = indexed.get("provenance")
    checked_as = source_provenance if check_provenance is None else check_provenance
    if type(store_http_validator) is not bool:
        raise ValueError("HTTP validator persistence flag must be boolean")
    if checked_as not in (
            "OFFLINE_UNVERIFIED", "SEC_HTTPS_RESPONSE", "SEC_HTTPS_304_NOT_MODIFIED"):
        raise ValueError("Invalid observation-check provenance")
    if (checked_as == "SEC_HTTPS_304_NOT_MODIFIED"
            and source_provenance != "SEC_HTTPS_RESPONSE"):
        raise ValueError("304 checks require an originally indexed SEC HTTPS response")
    if (checked_as == "SEC_HTTPS_304_NOT_MODIFIED"
            and not store_http_validator):
        raise ValueError("304 checks require conditional validator persistence")
    if store_http_validator and source_provenance != "SEC_HTTPS_RESPONSE":
        raise ValueError("HTTP validators may only be stored for SEC HTTPS responses")
    if store_http_validator and etag is not None and not _valid_etag(etag):
        raise ValueError("Invalid SEC ETag validator")
    _validate_index_for_save(raw, indexed, path)
    history_record_count = None
    if "history_manifest_sha256" in indexed:
        source = _validate_raw(raw)
        ids = source.get("accessionNumber")
        if not isinstance(ids, list):
            raise ValueError("HISTORY_PAGE_RECEIPT_ACCESSIONS_MISSING")
        history_record_count = len(ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    inserted = 0
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        with conn:
            conn.executescript(SCHEMA)
            # Serialize read-check-write across processes so simultaneous
            # replays reuse one observation instead of racing its UNIQUE key.
            conn.execute("BEGIN IMMEDIATE")
            digest = indexed["source_sha256"]
            existing = conn.execute(
                "SELECT id FROM observations WHERE provider=? AND issuer_cik=? AND sha256=?",
                (PROVIDER, indexed["issuer_cik"], digest),
            ).fetchone()
            if existing:
                obs_id = existing[0]
                stored = conn.execute("SELECT response FROM observations WHERE id=?", (obs_id,)).fetchone()
                if stored[0] != raw:
                    raise ValueError("Stored SEC hash collision or corrupt observation")
            else:
                cursor = conn.execute(
                    "INSERT INTO observations(provider,issuer_cik,sha256,response,seen_at,provenance)"
                    " VALUES(?,?,?,?,?,?)",
                    (PROVIDER, indexed["issuer_cik"], digest, raw, indexed["collected_at"],
                     indexed["provenance"]),
                )
                obs_id = cursor.lastrowid
            first_seen = conn.execute(
                "SELECT seen_at FROM observations WHERE id=?", (obs_id,),
            ).fetchone()[0]
            if indexed["collected_at"] < first_seen:
                raise ValueError("OBSERVATION_CHECK_PRECEDES_FIRST_SEEN")
            conn.execute(
                "INSERT OR IGNORE INTO observation_checks(observation_id,checked_at,provenance)"
                " VALUES(?,?,?)", (obs_id, indexed["collected_at"], checked_as),
            )
            if store_http_validator:
                if etag is None:
                    conn.execute(
                        "DELETE FROM http_validators WHERE provider=? AND issuer_cik=? AND source_uri=?",
                        (PROVIDER, indexed["issuer_cik"], indexed["source_uri"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO http_validators"
                        "(provider,issuer_cik,source_uri,etag,response_sha256,updated_at)"
                        " VALUES(?,?,?,?,?,?) ON CONFLICT(provider,issuer_cik,source_uri)"
                        " DO UPDATE SET etag=excluded.etag,response_sha256=excluded.response_sha256,"
                        "updated_at=excluded.updated_at",
                        (PROVIDER, indexed["issuer_cik"], indexed["source_uri"], etag,
                         digest, indexed["collected_at"]),
                    )
            for filing in indexed["filings"]:
                key = (PROVIDER, indexed["issuer_cik"], filing["accession"])
                old = conn.execute(
                    "SELECT filing_json FROM filings WHERE provider=? AND issuer_cik=? AND accession=?",
                    key,
                ).fetchone()
                # Metadata may legitimately refresh for the same accession;
                # preserve the original receipt, and record the later source
                # observation rather than overwrite historical filing evidence.
                if old is None:
                    conn.execute(
                        "INSERT INTO filings(provider,issuer_cik,accession,filing_json,first_observation_id)"
                        " VALUES(?,?,?,?,?)",
                        (*key, _canonical(filing).decode("utf-8"), obs_id),
                    )
                    inserted += 1
                conn.execute(
                    "INSERT OR IGNORE INTO filing_observations(filing_cik,accession,observation_id)"
                    " VALUES(?,?,?)", (indexed["issuer_cik"], filing["accession"], obs_id)
                )
            if "history_manifest_sha256" in indexed:
                page_name = indexed["source_uri"].rsplit("/", 1)[-1]
                receipt_key = (indexed["issuer_cik"], indexed["history_manifest_sha256"],
                               page_name)
                existing_page = conn.execute(
                    "SELECT page_sha256,observation_id,record_count FROM history_page_receipts "
                    "WHERE issuer_cik=? AND manifest_sha256=? AND page_name=?",
                    receipt_key,
                ).fetchone()
                page_receipt = (digest, obs_id, history_record_count)
                if existing_page is None:
                    conn.execute(
                        "INSERT INTO history_page_receipts"
                        "(issuer_cik,manifest_sha256,page_name,page_sha256,observation_id,record_count)"
                        " VALUES(?,?,?,?,?,?)", (*receipt_key, *page_receipt),
                    )
                elif existing_page != page_receipt:
                    version = conn.execute(
                        "SELECT observation_id,record_count FROM history_page_receipt_versions "
                        "WHERE issuer_cik=? AND manifest_sha256=? AND page_name=? AND page_sha256=?",
                        (*receipt_key, digest),
                    ).fetchone()
                    if version is not None and version != (obs_id, history_record_count):
                        raise ValueError("HISTORY_PAGE_RECEIPT_VERSION_CONFLICT")
                    if version is None:
                        conn.execute(
                            "INSERT INTO history_page_receipt_versions"
                            "(issuer_cik,manifest_sha256,page_name,page_sha256,observation_id,record_count)"
                            " VALUES(?,?,?,?,?,?)",
                            (*receipt_key, digest, obs_id, history_record_count),
                        )
            total = conn.execute(
                "SELECT COUNT(*) FROM filings WHERE provider=? AND issuer_cik=?",
                (PROVIDER, indexed["issuer_cik"]),
            ).fetchone()[0]
    return {
        "status": "SAVED" if not existing or inserted else "REUSED",
        "observation_id": obs_id, "new_filings": inserted,
        "total_filings": total, "db_path": str(path),
        "raw_index_sha256": indexed["source_sha256"],
    }


def _prepare_stored_index_source(payload: dict, *, provenance: str,
                                 cik: str, index_source_uri: Any = None) -> dict:
    """Validate and index one preserved source response for its returned rows."""
    if "cik" in payload:
        source_cik = payload.get("cik")
        if (type(source_cik) not in (int, str) or not str(source_cik).isascii()
                or not str(source_cik).isdecimal() or not int(str(source_cik))
                or cik10(str(int(str(source_cik)))) != cik):
            raise ValueError("Stored filing issuer does not match original index")
        filings = payload.get("filings")
        recent = filings.get("recent") if isinstance(filings, dict) else None
        expected_index_uri = f"https://data.sec.gov/submissions/CIK{cik}.json"
        history = False
    else:
        recent = payload
        expected_index_uri = index_source_uri
        if provenance != "OFFLINE_UNVERIFIED":
            raise ValueError("Stored historical index source is invalid")
        history = True
    if not isinstance(recent, dict):
        raise ValueError("Stored index filing arrays are missing")
    accessions = recent.get("accessionNumber")
    if not isinstance(accessions, list) or len(accessions) > (
            MAX_HISTORY_RECORDS if history else MAX_RECORDS):
        raise ValueError("Stored index accession array is invalid")
    if history:
        if (not isinstance(expected_index_uri, str) or re.fullmatch(
                rf"https://data\.sec\.gov/submissions/CIK{cik}-submissions-[0-9]{{3}}\.json",
                expected_index_uri, flags=re.ASCII) is None):
            raise ValueError("Stored historical index source is invalid")
    forms = _column(recent, "form", len(accessions))
    days = _column(recent, "filingDate", len(accessions))
    documents = _column(recent, "primaryDocument", len(accessions))
    accepted = recent.get("acceptanceDateTime")
    if accepted is not None and (not isinstance(accepted, list)
                                 or len(accepted) != len(accessions)):
        raise ValueError("Stored index acceptance timestamps are misaligned")
    positions: dict[str, int] = {}
    duplicates: set[str] = set()
    for i, value in enumerate(accessions):
        if isinstance(value, str):
            if value in positions:
                duplicates.add(value)
            else:
                positions[value] = i
    return {
        "expected_index_uri": expected_index_uri,
        "history": history,
        "positions": positions,
        "duplicates": duplicates,
        "forms": forms,
        "days": days,
        "documents": documents,
        "accepted": accepted,
    }


def _verify_stored_filing(record: dict, *, payload: dict, observation_sha256: str,
                         provenance: str, cik: str,
                         prepared_source: dict | None = None) -> None:
    """Recheck one stored row against its preserved source response."""
    if (not isinstance(record, dict)
            or record.get("index_raw_sha256") != observation_sha256):
        raise ValueError("Stored index response integrity failed")
    accession = record.get("accession")
    if (not isinstance(accession, str) or re.fullmatch(
            r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession, flags=re.ASCII) is None):
        raise ValueError("Stored accession format is invalid")
    source = prepared_source or _prepare_stored_index_source(
        payload, provenance=provenance, cik=cik,
        index_source_uri=record.get("index_source_uri"),
    )
    expected_index_uri = source["expected_index_uri"]
    history = source["history"]
    accession = record["accession"]
    if (accession not in source["positions"]
            or accession in source["duplicates"]):
        raise ValueError("Stored accession is absent or duplicated in original index")
    i = source["positions"][accession]
    forms, days, documents, accepted = (
        source["forms"], source["days"], source["documents"], source["accepted"]
    )
    accepted_at = _accepted(accepted[i]) if accepted is not None else None
    filed = parse_day(days[i])
    cutoff = parse_day(record.get("as_of_cutoff"))
    collected_at = _observation_time(record.get("collected_at"), cutoff=cutoff)
    observed_instant = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    expected_status = (
        "OFFLINE_SOURCE_UNVERIFIED" if history or provenance == "OFFLINE_UNVERIFIED"
        else "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED"
    )
    if (record.get("schema_version") != "1.0"
            or record.get("provider") != PROVIDER
            or record.get("issuer_cik") != cik
            or not isinstance(record.get("form"), str)
            or record.get("form") != forms[i]
            or record.get("form") not in ALLOWED_FORMS
            or record.get("filed_at") != filed.isoformat()
            or record.get("accepted_at") != accepted_at
            or record.get("collected_at") != collected_at
            or record.get("source_uri") != _source_uri(cik, accession, documents[i])
            or record.get("index_source_uri") != expected_index_uri
            or record.get("raw_sha256") is not None
            or record.get("amends_accession") is not None
            or record.get("evidence_status") != expected_status
            or filed > cutoff or filed > observed_instant.date()
            or (accepted_at is None and filed == observed_instant.date())
            or (accepted_at is not None and datetime.fromisoformat(
                accepted_at).astimezone(timezone.utc) > observed_instant)):
        raise ValueError("Stored filing metadata does not match original index response")
    expected_record = {
        "schema_version": "1.0", "provider": PROVIDER,
        "issuer_cik": cik, "accession": accession, "form": forms[i],
        "filed_at": filed.isoformat(), "accepted_at": accepted_at,
        "collected_at": collected_at,
        "source_uri": _source_uri(cik, accession, documents[i]),
        "index_source_uri": expected_index_uri,
        "index_raw_sha256": observation_sha256, "raw_sha256": None,
        "as_of_cutoff": cutoff.isoformat(), "amends_accession": None,
        "evidence_status": expected_status,
    }
    if record != expected_record:
        raise ValueError("Stored filing metadata does not match original index response")


def _last_checked_metadata(conn, *, cik: str, accessions: list[str],
                           as_of: date | None,
                           has_check_table: bool) -> dict[str, tuple[str, list[str]]]:
    """Load per-filing latest observations in bounded batched SQL queries."""
    if not accessions:
        return {}
    placeholders = ",".join("?" for _ in accessions)
    queries = [
        "SELECT fo.accession,o.seen_at,o.provenance FROM filing_observations AS fo "
        "JOIN observations AS o ON o.id=fo.observation_id "
        f"WHERE fo.filing_cik=? AND fo.accession IN ({placeholders})"
    ]
    if has_check_table:
        queries.append(
            "SELECT fo.accession,c.checked_at,c.provenance "
            "FROM filing_observations AS fo "
            "JOIN observation_checks AS c ON c.observation_id=fo.observation_id "
            f"WHERE fo.filing_cik=? AND fo.accession IN ({placeholders})"
        )
    moments: dict[str, list[tuple[datetime, str]]] = {
        accession: [] for accession in accessions
    }
    params = (cik, *accessions)
    for query in queries:
        for accession, timestamp, provenance in conn.execute(query, params):
            try:
                instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("Stored observation check timestamp is invalid") from exc
            if instant.tzinfo is None or instant.utcoffset() is None:
                raise ValueError("Stored observation check timestamp lacks timezone")
            instant = instant.astimezone(timezone.utc)
            if as_of is None or instant.date() <= as_of:
                moments[accession].append((instant, provenance))
    results = {}
    for accession, available in moments.items():
        if not available:
            raise ValueError("Stored filing has no available observation timestamp")
        last = max(moment for moment, _ in available)
        normalized = last.isoformat().replace("+00:00", "Z")
        provenances = sorted({
            provenance for moment, provenance in available if moment == last
        })
        results[accession] = (normalized, provenances)
    return results


def list_filings(
    db_path: Path, *, cik: str, limit: int = 50, as_of: str | None = None,
) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Output limit must be 1..200")
    target = cik10(cik)
    params: tuple[Any, ...]
    if as_of is None:
        query = (
            "SELECT f.filing_json,o.id,o.sha256,o.provenance,o.seen_at FROM filings AS f "
            "JOIN observations AS o ON o.id=f.first_observation_id "
            "WHERE f.provider=? AND f.issuer_cik=? "
            "ORDER BY json_extract(f.filing_json, '$.filed_at') DESC, f.accession DESC LIMIT ?"
        )
        params = (PROVIDER, target, limit)
    else:
        cutoff_day = parse_day(as_of).isoformat()
        query = (
            "SELECT f.filing_json,o.id,o.sha256,o.provenance,o.seen_at FROM filings AS f "
            "JOIN observations AS o ON o.id=f.first_observation_id "
            "WHERE f.provider=? AND f.issuer_cik=? "
            "AND json_extract(f.filing_json, '$.filed_at') <= ? "
            "AND julianday(json_extract(f.filing_json, '$.collected_at')) < julianday(?) + 1 "
            "AND julianday(o.seen_at) < julianday(?) + 1 "
            "ORDER BY json_extract(f.filing_json, '$.filed_at') DESC, f.accession DESC LIMIT ?"
        )
        params = (PROVIDER, target, as_of, cutoff_day, cutoff_day, limit)
    uri = Path(db_path).expanduser().resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rows = [(json.loads(filing_json), observation_id, digest, provenance, first_seen)
                for filing_json, observation_id, digest, provenance, first_seen
                in conn.execute(query, params)]
        groups: dict[int, list[int]] = {}
        for index, (_, observation_id, _, _, _) in enumerate(rows):
            groups.setdefault(observation_id, []).append(index)
        has_check_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='observation_checks'"
        ).fetchone() is not None
        history_receipt_tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('history_page_receipts','history_page_receipt_versions')"
            )
        }
        for observation_id, indices in groups.items():
            source = conn.execute(
                "SELECT sha256,response,provenance FROM observations WHERE id=?",
                (observation_id,),
            ).fetchone()
            if source is None:
                raise ValueError("Stored index observation is missing")
            source_sha256, raw, source_provenance = source
            if (not isinstance(raw, bytes)
                    or hashlib.sha256(raw).hexdigest() != source_sha256):
                raise ValueError("Stored index response integrity failed")
            payload = _validate_raw(raw)
            historical_source = "cik" not in payload
            first_record = rows[indices[0]][0]
            prepared_source = _prepare_stored_index_source(
                payload, provenance=source_provenance, cik=target,
                index_source_uri=first_record.get("index_source_uri"),
            )
            linked_pages = set()
            if historical_source and history_receipt_tables:
                if "history_page_receipts" in history_receipt_tables:
                    linked_pages.update((page_sha, page_name) for page_name, page_sha in conn.execute(
                        "SELECT page_name,page_sha256 FROM history_page_receipts "
                        "WHERE issuer_cik=? AND observation_id=?",
                        (target, observation_id),
                    ))
                if "history_page_receipt_versions" in history_receipt_tables:
                    linked_pages.update((page_sha, page_name) for page_name, page_sha in conn.execute(
                        "SELECT page_name,page_sha256 FROM history_page_receipt_versions "
                        "WHERE issuer_cik=? AND observation_id=?",
                        (target, observation_id),
                    ))
            for index in indices:
                record, _, expected_sha256, provenance, first_seen = rows[index]
                if expected_sha256 != source_sha256 or provenance != source_provenance:
                    raise ValueError("Stored index observation metadata is inconsistent")
                if first_seen != record.get("collected_at"):
                    raise ValueError("Stored first-seen time does not match the indexed receipt")
                if historical_source and linked_pages:
                    expected_name = record.get("index_source_uri", "").rsplit("/", 1)[-1]
                    if (expected_sha256, expected_name) not in linked_pages:
                        raise ValueError("Stored historical page URI does not match its receipt")
                _verify_stored_filing(
                    record, payload=payload, observation_sha256=source_sha256,
                    provenance=provenance, cik=target,
                    prepared_source=prepared_source,
                )
        cutoff = parse_day(as_of) if as_of is not None else None
        latest_checks = _last_checked_metadata(
            conn, cik=target,
            accessions=[record["accession"] for record, *_ in rows],
            as_of=cutoff, has_check_table=has_check_table,
        )
        output = []
        for record, _, _, _, first_seen in rows:
            last_checked, provenances = latest_checks[record["accession"]]
            output.append({**record, "first_seen_at": first_seen,
                           "last_checked_at": last_checked,
                           "last_checked_provenances": provenances})
        return output


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _load_submission_cache(db_path: Path, cik: str) -> dict | None:
    """Read a hash-checked SEC representation and ETag from the local ledger."""
    candidate = Path(db_path).expanduser()
    if candidate.is_symlink():
        raise ValueError("DB path cannot be a symbolic link")
    if not candidate.is_file():
        return None
    target = cik10(cik)
    source_uri = f"https://data.sec.gov/submissions/CIK{target}.json"
    uri = candidate.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='http_validators'"
        ).fetchone()
        if table is None:
            return None
        row = conn.execute(
            "SELECT v.etag,v.response_sha256,o.sha256,o.response "
            "FROM http_validators AS v JOIN observations AS o "
            "ON o.provider=v.provider AND o.issuer_cik=v.issuer_cik "
            "AND o.sha256=v.response_sha256 "
            "WHERE v.provider=? AND v.issuer_cik=? AND v.source_uri=?",
            (PROVIDER, target, source_uri),
        ).fetchone()
    if row is None:
        return None
    etag, digest, stored_digest, raw = row
    if (not _valid_etag(etag) or not isinstance(digest, str)
            or digest != stored_digest or not isinstance(raw, bytes)
            or hashlib.sha256(raw).hexdigest() != digest):
        raise ValueError("Stored SEC conditional cache failed integrity validation")
    payload = _validate_raw(raw)
    observed = payload.get("cik")
    if (type(observed) not in (int, str) or not str(observed).isascii()
            or not str(observed).isdecimal() or not int(str(observed))
            or cik10(str(observed)) != target):
        raise ValueError("Stored SEC conditional cache issuer mismatch")
    return {"raw": raw, "etag": etag, "sha256": digest, "source_uri": source_uri}


def _fetch_submissions_http(cik: str, *, user_agent: str,
                            cached: dict | None = None) -> tuple[bytes, str | None, bool]:
    target = cik10(cik)
    if not _valid_user_agent(user_agent):
        raise ValueError("Real non-placeholder SEC contact-bearing User-Agent required")
    url = f"https://data.sec.gov/submissions/CIK{target}.json"
    headers = {"User-Agent": user_agent, "Accept": "application/json",
               "Accept-Encoding": "identity"}
    if cached is not None:
        raw_cache, etag, cache_sha = (
            cached.get("raw"), cached.get("etag"), cached.get("sha256")
        )
        if (cached.get("source_uri") != url or not isinstance(raw_cache, bytes)
                or not _valid_etag(etag) or not isinstance(cache_sha, str)
                or hashlib.sha256(raw_cache).hexdigest() != cache_sha):
            raise ValueError("SEC conditional cache failed integrity validation")
        cached_payload = _validate_raw(raw_cache)
        cached_cik = cached_payload.get("cik")
        if (type(cached_cik) not in (int, str) or not str(cached_cik).isascii()
                or not str(cached_cik).isdecimal() or not int(str(cached_cik))
                or cik10(str(cached_cik)) != target):
            raise ValueError("SEC conditional cache issuer mismatch")
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect()
    )

    def read_response(resp):
        if resp.status != 200 or resp.geturl() != url:
            raise ValueError("Unexpected SEC HTTP status or redirect")
        if resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("SEC response is not application/json")
        size = resp.headers.get("Content-Length")
        if size is not None and (not size.isdecimal() or int(size) > MAX_JSON_BYTES):
            raise ValueError("SEC response size rejected")
        raw = resp.read(MAX_JSON_BYTES + 1)
        return raw, (resp.headers.get("ETag") if _valid_etag(resp.headers.get("ETag")) else None), False

    def read_not_modified(error):
        if cached is None:
            raise ValueError("SEC returned 304 without a hash-verified cached representation")
        if error.geturl() != url:
            raise ValueError("SEC 304 response URL mismatch")
        response_etag = error.headers.get("ETag")
        etag = response_etag if _valid_etag(response_etag) else (
            cached["etag"] if response_etag is None else None
        )
        return cached["raw"], etag, True

    try:
        raw, etag, not_modified = _bounded_sec_get(
            opener, req, read_response, read_not_modified=read_not_modified,
        )
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        raise ValueError(f"SEC request failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("SEC response exceeded 8MB")
    payload = _validate_raw(raw)
    observed = payload.get("cik")
    if (type(observed) not in (int, str) or not str(observed).isascii()
            or not str(observed).isdecimal() or not int(str(observed))
            or cik10(str(observed)) != target):
        raise ValueError("SEC response issuer CIK differs from requested CIK")
    return raw, etag, not_modified


def fetch_submissions(cik: str, *, user_agent: str,
                      allow_network: bool = False) -> bytes:
    if not allow_network:
        raise ValueError("Network disabled unless --allow-network is provided")
    raw, _, _ = _fetch_submissions_http(cik, user_agent=user_agent)
    return raw


def fetch_submissions_with_cache(db_path: Path, cik: str, *,
                                 user_agent: str) -> tuple[bytes, str | None, bool]:
    """Explicit network path with an optional hash-verified conditional cache."""
    cached = _load_submission_cache(db_path, cik)
    return _fetch_submissions_http(cik, user_agent=user_agent, cached=cached)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DL SEC filing index offline-first MVP")
    parser.add_argument("--cik", required=True, help="SEC CIK; zero-padded internally")
    parser.add_argument("--as-of", required=True, help="Exclude filings after YYYY-MM-DD")
    parser.add_argument("--forms", default="10-K,10-K/A,10-Q,10-Q/A,8-K,8-K/A", help="Allowed SEC forms; includes amendments by default")
    parser.add_argument("--input-json", type=Path, help="Local SEC-style response JSON (offline)")
    parser.add_argument("--allow-network", action="store_true",
                        help="Explicit bounded SEC GET (at most 3 attempts)")
    parser.add_argument("--collected-at", help="Offline record observation time (ISO 8601 with offset). "
                        "Not accepted with live --allow-network. Do not invent historical receipts.")
    parser.add_argument("--db", type=Path, required=True, help="Local SQLite ledger")
    parser.add_argument("--list", action="store_true", help="List stored filings without ingesting")
    args = parser.parse_args(argv)
    try:
        cik = cik10(args.cik)
        if args.list:
            if args.input_json or args.allow_network:
                raise ValueError("--list cannot also import")
            result = {"status": "READ_ONLY", "as_of": args.as_of,
                      "filings": list_filings(args.db, cik=cik, as_of=args.as_of)}
        else:
            if bool(args.input_json) == bool(args.allow_network):
                raise ValueError("Choose exactly one --input-json or --allow-network")
            if args.allow_network and args.collected_at is not None:
                raise ValueError("Live SEC observation time must be measured, not caller supplied")
            forms = parse_forms(args.forms)
            parse_day(args.as_of)
            if args.input_json:
                raw = _read_local_json(args.input_json)
                provenance = "OFFLINE_UNVERIFIED"
                etag = None
                not_modified = False
            else:
                raw, etag, not_modified = fetch_submissions_with_cache(
                    args.db, cik, user_agent=os.environ.get("DL_SEC_USER_AGENT", "")
                )
                provenance = "SEC_HTTPS_RESPONSE"
            indexed = index_submissions(
                raw, cik=cik, as_of=args.as_of, forms=forms, provenance=provenance,
                collected_at=args.collected_at,
            )
            if args.input_json:
                saved = save_index(args.db, raw, indexed)
            else:
                saved = save_index(
                    args.db, raw, indexed, store_http_validator=True, etag=etag,
                    check_provenance=("SEC_HTTPS_304_NOT_MODIFIED" if not_modified else None),
                )
            result = {**saved, "indexed": indexed}
            if not args.input_json:
                result["http_cache"] = {
                    "response_not_modified": not_modified,
                    "etag_stored": etag is not None,
                    "source_authenticity_verified": False,
                }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "DL_FAILED", "reason": str(exc)[:400]}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
