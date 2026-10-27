"""Bounded, offline-only SEC filings.files continuation importer.

A pinned and locally stored submissions snapshot is the sole authority for the
continuation filename and advertised bounds. The continuation itself is always
UNVERIFIED offline input; HTTPS, authenticity and source rights are NOT proved.
Existing DL SQLite observations and filing rows are reused, not migrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import core

MAX_HISTORY_ROWS = 10_000
MAX_MANIFEST_PAGES = 256
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _stored_manifest(db_path: Path, cik: str, manifest_sha256: str) -> tuple[dict, dict]:
    """Locate ONE pinned base submissions observation, with no DB writes."""
    target = core.cik10(cik)
    if not isinstance(manifest_sha256, str) or not DIGEST_RE.fullmatch(manifest_sha256):
        raise ValueError("INVALID_PINNED_MANIFEST_SHA256")
    path = Path(db_path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("EXISTING_REGULAR_DL_DB_REQUIRED")
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        found = conn.execute(
            "SELECT response,seen_at,provenance FROM observations "
            "WHERE provider=? AND issuer_cik=? AND sha256=?",
            (core.PROVIDER, target, manifest_sha256),
        ).fetchone()
    if found is None:
        raise ValueError("MANIFEST_NOT_IN_PINNED_LOCAL_LEDGER")
    response, seen_at, provenance = found
    if not isinstance(response, bytes) or hashlib.sha256(response).hexdigest() != manifest_sha256:
        raise ValueError("MANIFEST_RAW_DIGEST_MISMATCH")
    payload = core._validate_raw(response)
    observed_cik = payload.get("cik")
    if (type(observed_cik) not in (int, str) or not str(observed_cik).isascii()
            or not str(observed_cik).isdecimal()
            or core.cik10(str(observed_cik)) != target):
        raise ValueError("MANIFEST_CIK_MISMATCH")
    filings = payload.get("filings")
    if not isinstance(filings, dict) or not isinstance(filings.get("recent"), dict):
        raise ValueError("MANIFEST_NOT_BASE_SUBMISSIONS_JSON")
    files = filings.get("files")
    if not isinstance(files, list) or len(files) > MAX_MANIFEST_PAGES:
        raise ValueError("INVALID_HISTORY_MANIFEST_FILES")
    pages: dict[str, dict] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("INVALID_HISTORY_PAGE_RECORD")
        name = entry.get("name")
        if (not isinstance(name, str) or not re.fullmatch(
                rf"CIK{target}-submissions-[0-9]{{3}}\.json", name, re.ASCII)
                or name in pages):
            raise ValueError("UNSAFE_OR_DUPLICATE_HISTORY_PAGE_NAME")
        first, last = core.parse_day(entry.get("filingFrom")), core.parse_day(entry.get("filingTo"))
        count = entry.get("filingCount")
        if first > last or type(count) is not int or not 1 <= count <= MAX_HISTORY_ROWS:
            raise ValueError("INVALID_HISTORY_PAGE_RANGE_OR_COUNT")
        pages[name] = {"first": first, "last": last, "count": count}
    if provenance not in ("OFFLINE_UNVERIFIED", "SEC_HTTPS_RESPONSE"):
        raise ValueError("INVALID_MANIFEST_PROVENANCE")
    # An offline caller may have supplied this first observation timestamp.
    # It is a chronology constraint, not independent SEC authentication.
    first_seen = datetime.fromisoformat(seen_at.replace("Z", "+00:00"))
    if first_seen.tzinfo is None or first_seen.utcoffset() is None:
        raise ValueError("MANIFEST_OBSERVATION_TIME_UNTRUSTED")
    return payload, {"pages": pages, "first_seen": first_seen.astimezone(timezone.utc)}


def index_history_page(raw: bytes, *, db_path: Path, cik: str,
                       manifest_sha256: str, name: str, as_of: str,
                       collected_at: str, forms: frozenset[str]) -> dict:
    """Parse a saved continuation without network; retain source-byte digest."""
    target = core.cik10(cik)
    cutoff = core.parse_day(as_of)
    if not isinstance(forms, frozenset) or not forms or not forms.issubset(core.ALLOWED_FORMS):
        raise ValueError("UNSUPPORTED_HISTORY_FORMS")
    manifest, authority = _stored_manifest(db_path, target, manifest_sha256)
    if not isinstance(name, str) or name not in authority["pages"]:
        raise ValueError("HISTORY_PAGE_NOT_LISTED_IN_PINNED_MANIFEST")
    spec = authority["pages"][name]
    observed = core._observation_time(collected_at, cutoff=cutoff)
    observed_instant = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    if observed_instant < authority["first_seen"]:
        raise ValueError("HISTORY_COLLECTED_BEFORE_MANIFEST_OBSERVED")
    body = core._validate_raw(raw)
    if any(k in body for k in ("filings", "cik")):
        raise ValueError("EXPECTED_UNWRAPPED_HISTORY_COLUMN_ARRAYS")
    accessions = body.get("accessionNumber")
    if not isinstance(accessions, list) or len(accessions) != spec["count"]:
        raise ValueError("HISTORY_RECORD_COUNT_MISMATCH")
    n = len(accessions)
    for key, value in body.items():
        if not isinstance(value, list) or len(value) != n:
            raise ValueError(f"HISTORY_COLUMN_MISALIGNED:{key}")
    kinds = core._column(body, "form", n)
    dates = core._column(body, "filingDate", n)
    documents = core._column(body, "primaryDocument", n)
    accepted = body.get("acceptanceDateTime")
    digest = hashlib.sha256(raw).hexdigest()
    source_uri = f"https://data.sec.gov/submissions/{name}"
    seen = set()
    records = []
    for i, accession in enumerate(accessions):
        if (not isinstance(accession, str) or not re.fullmatch(
                r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession, re.ASCII)
                or accession in seen):
            raise ValueError("HISTORY_DUPLICATE_OR_INVALID_ACCESSION")
        seen.add(accession)
        day = core.parse_day(dates[i])
        if day < spec["first"] or day > spec["last"]:
            raise ValueError("HISTORY_ROW_OUTSIDE_MANIFEST_DATE_RANGE")
        kind = kinds[i]
        if not isinstance(kind, str):
            raise ValueError("INVALID_HISTORY_FORM_TYPE")
        if kind not in forms or day > cutoff or day > observed_instant.date():
            continue
        uri = core._source_uri(target, accession, documents[i])
        records.append({
            "schema_version": "1.0", "provider": core.PROVIDER,
            "issuer_cik": target, "accession": accession, "form": kind,
            "filed_at": day.isoformat(),
            "accepted_at": core._accepted(accepted[i]) if accepted is not None else None,
            "collected_at": observed, "source_uri": uri,
            "index_source_uri": source_uri, "index_raw_sha256": digest,
            "raw_sha256": None, "as_of_cutoff": cutoff.isoformat(),
            "amends_accession": None,
            "evidence_status": "OFFLINE_SOURCE_UNVERIFIED",
        })
    return {
        "schema_version": "1.0", "provider": core.PROVIDER,
        "issuer_cik": target, "issuer_name": str(manifest.get("name", ""))[:300],
        "source_sha256": digest, "source_bytes": len(raw),
        "source_uri": source_uri, "provenance": "OFFLINE_UNVERIFIED",
        "collected_at": observed, "as_of_cutoff": cutoff.isoformat(),
        "history_manifest_sha256": manifest_sha256,
        "filings": records, "indexed_count": len(records),
        "note": "PINNED_MANIFEST_OFFLINE_HISTORY; not live SEC authenticated or original filing content.",
    }


def import_history_page(*, raw: bytes, db_path: Path, cik: str,
                        manifest_sha256: str, name: str, as_of: str,
                        collected_at: str, forms: frozenset[str]) -> dict:
    indexed = index_history_page(
        raw, db_path=db_path, cik=cik, manifest_sha256=manifest_sha256,
        name=name, as_of=as_of, collected_at=collected_at, forms=forms,
    )
    persisted = core.save_index(db_path, raw, indexed)
    return {**persisted, "history_source_uri": indexed["source_uri"],
            "history_manifest_sha256": manifest_sha256,
            "indexed_count": indexed["indexed_count"],
            "evidence_status": "OFFLINE_SOURCE_UNVERIFIED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DL offline SEC historical continuation page importer")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--collected-at", required=True,
                        help="Honest, timezone-aware local observation time; not SEC attestation")
    parser.add_argument("--forms", default="10-K,10-K/A,10-Q,10-Q/A,8-K,8-K/A")
    args = parser.parse_args(argv)
    try:
        path = args.input_json.expanduser()
        if (path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= core.MAX_JSON_BYTES):
            raise ValueError("INVALID_BOUNDED_OFFLINE_HISTORY_FILE")
        raw = path.read_bytes()
        result = import_history_page(
            raw=raw, db_path=args.db, cik=args.cik,
            manifest_sha256=args.manifest_sha256, name=args.name,
            as_of=args.as_of, collected_at=args.collected_at,
            forms=core.parse_forms(args.forms),
        )
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "DL_HISTORY_FAILED", "reason": str(exc)[:350]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
