"""Disclosure Lightning MVP: bounded SEC submissions → immutable local evidence.

No implicit network. No finance claims. Standard-library only. Public-source
metadata alone is NOT verification of original filing document content.
"""
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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROVIDER = "SEC_EDGAR"
MAX_JSON_BYTES = 8_000_000
MAX_RECORDS = 1000
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


def _validate_raw(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_JSON_BYTES:
        raise ValueError("SEC submissions JSON must be 1..8MB")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 SEC submissions JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Submissions root must be a JSON object")
    return payload


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
"""


def _validate_index_for_save(raw: bytes, indexed: dict) -> None:
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
        accepted_at = _accepted(accepted[i]) if accepted is not None else None
        if (record.get("schema_version") != "1.0"
                or record.get("provider") != PROVIDER
                or record.get("issuer_cik") != target
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


def save_index(db_path: Path, raw: bytes, indexed: dict) -> dict:
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
    _validate_index_for_save(raw, indexed)
    path.parent.mkdir(parents=True, exist_ok=True)
    inserted = 0
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        with conn:
            conn.executescript(SCHEMA)
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


def list_filings(db_path: Path, *, cik: str, limit: int = 50) -> list[dict]:
    if not 1 <= limit <= 200:
        raise ValueError("Output limit must be 1..200")
    uri = Path(db_path).expanduser().resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        return [json.loads(row[0]) for row in conn.execute(
            "SELECT filing_json FROM filings WHERE provider=? AND issuer_cik=?"
            " ORDER BY accession DESC LIMIT ?", (PROVIDER, cik10(cik), limit)
        )]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_submissions(cik: str, *, user_agent: str, allow_network: bool = False) -> bytes:
    if not allow_network:
        raise ValueError("Network disabled unless --allow-network is provided")
    target = cik10(cik)
    if not _valid_user_agent(user_agent):
        raise ValueError("Real non-placeholder SEC contact-bearing User-Agent required")
    url = f"https://data.sec.gov/submissions/CIK{target}.json"
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept": "application/json",
                      "Accept-Encoding": "identity"}, method="GET"
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect()
    )
    try:
        with opener.open(req, timeout=15) as resp:
            if resp.status != 200 or resp.geturl() != url:
                raise ValueError("Unexpected SEC HTTP status or redirect")
            if resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("SEC response is not application/json")
            size = resp.headers.get("Content-Length")
            if size is not None and (not size.isdecimal() or int(size) > MAX_JSON_BYTES):
                raise ValueError("SEC response size rejected")
            raw = resp.read(MAX_JSON_BYTES + 1)
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
        raise ValueError(f"SEC request failed: {type(exc).__name__}") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("SEC response exceeded 8MB")
    _validate_raw(raw)
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DL SEC filing index offline-first MVP")
    parser.add_argument("--cik", required=True, help="SEC CIK; zero-padded internally")
    parser.add_argument("--as-of", required=True, help="Exclude filings after YYYY-MM-DD")
    parser.add_argument("--forms", default="10-K,10-K/A,10-Q,10-Q/A,8-K,8-K/A", help="Allowed SEC forms; includes amendments by default")
    parser.add_argument("--input-json", type=Path, help="Local SEC-style response JSON (offline)")
    parser.add_argument("--allow-network", action="store_true", help="Explicit one GET to data.sec.gov")
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
            result = {"status": "READ_ONLY", "filings": list_filings(args.db, cik=cik)}
        else:
            if bool(args.input_json) == bool(args.allow_network):
                raise ValueError("Choose exactly one --input-json or --allow-network")
            if args.allow_network and args.collected_at is not None:
                raise ValueError("Live SEC observation time must be measured, not caller supplied")
            forms = parse_forms(args.forms)
            parse_day(args.as_of)
            if args.input_json:
                path = args.input_json
                if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
                    raise ValueError("Offline JSON must be a regular bounded file")
                raw = path.read_bytes()
                provenance = "OFFLINE_UNVERIFIED"
            else:
                raw = fetch_submissions(
                    cik, user_agent=os.environ.get("DL_SEC_USER_AGENT", ""), allow_network=True
                )
                provenance = "SEC_HTTPS_RESPONSE"
            indexed = index_submissions(
                raw, cik=cik, as_of=args.as_of, forms=forms, provenance=provenance,
                collected_at=args.collected_at,
            )
            saved = save_index(args.db, raw, indexed)
            result = {**saved, "indexed": indexed}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "DL_FAILED", "reason": str(exc)[:400]}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
