"""KUODRA v1 synthetic/public/private *local* canonical numeric evidence core.

This is not an institution-approved security boundary. The caller must enforce
real access control and host-level deny-egress before handling any private data.
No filesystem, network, LLM, database, upload, or persistence calls occur here.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import math
import re
from typing import Any

HEADER = ("entity_id", "metric_id", "observation_at", "available_at", "value", "unit")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z", re.ASCII)
_VALUE = re.compile(r"-?(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?\Z", re.ASCII)
_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z", re.ASCII)
_MAX_CSV = 1_000_000
_MAX_ROWS = 5000


def _instant(value: str) -> datetime:
    if type(value) is not str or not _TS.fullmatch(value):
        raise ValueError("CANONICAL_UTC_TIMESTAMP_REQUIRED")
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if result.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            raise ValueError("CANONICAL_UTC_TIMESTAMP_REQUIRED")
        return result
    except ValueError as exc:
        raise ValueError("CANONICAL_UTC_TIMESTAMP_REQUIRED") from exc


def _id(value: str) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def normalize_local_csv(raw: bytes, *, dataset_id: str, source_id: str,
                        access_level: str, consent: bool = False) -> dict[str, Any]:
    """Normalize six exact UTF-8 CSV columns to immutable-like long records.

    Consent is an explicit operator acknowledgement, NOT authentication or an
    ACL. Only trusted callers may supply this metadata; PUBLIC/PRIVATE bytes
    must never be uploaded to the public repository by this function's caller.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_CSV
            or not _id(dataset_id) or not _id(source_id)
            or access_level not in ("PUBLIC", "PRIVATE")
            or type(consent) is not bool
            or (access_level == "PRIVATE" and not consent)):
        raise ValueError("CANONICAL_SOURCE_POLICY_DENIED")
    try:
        decoded = raw.decode("utf-8", errors="strict")
        if "\0" in decoded or "\r" in decoded.replace("\r\n", ""):
            raise ValueError("CANONICAL_CSV_INVALID")
        rows = csv.reader(StringIO(decoded, newline=""), strict=True)
        if tuple(next(rows)) != HEADER:
            raise ValueError("CANONICAL_CSV_HEADER_INVALID")
        records = []
        duplicates: set[tuple[str, str, str]] = set()
        units: dict[str, str] = {}
        for cells in rows:
            if len(cells) != 6 or any(not x for x in cells):
                raise ValueError("CANONICAL_CSV_ROW_INVALID")
            entity, metric, observed, available, value, unit = cells
            if not _id(entity) or not _id(metric) or not _id(unit):
                raise ValueError("CANONICAL_CSV_IDENTIFIER_INVALID")
            obs_at = _instant(observed)
            ready_at = _instant(available)
            if ready_at < obs_at:
                raise ValueError("CANONICAL_RELEASE_PRECEDES_OBSERVATION")
            if not _VALUE.fullmatch(value):
                raise ValueError("CANONICAL_VALUE_INVALID")
            number = Decimal(value)
            if not number.is_finite():
                raise ValueError("CANONICAL_VALUE_INVALID")
            key = (entity, metric, observed)
            if key in duplicates:
                raise ValueError("CANONICAL_DUPLICATE_OR_REVISION_UNDECLARED")
            duplicates.add(key)
            if metric in units and units[metric] != unit:
                raise ValueError("CANONICAL_UNIT_CONFLICT")
            units[metric] = unit
            records.append({"dataset_id": dataset_id, "entity_id": entity,
                "metric_id": metric, "observation_at": observed,
                "available_at": available, "value": str(number), "unit": unit,
                "source_id": source_id, "access_level": access_level,
                "evidence_sha256": sha256(raw).hexdigest()})
            if len(records) > _MAX_ROWS:
                raise ValueError("CANONICAL_ROW_LIMIT_EXCEEDED")
        if not records:
            raise ValueError("CANONICAL_EMPTY_DATASET")
    except (UnicodeError, csv.Error, StopIteration, InvalidOperation) as exc:
        raise ValueError("CANONICAL_CSV_INVALID") from exc
    return {"schema": "kuodra.canonical.long.v1", "dataset_id": dataset_id,
            "source_id": source_id, "access_level": access_level,
            "source_sha256": sha256(raw).hexdigest(), "source_authenticated": False,
            "source_rights_verified": False, "publisher_vintage_verified": False,
            "host_egress_policy_verified": False, "rows": len(records),
            "records": records, "network_requests": 0, "raw_persisted": False}


def observed_relationships(dataset: dict, *, metrics: tuple[str, ...],
                           as_of: str, max_results: int = 3,
                           min_pairs: int = 12) -> dict[str, Any]:
    """Descriptive *association* only: no p-values, causal or accuracy claims.

    Pairwise complete observations at the SAME timestamp and entity, filtered
    on release time; no silent forward-fill, unit conversion or cross-owner join.
    """
    cutoff = _instant(as_of)
    if (type(dataset) is not dict or dataset.get("schema") != "kuodra.canonical.long.v1"
            or dataset.get("access_level") not in ("PUBLIC", "PRIVATE")
            or type(metrics) is not tuple or not 2 <= len(metrics) <= 12
            or len(set(metrics)) != len(metrics)
            or any(not _id(m) for m in metrics)
            or type(max_results) is not int or not 1 <= max_results <= 3
            or type(min_pairs) is not int or min_pairs < 12):
        raise ValueError("INSIGHT_INPUT_CONTRACT_INVALID")
    records = dataset.get("records")
    if type(records) is not list or not records or len(records) != dataset.get("rows"):
        raise ValueError("INSIGHT_ROWS_CONTRACT_INVALID")
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for row in records:
        if (type(row) is not dict or row.get("dataset_id") != dataset["dataset_id"]
                or row.get("access_level") != dataset["access_level"]
                or row.get("source_id") != dataset["source_id"]
                or row.get("evidence_sha256") != dataset["source_sha256"]):
            raise ValueError("INSIGHT_SOURCE_LINEAGE_INVALID")
        # The canonical dataset is a mutable Python mapping after import.
        # A caller may modify its observation/release timestamps without
        # changing the stored source label. Revalidate chronology BEFORE
        # filtering; otherwise an impossible, backdated release can insert
        # future observations into a historical association.
        observed, released = _instant(row["observation_at"]), _instant(row["available_at"])
        if released < observed:
            raise ValueError("INSIGHT_RELEASE_ORDER_INVALID")
        if row["metric_id"] not in metrics or observed > cutoff or released > cutoff:
            continue
        key = (row["entity_id"], row["observation_at"])
        bucket = grouped.setdefault(key, {})
        if row["metric_id"] in bucket:
            raise ValueError("INSIGHT_DUPLICATE_SERIES")
        numeric = float(Decimal(row["value"]))
        if not math.isfinite(numeric):
            raise ValueError("INSIGHT_NUMERIC_RANGE_INVALID")
        bucket[row["metric_id"]] = numeric
    found = []
    for i, a in enumerate(metrics):
        for b in metrics[i+1:]:
            paired = [(v[a],v[b]) for v in grouped.values() if a in v and b in v]
            if len(paired) < min_pairs:
                continue
            xs, ys = zip(*paired)
            xa, ya = math.fsum(xs)/len(xs), math.fsum(ys)/len(ys)
            vx = math.fsum((v-xa)**2 for v in xs)
            vy = math.fsum((v-ya)**2 for v in ys)
            if vx <= 0 or vy <= 0:
                continue
            cov = math.fsum((x-xa)*(y-ya) for x,y in paired)
            r = max(-1.0, min(1.0, cov/math.sqrt(vx*vy)))
            found.append({"metric_a": a, "metric_b": b,
                          "pearson_r": round(r, 6), "paired_n": len(paired),
                          "finding_type": "DESCRIPTIVE_ASSOCIATION_ONLY",
                          "significance_status": "NOT_EVALUATED",
                          "causal_claim": False, "predictive_claim": False})
    found.sort(key=lambda x: -abs(x["pearson_r"]))
    return {"schema": "kuodra.insights.descriptive.v1",
            "status": "DESCRIPTIVE_ONLY" if found else "INSUFFICIENT_EVIDENCE",
            "dataset_id": dataset["dataset_id"], "access_level": dataset["access_level"],
            "source_sha256": dataset["source_sha256"], "as_of": as_of,
            "hypotheses_tested": len(metrics)*(len(metrics)-1)//2,
            "multiple_testing_status": "NOT_ADJUSTED_NO_SIGNIFICANCE_CLAIM",
            "insights": found[:max_results], "model_trained": False,
            "guard": "HOLD", "network_requests": 0}


def normalize_local_sqlite(raw_db: bytes, *, table: str, dataset_id: str,
                           source_id: str, access_level: str,
                           consent: bool = False) -> dict[str, Any]:
    """Read a bounded SQLite *byte copy* in memory, no caller SQL or disk I/O.

    This is NOT a secure parser for hostile DB files. A sandboxed worker and
    institution ACL are needed for actual confidential document ingestion.
    """
    import sqlite3
    if (type(raw_db) is not bytes or not 100 < len(raw_db) <= 2_000_000
            or not raw_db.startswith(b"SQLite format 3\x00")
            or not _id(table) or table.startswith("sqlite_")
            or access_level not in ("PUBLIC", "PRIVATE")
            or type(consent) is not bool
            or (access_level == "PRIVATE" and not consent)):
        raise ValueError("SQLITE_INPUT_OR_SCOPE_DENIED")
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(raw_db)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        meta=connection.execute(
            "SELECT type,sql FROM sqlite_master WHERE name=?",(table,)
        ).fetchone()
        if (meta is None or meta[0] != "table"
                or type(meta[1]) is not str
                or "VIRTUAL TABLE" in meta[1].upper()):
            raise ValueError("SQLITE_PLAIN_TABLE_REQUIRED")
        cols=[r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
        if tuple(cols) != HEADER:
            raise ValueError("SQLITE_CANONICAL_COLUMNS_REQUIRED")
        query="SELECT " + ",".join('"'+c+'"' for c in HEADER)+f' FROM "{table}" LIMIT {_MAX_ROWS+1}'
        values=connection.execute(query).fetchall()
        if not values or len(values)>_MAX_ROWS:
            raise ValueError("SQLITE_ROW_LIMIT_OR_EMPTY")
        f=StringIO(newline="")
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(HEADER)
        for row in values:
            if any(type(cell) is not str for cell in row):
                raise ValueError("SQLITE_TEXT_COLUMNS_REQUIRED")
            writer.writerow(row)
        normalized=normalize_local_csv(f.getvalue().encode("utf-8"),
            dataset_id=dataset_id,source_id=source_id,
            access_level=access_level,consent=consent)
        source_hash=sha256(raw_db).hexdigest()
        normalized["normalized_csv_sha256"]=normalized["source_sha256"]
        normalized["source_sha256"]=source_hash
        normalized["source_type"]="SQLITE_IN_MEMORY_READ_ONLY"
        for row in normalized["records"]:
            row["evidence_sha256"]=source_hash
        return normalized
    except (sqlite3.DatabaseError, UnicodeError, AttributeError) as exc:
        raise ValueError("SQLITE_MALFORMED_OR_UNSUPPORTED") from exc
    finally:
        connection.close()
