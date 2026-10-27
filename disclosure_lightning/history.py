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
from datetime import date, datetime, timezone
from pathlib import Path

from . import core
from .originals import _read_local

MAX_HISTORY_ROWS = core.MAX_HISTORY_RECORDS
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
        accepted_at = core._accepted(accepted[i]) if accepted is not None else None
        if accepted_at is None and day == observed_instant.date():
            # Date-only same-day history cannot prove prior-to-observation
            # availability. Do not guess an acceptance instant.
            continue
        if (accepted_at is not None
                and datetime.fromisoformat(accepted_at).astimezone(timezone.utc) > observed_instant):
            continue
        uri = core._source_uri(target, accession, documents[i])
        records.append({
            "schema_version": "1.0", "provider": core.PROVIDER,
            "issuer_cik": target, "accession": accession, "form": kind,
            "filed_at": day.isoformat(),
            "accepted_at": accepted_at,
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



def list_manifest_pages(*, db_path: Path, cik: str, manifest_sha256: str,
                        as_of: str) -> list[dict]:
    """List the allowed historical files without requesting or reading them."""
    cutoff = core.parse_day(as_of)
    _, authority = _stored_manifest(db_path, cik, manifest_sha256)
    return [
        {"name": name, "filing_from": spec["first"].isoformat(),
         "filing_to": spec["last"].isoformat(),
         "filing_count": spec["count"],
         "eligible_by_start_date": spec["first"] <= cutoff}
        for name, spec in sorted(authority["pages"].items())
    ]


def import_history_batch(*, pages: dict[str, bytes], db_path: Path,
                         cik: str, manifest_sha256: str, as_of: str,
                         collected_at: str, forms: frozenset[str],
                         max_pages: int = 4) -> dict:
    """Preflight all selected local history pages, then save them one by one.

    No implicit HTTP and no all-or-nothing DB guarantee. A partial write is
    raised with successfully saved page names so an idempotent replay can
    resume without claiming complete processing.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= 8:
        raise ValueError("INVALID_HISTORY_BATCH_PAGE_LIMIT")
    if (not isinstance(pages, dict) or not pages
            or len(pages) > max_pages):
        raise ValueError("INVALID_HISTORY_BATCH_PAGE_COUNT")
    # Validate membership and cutoff before reading a single supplied page.
    manifest = list_manifest_pages(
        db_path=db_path, cik=cik, manifest_sha256=manifest_sha256,
        as_of=as_of,
    )
    allowed = {item["name"]: item for item in manifest}
    if not all(isinstance(name, str) and name in allowed for name in pages):
        raise ValueError("HISTORY_BATCH_CONTAINS_UNLISTED_PAGE")
    if any(not allowed[name]["eligible_by_start_date"] for name in pages):
        raise ValueError("HISTORY_BATCH_PAGE_AFTER_AS_OF")
    total = 0
    for data in pages.values():
        if not isinstance(data, bytes) or not 0 < len(data) <= core.MAX_JSON_BYTES:
            raise ValueError("HISTORY_BATCH_FILE_SIZE_OR_TYPE")
        total += len(data)
    if total > 32_000_000:
        raise ValueError("HISTORY_BATCH_TOTAL_BYTES_EXCEEDED")
    selected = sorted(pages)
    parsed = []
    accessions = set()
    hashes = set()
    for name in selected:
        raw = pages[name]
        # Always parse the whole page, including excluded form types, to
        # catch cross-page collisions before any persistent writes.
        full = core._validate_raw(raw)
        ids = full.get("accessionNumber")
        if not isinstance(ids, list):
            raise ValueError("HISTORY_BATCH_MISSING_ACCESSIONS")
        for accession in ids:
            if not isinstance(accession, str) or accession in accessions:
                raise ValueError("HISTORY_BATCH_DUPLICATE_ACCESSION")
            accessions.add(accession)
        indexed = index_history_page(
            raw, db_path=db_path, cik=cik, manifest_sha256=manifest_sha256,
            name=name, as_of=as_of, collected_at=collected_at, forms=forms,
        )
        if indexed["source_sha256"] in hashes:
            # observations uniqueness is per digest, not per page name.
            raise ValueError("HISTORY_BATCH_IDENTICAL_PAGE_BYTES")
        hashes.add(indexed["source_sha256"])
        parsed.append((name, raw, indexed))
    completed = []
    new_filings = 0
    for name, raw, indexed in parsed:
        try:
            saved = core.save_index(db_path, raw, indexed)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
            done = ",".join(completed)
            raise ValueError(
                f"HISTORY_BATCH_PARTIAL_WRITE:{len(completed)}/{len(parsed)}"
                f":completed={done}:reason={type(exc).__name__}"
            ) from exc
        completed.append(name)
        new_filings += saved["new_filings"]
    return {
        "status": "SAVED_BATCH" if new_filings else "REUSED_BATCH",
        "pages_processed": len(completed),
        "page_names": completed,
        # This describes only selected input vs pinned manifest; not an
        # authenticated or database-wide claim of SEC-history completeness.
        "selected_batch_missing_manifest_pages": sorted(
            item["name"] for item in manifest
            if item["eligible_by_start_date"] and item["name"] not in pages
        ),
        "selected_batch_covers_eligible_manifest": all(
            not item["eligible_by_start_date"] or item["name"] in pages
            for item in manifest
        ),
        "issuer_history_authenticity_verified": False,
        "new_filings": new_filings,
        "history_manifest_sha256": manifest_sha256,
        "total_input_bytes": total,
        "provenance": "OFFLINE_UNVERIFIED",
        "original_filing_authenticated": False,
        "network_requests": 0,
        "note": "Sequential idempotent writes. Not an atomic multi-page transaction.",
    }


def import_history_directory(*, directory: Path, db_path: Path,
                             cik: str, manifest_sha256: str, as_of: str,
                             collected_at: str, forms: frozenset[str],
                             max_pages: int = 4) -> dict:
    """Read only exact manifest-listed basenames from an explicit local folder."""
    base = Path(directory).expanduser()
    if base.is_symlink() or not base.is_dir():
        raise ValueError("HISTORY_BATCH_DIRECTORY_INVALID")
    if type(max_pages) is not int or not 1 <= max_pages <= 8:
        raise ValueError("INVALID_HISTORY_BATCH_PAGE_LIMIT")
    manifest = list_manifest_pages(
        db_path=db_path, cik=cik,
        manifest_sha256=manifest_sha256, as_of=as_of,
    )
    eligible = [item["name"] for item in manifest if item["eligible_by_start_date"]]
    present = []
    for name in eligible:
        item = base / name
        if item.is_symlink():
            raise ValueError("HISTORY_BATCH_SYMLINK_REJECTED")
        if item.exists():
            if not item.is_file() or not 0 < item.stat().st_size <= core.MAX_JSON_BYTES:
                raise ValueError("HISTORY_BATCH_FILE_INVALID")
            present.append(name)
    if not present or len(present) > max_pages:
        raise ValueError("HISTORY_BATCH_NO_FILES_OR_PAGE_LIMIT")
    # Reuse the archive's no-follow, regular-file read rather than reopening
    # a possibly swapped symlink after the preflight stat.
    raw_pages = {name: _read_local(base / name) for name in present}
    return import_history_batch(
        pages=raw_pages, db_path=db_path, cik=cik,
        manifest_sha256=manifest_sha256, as_of=as_of,
        collected_at=collected_at, forms=forms, max_pages=max_pages,
    )


def review_amendment_candidates(*, db_path: Path, cik: str,
                                as_of: str, limit: int = 500) -> dict:
    """Review potential amendment parents; NEVER write an amends_accession.

    A matching form and reportDate are not the SEC's explicit amendment link.
    Require a unique earlier base filing and pinned, byte-verified metadata;
    omit guesses when the required fields are missing or ambiguous.
    """
    target = core.cik10(cik)
    cutoff = core.parse_day(as_of)
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("INVALID_AMENDMENT_REVIEW_LIMIT")
    candidate = Path(db_path).expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("EXISTING_REGULAR_DL_DB_REQUIRED")
    uri = candidate.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT filing_json FROM filings WHERE provider=? AND issuer_cik=?"
            " ORDER BY accession ASC LIMIT ?",
            (core.PROVIDER, target, limit + 1),
        ).fetchall()
        if len(rows) > limit:
            raise ValueError("AMENDMENT_REVIEW_INCOMPLETE_LEDGER_LIMIT")
        source_cache: dict[str, tuple[dict, date]] = {}
        source_bytes_loaded = 0
        receipts = []
        for (encoded,) in rows:
            receipt = json.loads(encoded)
            if (not isinstance(receipt, dict)
                    or receipt.get("provider") != core.PROVIDER
                    or receipt.get("issuer_cik") != target
                    or not isinstance(receipt.get("accession"), str)
                    or not isinstance(receipt.get("form"), str)):
                raise ValueError("AMENDMENT_LEDGER_RECEIPT_INVALID")
            filed = core.parse_day(receipt.get("filed_at"))
            if filed > cutoff:
                continue
            digest = receipt.get("index_raw_sha256")
            if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
                raise ValueError("AMENDMENT_INDEX_DIGEST_MISSING")
            if digest not in source_cache:
                stored = conn.execute(
                    "SELECT response,seen_at FROM observations WHERE "
                    "provider=? AND issuer_cik=? AND sha256=?",
                    (core.PROVIDER, target, digest),
                ).fetchone()
                if stored is None or not isinstance(stored[0], bytes):
                    raise ValueError("AMENDMENT_INDEX_ORIGINAL_NOT_FOUND")
                response, first_seen = stored
                source_bytes_loaded += len(response)
                if len(source_cache) >= 128 or source_bytes_loaded > 128_000_000:
                    raise ValueError("AMENDMENT_REVIEW_SOURCE_BYTE_BUDGET_EXCEEDED")
                if hashlib.sha256(response).hexdigest() != digest:
                    raise ValueError("AMENDMENT_INDEX_ORIGINAL_CORRUPTED")
                moment = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                if moment.tzinfo is None or moment.utcoffset() is None:
                    raise ValueError("AMENDMENT_INDEX_OBSERVATION_UNTRUSTED")
                source_cache[digest] = (
                    core._validate_raw(response),
                    moment.astimezone(timezone.utc).date(),
                )
            original, observed_day = source_cache[digest]
            if observed_day > cutoff:
                # A later observation cannot prove availability at an earlier
                # as-of date, even if the filing itself is years old.
                continue
            nested = original.get("filings")
            entries = nested.get("recent") if isinstance(nested, dict) else original
            if not isinstance(entries, dict):
                raise ValueError("AMENDMENT_INDEX_SOURCE_INVALID")
            ids = entries.get("accessionNumber")
            if not isinstance(ids, list):
                raise ValueError("AMENDMENT_INDEX_MISSING_ACCESSIONS")
            positions = [i for i, entry in enumerate(ids)
                         if entry == receipt["accession"]]
            if len(positions) != 1:
                raise ValueError("AMENDMENT_RECEIPT_SOURCE_NOT_UNIQUE")
            index = positions[0]
            for key, expected in (
                ("form", receipt["form"]), ("filingDate", filed.isoformat())
            ):
                aligned = entries.get(key)
                if (not isinstance(aligned, list) or len(aligned) != len(ids)
                        or aligned[index] != expected):
                    raise ValueError("AMENDMENT_RECEIPT_SOURCE_METADATA_MISMATCH")
            dates = entries.get("reportDate")
            period = None
            if isinstance(dates, list):
                if len(dates) != len(ids):
                    raise ValueError("AMENDMENT_REPORT_DATE_MISALIGNED")
                value = dates[index]
                if value not in ("", None):
                    period = core.parse_day(value)
                    if period > filed:
                        raise ValueError("AMENDMENT_REPORT_DATE_AFTER_FILING")
            receipts.append({
                "accession": receipt["accession"], "form": receipt["form"],
                "filed_at": filed.isoformat(),
                "period_end": period.isoformat() if period else None,
                "index_raw_sha256": digest,
            })
    base = {}
    for row in receipts:
        if row["form"] in ("10-K", "10-Q", "8-K") and row["period_end"]:
            key = (row["form"], row["period_end"])
            base.setdefault(key, []).append(row)
    result = []
    for amend in receipts:
        form = amend["form"]
        if form not in ("10-K/A", "10-Q/A", "8-K/A"):
            continue
        original_form = form[:-2]
        period_end = amend["period_end"]
        earlier = [
            record for record in base.get((original_form, period_end), [])
            if record["filed_at"] < amend["filed_at"]
            and record["accession"] != amend["accession"]
        ] if period_end else []
        status = (
            "REPORT_PERIOD_MISSING_NO_INFERENCE" if period_end is None
            else "NO_UNIQUE_BASE_MATCH" if not earlier
            else "UNVERIFIED_PERIOD_MATCH_CANDIDATE" if len(earlier) == 1
            else "AMBIGUOUS_MULTIPLE_BASE_MATCHES"
        )
        result.append({
            "amendment_accession": amend["accession"],
            "amendment_form": form,
            "filed_at": amend["filed_at"],
            "report_period_end": period_end,
            "status": status,
            "candidate_parent_accession": earlier[0]["accession"]
            if len(earlier) == 1 else None,
            "candidate_count": len(earlier),
            "authoritative_amends_accession": None,
            "authenticated_amendment_relation": False,
            "index_raw_sha256": amend["index_raw_sha256"],
        })
    return {
        "status": "READ_ONLY_UNVERIFIED_AMENDMENT_REVIEW",
        "issuer_cik": target,
        "as_of_cutoff": cutoff.isoformat(),
        "indexed_filings_checked": len(receipts),
        "amendments": result,
        "ledger_mutated": False,
        "source_authenticity_verified": False,
        "note": "Matching form/period is a candidate, not proof of original amendment target.",
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DL offline SEC historical continuation page importer"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--name")
    parser.add_argument("--input-json", type=Path)
    parser.add_argument("--batch-dir", type=Path)
    parser.add_argument("--list-manifest", action="store_true")
    parser.add_argument("--review-amendments", action="store_true")
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--collected-at",
                        help="Honest, timezone-aware local observation time; not SEC attestation")
    parser.add_argument("--forms", default="10-K,10-K/A,10-Q,10-Q/A,8-K,8-K/A")
    args = parser.parse_args(argv)
    try:
        options = [bool(args.input_json), bool(args.batch_dir),
                   args.list_manifest, args.review_amendments]
        if sum(options) != 1:
            raise ValueError("SELECT_ONE_SINGLE_BATCH_MANIFEST_OR_REVIEW_MODE")
        if args.review_amendments:
            if args.name or args.collected_at or args.manifest_sha256:
                raise ValueError("AMENDMENT_REVIEW_IS_READ_ONLY_NO_IMPORT_ARGS")
            result = review_amendment_candidates(
                db_path=args.db, cik=args.cik, as_of=args.as_of)
        elif args.list_manifest:
            if not args.manifest_sha256 or args.name or args.collected_at:
                raise ValueError("MANIFEST_LISTING_REQUIRES_PIN_ONLY")
            result = {"status": "READ_ONLY_UNVERIFIED_MANIFEST", "pages":
                      list_manifest_pages(db_path=args.db, cik=args.cik,
                                          manifest_sha256=args.manifest_sha256,
                                          as_of=args.as_of)}
        else:
            if not args.manifest_sha256 or args.collected_at is None:
                raise ValueError("MANIFEST_PIN_AND_COLLECTION_TIMESTAMP_REQUIRED")
            forms = core.parse_forms(args.forms)
            if args.batch_dir is not None:
                if args.name:
                    raise ValueError("BATCH_CANNOT_SELECT_SINGLE_NAME")
                result = import_history_directory(
                    directory=args.batch_dir, db_path=args.db,
                    cik=args.cik, manifest_sha256=args.manifest_sha256,
                    as_of=args.as_of, collected_at=args.collected_at,
                    forms=forms, max_pages=args.max_pages,
                )
            else:
                if not args.name:
                    raise ValueError("SINGLE_HISTORY_NAME_REQUIRED")
                path = args.input_json.expanduser()
                if (path.is_symlink() or not path.is_file()
                        or not 0 < path.stat().st_size <= core.MAX_JSON_BYTES):
                    raise ValueError("INVALID_BOUNDED_OFFLINE_HISTORY_FILE")
                result = import_history_page(
                    raw=_read_local(path), db_path=args.db, cik=args.cik,
                    manifest_sha256=args.manifest_sha256, name=args.name,
                    as_of=args.as_of, collected_at=args.collected_at,
                    forms=forms,
                )
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "DL_HISTORY_FAILED", "reason": str(exc)[:350]}),
              file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
