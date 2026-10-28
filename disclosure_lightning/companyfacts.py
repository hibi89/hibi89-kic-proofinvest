"""Append-only SEC CompanyFacts response storage; no financial normalization."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Any

from . import core
from .core import (
    _NoRedirect, _bounded_sec_get, _timestamp, _valid_etag, _valid_user_agent,
    cik10, parse_day,
)

MAX_CONCEPTS = 50_000
MAX_FACT_ROWS = 200_000
MAX_COMPANYFACTS_BYTES = 50_000_000
PROVENANCES = frozenset({"OFFLINE_UNVERIFIED", "SEC_HTTPS_RESPONSE"})

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS companyfacts_observations(
    issuer_cik TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    response BLOB NOT NULL,
    entity_name TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    as_of_cutoff TEXT NOT NULL,
    provenance TEXT NOT NULL,
    PRIMARY KEY(issuer_cik,sha256)
);
CREATE TABLE IF NOT EXISTS companyfacts_checks(
    issuer_cik TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    provenance TEXT NOT NULL,
    PRIMARY KEY(issuer_cik,sha256,checked_at,provenance),
    FOREIGN KEY(issuer_cik,sha256)
      REFERENCES companyfacts_observations(issuer_cik,sha256)
);
CREATE TABLE IF NOT EXISTS companyfacts_validators(
    issuer_cik TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    etag TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(issuer_cik,source_uri),
    FOREIGN KEY(issuer_cik,sha256)
      REFERENCES companyfacts_observations(issuer_cik,sha256)
);
"""


def source_uri(cik: str) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10(cik)}.json"


def _validate_payload(raw: bytes, cik: str) -> tuple[dict, int, int]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_COMPANYFACTS_BYTES:
        raise ValueError("CompanyFacts JSON must be 1..50MB")
    try:
        payload = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=core._unique_json_object,
            parse_constant=core._reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 CompanyFacts JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("CompanyFacts root must be a JSON object")
    target = cik10(cik)
    observed = payload.get("cik")
    if (type(observed) not in (int, str) or not str(observed).isascii()
            or not str(observed).isdecimal() or len(str(observed)) > 10
            or cik10(str(observed)) != target):
        raise ValueError("CompanyFacts issuer CIK differs from requested CIK")
    entity = payload.get("entityName")
    facts = payload.get("facts")
    if not isinstance(entity, str) or not entity.strip() or len(entity) > 500:
        raise ValueError("CompanyFacts entityName is missing or invalid")
    if not isinstance(facts, dict) or not facts or len(facts) > 100:
        raise ValueError("CompanyFacts facts object is missing or excessive")
    concept_count = 0
    row_count = 0
    for taxonomy, concepts in facts.items():
        if (not isinstance(taxonomy, str)
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", taxonomy,
                                re.ASCII) is None
                or not isinstance(concepts, dict)):
            raise ValueError("CompanyFacts taxonomy namespace is invalid")
        concept_count += len(concepts)
        for name, concept in concepts.items():
            if (not isinstance(name, str)
                    or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,199}", name,
                                    re.ASCII) is None
                    or not isinstance(concept, dict)):
                raise ValueError("CompanyFacts concept record is invalid")
            units = concept.get("units")
            if not isinstance(units, dict):
                raise ValueError("CompanyFacts concept units are invalid")
            for unit, rows in units.items():
                if (not isinstance(unit, str) or not unit or len(unit) > 64
                        or not isinstance(rows, list)):
                    raise ValueError("CompanyFacts unit record is invalid")
                row_count += len(rows)
                if row_count > MAX_FACT_ROWS:
                    raise ValueError("CompanyFacts record count exceeds safety bound")
                if any(not isinstance(row, dict) for row in rows):
                    raise ValueError("CompanyFacts fact row is invalid")
    if concept_count > MAX_CONCEPTS:
        raise ValueError("CompanyFacts concept count exceeds safety bound")
    return payload, concept_count, row_count


def index_companyfacts(raw: bytes, *, cik: str, as_of: str,
                       collected_at: str | None = None,
                       provenance: str = "OFFLINE_UNVERIFIED") -> dict[str, Any]:
    if provenance not in PROVENANCES:
        raise ValueError("Invalid CompanyFacts provenance")
    target = cik10(cik)
    cutoff = parse_day(as_of)
    observed_at = core._observation_time(
        _timestamp() if collected_at is None else collected_at, cutoff=cutoff,
    )
    payload, concept_count, row_count = _validate_payload(raw, target)
    digest = hashlib.sha256(raw).hexdigest()
    uri = source_uri(target)
    return {
        "schema_version": "1.0", "provider": "SEC_EDGAR",
        "dataset": "COMPANYFACTS", "issuer_cik": target,
        "entity_name": payload["entityName"], "source_uri": uri,
        "source_sha256": digest, "source_bytes": len(raw),
        "collected_at": observed_at, "as_of_cutoff": cutoff.isoformat(),
        "provenance": provenance, "concept_count": concept_count,
        "fact_row_count": row_count,
        "evidence_status": ("OFFLINE_SOURCE_UNVERIFIED" if provenance == "OFFLINE_UNVERIFIED"
                            else "INDEXED_OFFICIAL_HTTP_NOT_FULL_COMPANYFACTS_VERIFIED"),
        "financial_claim_verified": False,
        "source_authenticity_verified": False,
    }


def save_companyfacts(db_path: Path, raw: bytes, indexed: dict, *,
                      etag: str | None = None,
                      check_provenance: str | None = None) -> dict[str, Any]:
    if not isinstance(indexed, dict) or indexed.get("dataset") != "COMPANYFACTS":
        raise ValueError("CompanyFacts metadata required")
    reindexed = index_companyfacts(
        raw, cik=indexed.get("issuer_cik"), as_of=indexed.get("as_of_cutoff"),
        collected_at=indexed.get("collected_at"), provenance=indexed.get("provenance"),
    )
    if reindexed != indexed:
        raise ValueError("CompanyFacts metadata mismatch")
    uri = indexed["source_uri"]
    if etag is not None and (indexed["provenance"] != "SEC_HTTPS_RESPONSE"
                             or not _valid_etag(etag)):
        raise ValueError("Invalid CompanyFacts ETag")
    checked_as = indexed["provenance"] if check_provenance is None else check_provenance
    if checked_as not in (*PROVENANCES, "SEC_HTTPS_304_NOT_MODIFIED"):
        raise ValueError("Invalid CompanyFacts check provenance")
    if (checked_as == "SEC_HTTPS_304_NOT_MODIFIED"
            and (indexed["provenance"] != "SEC_HTTPS_RESPONSE" or etag is None)):
        raise ValueError("CompanyFacts 304 requires a live response and validator")

    path = Path(db_path).expanduser()
    if path.is_symlink():
        raise ValueError("DB path cannot be a symbolic link")
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = indexed["source_sha256"]
    checked_at = indexed["collected_at"]
    state = "REUSED"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        # executescript() commits any pending transaction before running. Keep
        # schema creation outside the evidence transaction, then explicitly
        # begin the all-or-nothing observation/check/validator write.
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        try:
            old = db.execute(
                "SELECT response,source_uri FROM companyfacts_observations "
                "WHERE issuer_cik=? AND sha256=?",
                (indexed["issuer_cik"], digest),
            ).fetchone()
            if old is None:
                db.execute(
                    "INSERT INTO companyfacts_observations VALUES(?,?,?,?,?,?,?,?)",
                    (indexed["issuer_cik"], digest, uri, raw, indexed["entity_name"],
                     checked_at, indexed["as_of_cutoff"], indexed["provenance"]),
                )
                state = "SAVED"
            elif old != (raw, uri):
                raise ValueError("CompanyFacts digest collision or source conflict")
            db.execute(
                "INSERT OR IGNORE INTO companyfacts_checks VALUES(?,?,?,?)",
                (indexed["issuer_cik"], digest, checked_at, checked_as),
            )
            if indexed["provenance"] == "SEC_HTTPS_RESPONSE":
                if etag is None:
                    db.execute(
                        "DELETE FROM companyfacts_validators WHERE issuer_cik=? AND source_uri=?",
                        (indexed["issuer_cik"], uri),
                    )
                else:
                    db.execute(
                        "INSERT INTO companyfacts_validators VALUES(?,?,?,?,?) "
                        "ON CONFLICT(issuer_cik,source_uri) DO UPDATE SET "
                        "etag=excluded.etag,sha256=excluded.sha256,updated_at=excluded.updated_at",
                        (indexed["issuer_cik"], uri, etag, digest, checked_at),
                    )
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return {"status": state, "observation_id": digest, "db_path": str(path.resolve()),
            "source_uri": uri, "source_sha256": digest,
            "financial_claim_verified": False, "source_authenticity_verified": False}


def _load_cache(db_path: Path, cik: str) -> dict | None:
    path = Path(db_path).expanduser()
    if path.is_symlink() or not path.is_file():
        return None
    uri = source_uri(cik)
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='companyfacts_validators'"
        ).fetchone()
        if table is None:
            return None
        row = db.execute(
            "SELECT v.etag,v.sha256,o.response,o.source_uri,EXISTS("
            "SELECT 1 FROM companyfacts_checks c "
            "WHERE c.issuer_cik=v.issuer_cik AND c.sha256=v.sha256 "
            "AND c.provenance IN ('SEC_HTTPS_RESPONSE','SEC_HTTPS_304_NOT_MODIFIED')) "
            "FROM companyfacts_validators v "
            "JOIN companyfacts_observations o ON o.issuer_cik=v.issuer_cik AND o.sha256=v.sha256 "
            "WHERE v.issuer_cik=? AND v.source_uri=?",
            (cik10(cik), uri),
        ).fetchone()
    if row is None:
        return None
    etag, digest, raw, stored_uri, has_live_check = row
    if (not _valid_etag(etag) or not isinstance(raw, bytes)
            or hashlib.sha256(raw).hexdigest() != digest or stored_uri != uri
            or not has_live_check):
        raise ValueError("Stored CompanyFacts cache failed integrity validation")
    _validate_payload(raw, cik)
    return {"etag": etag, "sha256": digest, "raw": raw, "source_uri": uri}


def _fetch_http(cik: str, *, user_agent: str,
                cached: dict | None = None) -> tuple[bytes, str | None, bool]:
    target = cik10(cik)
    if not _valid_user_agent(user_agent):
        raise ValueError("Real non-placeholder SEC contact-bearing User-Agent required")
    url = source_uri(target)
    headers = {"User-Agent": user_agent, "Accept": "application/json",
               "Accept-Encoding": "identity"}
    if cached is not None:
        if (cached.get("source_uri") != url or not _valid_etag(cached.get("etag"))
                or hashlib.sha256(cached.get("raw", b"")).hexdigest() != cached.get("sha256")):
            raise ValueError("CompanyFacts conditional cache failed integrity validation")
        headers["If-None-Match"] = cached["etag"]
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def read_response(response):
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Unexpected SEC CompanyFacts status or redirect")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or int(length) > MAX_COMPANYFACTS_BYTES):
            raise ValueError("SEC CompanyFacts response size rejected")
        content_type = response.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise ValueError("SEC CompanyFacts response is not JSON")
        raw = response.read(MAX_COMPANYFACTS_BYTES + 1)
        return raw, (response.headers.get("ETag")
                     if _valid_etag(response.headers.get("ETag")) else None), False

    def read_not_modified(error):
        if cached is None:
            raise ValueError("SEC CompanyFacts 304 without a verified cached response")
        if error.geturl() != url:
            raise ValueError("SEC CompanyFacts 304 source URL mismatch")
        value = error.headers.get("ETag")
        if value is not None and not _valid_etag(value):
            raise ValueError("SEC CompanyFacts 304 ETag is invalid")
        return cached["raw"], value or cached["etag"], True

    try:
        raw, etag, unchanged = _bounded_sec_get(
            opener, request, read_response, read_not_modified=read_not_modified,
        )
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        raise ValueError(f"SEC CompanyFacts request failed: {type(exc).__name__}") from exc
    if not 0 < len(raw) <= MAX_COMPANYFACTS_BYTES:
        raise ValueError("SEC CompanyFacts response empty or oversized")
    _validate_payload(raw, target)
    return raw, etag, unchanged


def fetch_companyfacts_with_cache(db_path: Path, cik: str, *, user_agent: str,
                                  allow_network: bool = False) -> tuple[bytes, str | None, bool]:
    if not allow_network:
        raise ValueError("Network disabled unless --allow-network is provided")
    return _fetch_http(cik, user_agent=user_agent, cached=_load_cache(db_path, cik))


def list_companyfacts(db_path: Path, *, cik: str, as_of: str) -> list[dict]:
    target, cutoff = cik10(cik), parse_day(as_of).isoformat()
    path = Path(db_path).expanduser()
    if path.is_symlink() or not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='companyfacts_observations'"
        ).fetchone()
        if exists is None:
            return []
        rows = db.execute(
            "SELECT sha256,source_uri,entity_name,collected_at,as_of_cutoff,provenance,length(response) "
            "FROM companyfacts_observations WHERE issuer_cik=? AND as_of_cutoff<=? "
            "AND date(collected_at)<=? ORDER BY collected_at,sha256",
            (target, cutoff, cutoff),
        ).fetchall()
    return [{"sha256": sha, "source_uri": uri, "entity_name": name,
             "collected_at": collected, "as_of_cutoff": indexed_asof,
             "provenance": provenance, "response_bytes": size,
             "financial_claim_verified": False, "source_authenticity_verified": False}
            for sha, uri, name, collected, indexed_asof, provenance, size in rows]


def read_companyfacts(db_path: Path, *, cik: str, sha256: str,
                      as_of: str | None = None) -> bytes:
    raw, _ = _read_companyfacts_record(db_path, cik=cik, sha256=sha256, as_of=as_of)
    return raw


def _read_companyfacts_record(db_path: Path, *, cik: str, sha256: str,
                              as_of: str | None) -> tuple[bytes, dict]:
    target = cik10(cik)
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ValueError("Invalid CompanyFacts SHA-256")
    path = Path(db_path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("CompanyFacts DB is unavailable")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        row = db.execute(
            "SELECT response,source_uri,collected_at,as_of_cutoff,entity_name,provenance "
            "FROM companyfacts_observations "
            "WHERE issuer_cik=? AND sha256=?", (target, sha256),
        ).fetchone()
    if row is None:
        raise KeyError("CompanyFacts observation not found")
    raw, uri, collected, stored_cutoff, entity_name, provenance = row
    if (not isinstance(raw, bytes) or uri != source_uri(target)
            or hashlib.sha256(raw).hexdigest() != sha256
            or parse_day(stored_cutoff).isoformat() != stored_cutoff):
        raise ValueError("CompanyFacts source integrity failed")
    indexed = index_companyfacts(
        raw, cik=target, as_of=stored_cutoff, collected_at=collected,
        provenance=provenance,
    )
    if (indexed["source_uri"] != uri or indexed["entity_name"] != entity_name
            or indexed["source_sha256"] != sha256):
        raise ValueError("CompanyFacts metadata integrity failed")
    if as_of is not None:
        day = parse_day(as_of).isoformat()
        if stored_cutoff > day or collected[:10] > day:
            raise ValueError("CompanyFacts response was not available by as-of date")
    payload, _, _ = _validate_payload(raw, target)
    return raw, {"indexed": indexed, "companyfacts": payload}


def read_companyfacts_envelope(db_path: Path, *, cik: str, sha256: str,
                               as_of: str) -> dict[str, Any]:
    """Build a versioned read-only JSON handoff from one integrity-checked DB row."""
    raw, record = _read_companyfacts_record(
        db_path, cik=cik, sha256=sha256, as_of=as_of,
    )
    return {
        "schema": "disclosure-lightning.companyfacts-envelope.v1",
        **record["indexed"],
        "companyfacts": record["companyfacts"],
        "response_bytes": len(raw),
        "financial_claim_verified": False,
        "source_authenticity_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only SEC CompanyFacts raw evidence cache")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--cik", required=True)
    parser.add_argument("--as-of", required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input-json", type=Path)
    group.add_argument("--allow-network", action="store_true")
    group.add_argument("--read-sha256")
    parser.add_argument("--collected-at")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.list:
            if args.input_json or args.allow_network or args.read_sha256 or args.collected_at:
                raise ValueError("Read-only listing cannot import or fetch")
            result = {"status": "READ_ONLY", "as_of": parse_day(args.as_of).isoformat(),
                      "observations": list_companyfacts(args.db, cik=args.cik, as_of=args.as_of)}
        elif args.read_sha256:
            if args.collected_at is not None:
                raise ValueError("Read-only retrieval does not accept a collection timestamp")
            result = read_companyfacts_envelope(
                args.db, cik=args.cik, sha256=args.read_sha256, as_of=args.as_of,
            )
            result["status"] = "READ_ONLY"
        else:
            if bool(args.input_json) == bool(args.allow_network):
                raise ValueError("Provide exactly one of --input-json or --allow-network")
            if args.allow_network and args.collected_at is not None:
                raise ValueError("Live retrieval timestamp is derived from actual process time")
            if args.input_json:
                raw = core._read_local_json(
                    args.input_json, max_bytes=MAX_COMPANYFACTS_BYTES,
                )
                etag, unchanged, provenance = None, False, "OFFLINE_UNVERIFIED"
            else:
                raw, etag, unchanged = fetch_companyfacts_with_cache(
                    args.db, args.cik,
                    user_agent=os.environ.get("DL_SEC_USER_AGENT", ""), allow_network=True,
                )
                provenance = "SEC_HTTPS_RESPONSE"
            indexed = index_companyfacts(
                raw, cik=args.cik, as_of=args.as_of,
                collected_at=args.collected_at, provenance=provenance,
            )
            saved = save_companyfacts(
                args.db, raw, indexed, etag=etag,
                check_provenance="SEC_HTTPS_304_NOT_MODIFIED" if unchanged else None,
            )
            result = {**saved, "indexed": indexed}
            if args.allow_network:
                result["http_cache"] = {"response_not_modified": unchanged,
                                        "etag_stored": etag is not None,
                                        "source_authenticity_verified": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "DL_COMPANYFACTS_FAILED", "reason": str(exc)[:400]},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
