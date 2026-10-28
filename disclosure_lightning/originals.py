"""DL original-filing byte collector: saved SEC index → bounded primary document.

Two strict modes: caller-supplied offline file (UNVERIFIED) or one explicitly
opted-in official SEC archive HTTP GET with genuine contact. Original file bytes
are stored unchanged, by SHA-256, separately from SEC submissions JSON.
No inferred issuer numbers, HTML parsing, historical authentication, or ML.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sqlite3
import stat
import sys
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

from .core import _NoRedirect, _timestamp, _valid_user_agent, cik10, parse_day

MAX_FILING_BYTES = 25_000_000
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z", re.ASCII)
DOCNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z", re.ASCII)
MIME_TYPES = frozenset({
    "text/html", "text/plain", "text/xml", "application/xml",
    "application/xhtml+xml",
})


def _accession(value: str) -> str:
    if not isinstance(value, str) or ACCESSION.fullmatch(value) is None:
        raise ValueError("SEC accession must match NNNNNNNNNN-YY-NNNNNN")
    return value


def _db_path(db_path: Path) -> Path:
    supplied = Path(db_path).expanduser()
    if supplied.is_symlink() or not supplied.is_file():
        raise ValueError("A real previously indexed SQLite DB is required")
    return supplied.resolve()


def _read_conn(db_path: Path):
    uri = _db_path(db_path).as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def locate_original(db_path: Path, *, cik: str, accession: str,
                    as_of: str | None = None) -> dict:
    """Allow only primary SEC filing URL already anchored in saved metadata."""
    cik, accession = cik10(cik), _accession(accession)
    with closing(_read_conn(db_path)) as conn:
        if as_of is None:
            row = conn.execute(
                "SELECT filing_json FROM filings WHERE provider='SEC_EDGAR'"
                " AND issuer_cik=? AND accession=?", (cik, accession)
            ).fetchone()
        else:
            cutoff_day = parse_day(as_of).isoformat()
            row = conn.execute(
                "SELECT f.filing_json FROM filings AS f "
                "JOIN observations AS o ON o.id=f.first_observation_id "
                "WHERE f.provider='SEC_EDGAR' AND f.issuer_cik=? AND f.accession=? "
                "AND json_extract(f.filing_json,'$.filed_at')<=? "
                "AND julianday(json_extract(f.filing_json,'$.collected_at'))<julianday(?) + 1 "
                "AND julianday(o.seen_at)<julianday(?) + 1",
                (cik, accession, cutoff_day, cutoff_day, cutoff_day),
            ).fetchone()
    if row is None:
        if as_of is not None:
            raise ValueError("SEC filing was not available by as-of date")
        raise ValueError("SEC filing ID not found in the indexed SQLite evidence")
    receipt = json.loads(row[0])
    prefix = ("https://www.sec.gov/Archives/edgar/data/"
              f"{int(cik)}/{accession.replace('-', '')}/")
    url = receipt.get("source_uri")
    if (not isinstance(url, str) or not url.startswith(prefix)
            or len(url) > len(prefix) + 200):
        raise ValueError("Primary document URL not established by metadata")
    name = url[len(prefix):]
    if DOCNAME.fullmatch(name) is None or name.startswith(".") or ".." in name:
        raise ValueError("Unsafe SEC primary document path")
    if (receipt.get("issuer_cik") != cik or receipt.get("accession") != accession
            or receipt.get("provider") != "SEC_EDGAR"
            or receipt.get("raw_sha256") is not None
            or receipt.get("evidence_status") not in (
                "OFFLINE_SOURCE_UNVERIFIED",
                "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED",
            )):
        raise ValueError("Unexpected SEC metadata contract")
    return receipt


def _read_local(path: Path) -> bytes:
    source = Path(path).expanduser()
    if source.is_symlink():
        raise ValueError("Symlink original input forbidden")
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_FILING_BYTES:
            raise ValueError("Original file must be a bounded regular file")
        data = handle.read(MAX_FILING_BYTES + 1)
    if not 0 < len(data) <= MAX_FILING_BYTES:
        raise ValueError("Original file must contain 1..25MB")
    return data


def fetch_original(*, receipt: dict, user_agent: str,
                   allow_network: bool = False) -> tuple[bytes, str]:
    """Exactly one official GET, no redirect, proxy, retries or pagination."""
    if not allow_network:
        raise ValueError("Explicit --allow-network is required")
    if not _valid_user_agent(user_agent):
        raise ValueError("Actual non-placeholder contact-bearing SEC User-Agent required")
    if receipt.get("evidence_status") != "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED":
        raise ValueError("Live original fetch requires previously indexed SEC HTTPS metadata")
    cik, accession = cik10(receipt.get("issuer_cik")), _accession(receipt.get("accession"))
    prefix = ("https://www.sec.gov/Archives/edgar/data/"
              f"{int(cik)}/{accession.replace('-', '')}/")
    url = receipt.get("source_uri")
    name = url[len(prefix):] if isinstance(url, str) and url.startswith(prefix) else ""
    if (not name or DOCNAME.fullmatch(name) is None
            or name.startswith(".") or ".." in name):
        raise ValueError("SEC original URL must match its CIK/accession and primary filename")
    req = urllib.request.Request(
        url, headers={
            "User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,text/plain,application/xml,text/xml",
            "Accept-Encoding": "identity",
        }, method="GET",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect(),
    )
    try:
        with opener.open(req, timeout=15) as response:
            if response.geturl() != url or response.status != 200:
                raise ValueError("SEC archive returned redirect or non-200 response")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind not in MIME_TYPES:
                raise ValueError("SEC primary file has unsupported content-type")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal()
                                       or not 0 < int(length) <= MAX_FILING_BYTES):
                raise ValueError("SEC primary file advertised invalid size")
            content = response.read(MAX_FILING_BYTES + 1)
    except (urllib.error.URLError, http.client.HTTPException, OSError,
            TimeoutError) as exc:
        raise ValueError(f"SEC archive request failed: {type(exc).__name__}") from exc
    if not 0 < len(content) <= MAX_FILING_BYTES:
        raise ValueError("SEC original response was empty or oversized")
    return content, kind


def persist_original(*, db_path: Path, receipt: dict, raw: bytes,
                     kind: str, origin: str) -> dict:
    if origin not in ("OFFLINE_FILE_UNVERIFIED", "SEC_HTTPS_RESPONSE_UNVERIFIED"):
        raise ValueError("Invalid original file provenance")
    if kind not in MIME_TYPES and kind != "application/octet-stream":
        raise ValueError("Unsupported original file content type")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_FILING_BYTES:
        raise ValueError("Original SEC bytes missing or excessive")
    location = locate_original(
        db_path, cik=receipt["issuer_cik"], accession=receipt["accession"]
    )
    if location != receipt:
        raise ValueError("Original filing locator changed since preflight")
    if origin == "SEC_HTTPS_RESPONSE_UNVERIFIED" and location["evidence_status"] != (
            "INDEXED_OFFICIAL_HTTP_NOT_FULL_FILING_VERIFIED"):
        raise ValueError("SEC transport receipt requires original official metadata")
    digest = hashlib.sha256(raw).hexdigest()
    db_path = _db_path(db_path)
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("PRAGMA busy_timeout=5000")
        with db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS original_filing_receipts (
                    issuer_cik TEXT NOT NULL,
                    accession TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    input_origin TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_bytes BLOB NOT NULL,
                    PRIMARY KEY (issuer_cik, accession, sha256)
                )
            """)
            existing = db.execute(
                "SELECT file_bytes FROM original_filing_receipts "
                "WHERE issuer_cik=? AND accession=? AND sha256=?",
                (location["issuer_cik"], location["accession"], digest),
            ).fetchone()
            if existing is not None:
                if existing[0] != raw:
                    raise ValueError("Original SHA-256 digest collision or corrupt evidence")
                state = "REUSED"
            else:
                db.execute(
                    "INSERT INTO original_filing_receipts VALUES(?,?,?,?,?,?,?,?)",
                    (location["issuer_cik"], location["accession"], digest,
                     location["source_uri"], _timestamp(), origin, kind, raw),
                )
                state = "SAVED"
    return {
        "status": state, "issuer_cik": location["issuer_cik"],
        "accession": location["accession"], "source_uri": location["source_uri"],
        "filing_sha256": digest, "filing_bytes": len(raw),
        "input_origin": origin,
        "content_type": kind,
        "original_filing_retrieved": origin == "SEC_HTTPS_RESPONSE_UNVERIFIED",
        "authenticated_external_source": False,
        "note": "SHA-256 of saved original bytes, not a certification of filing authenticity.",
    }


def list_originals(*, db_path: Path, cik: str, accession: str,
                   as_of: str | None = None) -> list[dict]:
    c, a = cik10(cik), _accession(accession)
    with closing(_read_conn(db_path)) as db:
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='original_filing_receipts'"
        ).fetchone()
        if not exists:
            return []
        if as_of is None:
            rows = db.execute(
                "SELECT r.sha256,r.source_uri,r.retrieved_at,r.input_origin,r.content_type,length(r.file_bytes)"
                " FROM original_filing_receipts AS r JOIN filings AS f"
                " ON f.provider='SEC_EDGAR' AND f.issuer_cik=r.issuer_cik AND f.accession=r.accession"
                " WHERE r.issuer_cik=? AND r.accession=?"
                " AND r.source_uri=json_extract(f.filing_json,'$.source_uri')"
                " ORDER BY r.retrieved_at, r.sha256", (c, a),
            ).fetchall()
        else:
            cutoff_day = parse_day(as_of).isoformat()
            rows = db.execute(
                "SELECT r.sha256,r.source_uri,r.retrieved_at,r.input_origin,r.content_type,length(r.file_bytes)"
                " FROM original_filing_receipts AS r JOIN filings AS f"
                " ON f.provider='SEC_EDGAR' AND f.issuer_cik=r.issuer_cik AND f.accession=r.accession"
                " WHERE r.issuer_cik=? AND r.accession=?"
                " AND julianday(r.retrieved_at)<julianday(?) + 1"
                " AND r.source_uri=json_extract(f.filing_json,'$.source_uri')"
                " AND json_extract(f.filing_json,'$.filed_at')<=?"
                " AND julianday(json_extract(f.filing_json,'$.collected_at'))<julianday(?) + 1"
                " ORDER BY r.retrieved_at, r.sha256",
                (c, a, cutoff_day, cutoff_day, cutoff_day),
            ).fetchall()
    return [
        {"filing_sha256": sha, "source_uri": uri, "retrieved_at": when,
         "input_origin": origin, "content_type": kind, "filing_bytes": length}
        for sha, uri, when, origin, kind, length in rows
    ]



def read_original_bytes(*, db_path: Path, cik: str, accession: str,
                        sha256: str, as_of: str | None = None) -> bytes:
    """Read exactly one persisted raw primary document; verify digest on read.

    This returns untrusted original bytes, NOT normalized finance claims.
    Never render them as trusted HTML without separate sanitization.
    """
    c, a = cik10(cik), _accession(accession)
    if not isinstance(sha256, str) or re.fullmatch(
            r"[0-9a-f]{64}", sha256, re.ASCII) is None:
        raise ValueError("Invalid original filing SHA-256")
    location = locate_original(db_path, cik=c, accession=a, as_of=as_of)
    if as_of is not None:
        eligible = list_originals(
            db_path=db_path, cik=c, accession=a, as_of=as_of
        )
        if not any(item["filing_sha256"] == sha256 for item in eligible):
            raise ValueError("Original filing bytes were not available by as-of date")
    with closing(_read_conn(db_path)) as db:
        row = db.execute(
            "SELECT file_bytes,source_uri FROM original_filing_receipts "
            "WHERE issuer_cik=? AND accession=? AND sha256=?",
            (c, a, sha256),
        ).fetchone()
    if row is None:
        raise KeyError("Original filing receipt not found")
    raw, source_uri = row
    if source_uri != location["source_uri"]:
        raise ValueError("Saved original source URI no longer matches indexed locator")
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_FILING_BYTES
            or hashlib.sha256(raw).hexdigest() != sha256):
        raise ValueError("Saved original filing content integrity failed")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DL original SEC primary document archive (no unverified promotion)"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", required=True)
    parser.add_argument("--as-of", help="Filter read-only receipts by the UTC end of this date")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input-file", type=Path, help="Offline file input (not SEC-authenticated)")
    group.add_argument("--allow-network", action="store_true", help="One SEC archive HTTPS GET")
    parser.add_argument("--content-type", choices=tuple(sorted(MIME_TYPES | {"application/octet-stream"})),
                        default="application/octet-stream",
                        help="Explicit local file MIME claim (unverified); live MIME is response-derived")
    parser.add_argument("--list", action="store_true", help="Read-only receipt list")
    args = parser.parse_args(argv)
    try:
        if args.list:
            if args.input_file or args.allow_network or args.content_type != "application/octet-stream":
                raise ValueError("Read-only listing cannot import")
            result = {"status": "READ_ONLY", "receipts": list_originals(
                db_path=args.db, cik=args.cik, accession=args.accession,
                as_of=args.as_of,
            )}
            if args.as_of is not None:
                result["as_of"] = parse_day(args.as_of).isoformat()
        else:
            if args.as_of is not None:
                raise ValueError("--as-of is only supported with --list")
            if not (args.input_file or args.allow_network):
                raise ValueError("Provide --input-file or --allow-network explicitly")
            if args.allow_network and args.content_type != "application/octet-stream":
                raise ValueError("Live content-type comes from HTTP response only")
            receipt = locate_original(args.db, cik=args.cik, accession=args.accession)
            if args.input_file:
                raw = _read_local(args.input_file)
                kind, origin = args.content_type, "OFFLINE_FILE_UNVERIFIED"
            else:
                raw, kind = fetch_original(
                    receipt=receipt, allow_network=True,
                    user_agent=os.environ.get("DL_SEC_USER_AGENT", ""),
                )
                origin = "SEC_HTTPS_RESPONSE_UNVERIFIED"
            result = persist_original(
                db_path=args.db, receipt=receipt, raw=raw, kind=kind, origin=origin
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({
            "status": "DL_ORIGINAL_FAILED", "reason": str(exc)[:400],
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
