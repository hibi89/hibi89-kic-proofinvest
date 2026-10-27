"""Offline SEC Submissions ingestion for Disclosure Lightning's minimum working unit.

This module NEVER performs HTTP. Bytes are caller-supplied, not authenticated
SEC filings. The SHA-256 covers submissions JSON, NOT the underlying filing.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import re
import sqlite3
import stat

MAX_BYTES = 8_000_000
MAX_ROWS = 5_000
FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"})
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
DOCUMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


def _day(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("INVALID_DATE")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("INVALID_DATE") from exc


def _utc_instant(value: Any) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("COLLECTION_TIME_MUST_HAVE_OFFSET")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_COLLECTION_TIME") from exc
    if parsed.tzinfo is None:
        raise ValueError("COLLECTION_TIME_MUST_HAVE_OFFSET")
    return parsed.astimezone(timezone.utc)


def parse_submissions(raw: bytes, *, cik: str, collected_at: str, as_of: str) -> dict[str, Any]:
    """Return strict, source-labelled SEC-shaped filing metadata envelopes."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("INVALID_OR_OVERSIZED_SOURCE_BYTES")
    if not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik) or int(cik) == 0:
        raise ValueError("INVALID_CIK")
    cutoff = _day(as_of)
    collection = _utc_instant(collected_at)
    if collection.date() > cutoff:
        raise ValueError("COLLECTION_AFTER_AS_OF")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("INVALID_SUBMISSIONS_JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("INVALID_SUBMISSIONS_JSON")
    source_cik = payload.get("cik")
    if type(source_cik) not in (str, int) or not str(source_cik).isascii() or not str(source_cik).isdecimal():
        raise ValueError("SOURCE_CIK_MISMATCH")
    if str(int(source_cik)).zfill(10) != cik:
        raise ValueError("SOURCE_CIK_MISMATCH")
    filings = payload.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    if not isinstance(recent, dict):
        raise ValueError("MISSING_RECENT_FILINGS")
    fields = ("accessionNumber", "form", "filingDate", "primaryDocument")
    columns = [recent.get(field) for field in fields]
    if any(not isinstance(col, list) for col in columns):
        raise ValueError("INVALID_RECENT_COLUMNS")
    lengths = {len(col) for col in columns}
    if len(lengths) != 1 or len(columns[0]) > MAX_ROWS:
        raise ValueError("MISMATCHED_OR_OVERSIZED_COLUMNS")
    source_hash = sha256(raw).hexdigest()
    listing_uri = f"https://data.sec.gov/submissions/CIK{cik}.json"
    output: list[dict[str, Any]] = []
    excluded_future = 0
    for accession, form, filed_text, document in zip(*columns):
        if form not in FORMS:
            continue
        if not isinstance(accession, str) or ACCESSION.fullmatch(accession) is None:
            raise ValueError("INVALID_ACCESSION")
        if not isinstance(document, str) or DOCUMENT.fullmatch(document) is None:
            raise ValueError("INVALID_PRIMARY_DOCUMENT")
        filed = _day(filed_text)
        if filed > cutoff or filed > collection.date():
            excluded_future += 1
            continue
        # This is a computed official-domain locator from UNTRUSTED metadata;
        # the filing itself has NOT been downloaded or authenticated.
        source_uri = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{document}"
        )
        output.append({
            "record_type": "RawFilingEnvelopeV1",
            "schema_version": "1.0",
            "provider": "SEC_EDGAR",
            "issuer_cik": cik,
            "accession": accession,
            "form": form,
            "filed_at": filed.isoformat(),
            "collected_at": collection.isoformat().replace("+00:00", "Z"),
            "as_of_cutoff": as_of,
            "source_uri": source_uri,
            "submissions_uri": listing_uri,
            "raw_sha256": source_hash,
            "raw_sha256_scope": "SEC_SUBMISSIONS_JSON_NOT_FILING",
            "filing_content_sha256": None,
            "original_filing_retrieved": False,
            "evidence_status": "METADATA_ONLY_UNVERIFIED",
            "amends_accession": None,
            "amendment_form": form.endswith("/A"),
        })
    # A repeated accession within one input is ambiguous, even if metadata
    # happen to match. Do not quietly select one or rewrite history.
    keys = [(row["issuer_cik"], row["accession"]) for row in output]
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATED_ACCESSION")
    return {
        "schema": "disclosure-lightning.submissions-offline.v1",
        "source_kind": "CALLER_SUPPLIED_SEC_SHAPED_JSON_NOT_AUTHENTICATED",
        "status": "parsed_offline_unverified",
        "source_payload_sha256": source_hash,
        "source_uri": listing_uri,
        "records": output,
        "excluded_future": excluded_future,
        "source_rights_verified": False,
        "live_api_called": False,
        "filing_content_downloaded": False,
    }


def read_json_file(path: Path) -> bytes:
    """Read bounded regular JSON bytes, avoiding symlinks and local pipes."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("SYMLINK_INPUT_FORBIDDEN")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as reader:
        info = os.fstat(reader.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("NONREGULAR_OR_OVERSIZED_INPUT")
        raw = reader.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("SOURCE_SIZE_LIMIT")
    return raw


def persist(db_path: Path, result: dict[str, Any]) -> dict[str, int]:
    """Append immutable filing versions/observations, with idempotent inserts.

    A new source snapshot creates observations but does not duplicate unchanged
    filing metadata versions. No raw filing HTML is downloaded or inferred.
    """
    if result.get("schema") != "disclosure-lightning.submissions-offline.v1":
        raise ValueError("INVALID_INPUT_CONTRACT")
    db_path = Path(db_path)
    if db_path.is_symlink() or not db_path.parent.is_dir():
        raise ValueError("INVALID_DATABASE_PATH")
    versions_added = observations_added = 0
    with sqlite3.connect(db_path) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS filing_versions (
                issuer_cik TEXT NOT NULL, accession TEXT NOT NULL,
                version_hash TEXT NOT NULL, envelope_json TEXT NOT NULL,
                PRIMARY KEY (issuer_cik, accession, version_hash)
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS fetch_observations (
                issuer_cik TEXT NOT NULL, accession TEXT NOT NULL,
                version_hash TEXT NOT NULL, submissions_sha256 TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (issuer_cik, accession, version_hash, submissions_sha256)
            )
        """)
        for row in result["records"]:
            identity = {
                key: row[key] for key in
                ("provider", "issuer_cik", "accession", "form", "filed_at", "source_uri")
            }
            version_hash = sha256(json.dumps(
                identity, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            envelope = json.dumps(row, ensure_ascii=False, sort_keys=True)
            a = db.execute(
                "INSERT OR IGNORE INTO filing_versions VALUES (?, ?, ?, ?)",
                (row["issuer_cik"], row["accession"], version_hash, envelope),
            )
            b = db.execute(
                "INSERT OR IGNORE INTO fetch_observations VALUES (?, ?, ?, ?, ?)",
                (row["issuer_cik"], row["accession"], version_hash,
                 row["raw_sha256"], row["collected_at"]),
            )
            versions_added += a.rowcount
            observations_added += b.rowcount
    return {"versions_added": versions_added, "observations_added": observations_added}


def export_filings(db_path: Path, *, cik: str) -> list[dict[str, Any]]:
    if not isinstance(cik, str) or not re.fullmatch(r"[0-9]{10}", cik):
        raise ValueError("INVALID_CIK")
    if Path(db_path).is_symlink():
        raise ValueError("SYMLINK_DATABASE_FORBIDDEN")
    with sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT envelope_json FROM filing_versions WHERE issuer_cik=? "
            "ORDER BY accession, version_hash", (cik,)
        ).fetchall()
    return [json.loads(item[0]) for item in rows]
