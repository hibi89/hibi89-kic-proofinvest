"""In-memory SQLite wide table -> explicit KUODRA long schema (fictional QA).

SQLCipher/encryption, hostile SQLite parser sandbox, institution IAM and OS
network isolation are NOT provided. Raw private files need an approved host.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import sqlite3
from typing import Any

from .kuodra_unified_core import _id, _MAX_ROWS
from .kuodra_wide_adapter import normalize_mapped_wide_csv


def normalize_mapped_wide_sqlite(raw_db: bytes, *, table: str,
                                 dataset_id: str, source_id: str,
                                 access_level: str,
                                 metric_columns: dict[str, tuple[str, str]],
                                 consent: bool = False) -> dict[str, Any]:
    """Read only a plain table, require exact metadata + mapped metric columns."""
    if (type(raw_db) is not bytes or not 100 < len(raw_db) <= 2_000_000
            or not raw_db.startswith(b'SQLite format 3\x00')
            or not _id(table) or table.lower().startswith('sqlite_')
            or type(metric_columns) is not dict
            or not 1 <= len(metric_columns) <= 12):
        raise ValueError('WIDE_SQLITE_INPUT_OR_TABLE_DENIED')
    connection = sqlite3.connect(':memory:')
    try:
        connection.deserialize(raw_db)
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.execute('PRAGMA query_only=ON')
        meta = connection.execute('SELECT type, sql FROM sqlite_master WHERE name=?',
                                  (table,)).fetchone()
        if (meta is None or meta[0] != 'table' or type(meta[1]) is not str
                or 'VIRTUAL TABLE' in meta[1].upper()):
            raise ValueError('WIDE_SQLITE_PLAIN_TABLE_REQUIRED')
        columns = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
        expected = {'entity_id', 'observation_at', 'available_at'} | set(metric_columns)
        if (len(columns) != len(expected) or any(not _id(c) for c in columns)
                or len(set(columns)) != len(columns)
                or set(columns) != expected):
            raise ValueError('WIDE_SQLITE_EXACT_COLUMNS_REQUIRED')
        query = 'SELECT ' + ','.join('"' + c + '"' for c in columns) + \
                f' FROM "{table}" LIMIT {_MAX_ROWS + 1}'
        values = connection.execute(query).fetchall()
        if not values or len(values) > _MAX_ROWS:
            raise ValueError('WIDE_SQLITE_ROWS_OUT_OF_RANGE')
        buffer = StringIO(newline='')
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(columns)
        for row in values:
            if any(type(cell) is not str for cell in row):
                raise ValueError('WIDE_SQLITE_TEXT_CELLS_REQUIRED')
            writer.writerow(row)
        normalized_wide = buffer.getvalue().encode('utf-8')
        result = normalize_mapped_wide_csv(normalized_wide,
                  dataset_id=dataset_id, source_id=source_id,
                  access_level=access_level, metric_columns=metric_columns,
                  consent=consent)
        db_digest = sha256(raw_db).hexdigest()
        result['wide_csv_sha256'] = result['source_sha256']
        result['source_sha256'] = db_digest
        result['source_type'] = 'MAPPED_WIDE_SQLITE_IN_MEMORY_UNVERIFIED'
        for record in result['records']:
            record['evidence_sha256'] = db_digest
        return result
    except (sqlite3.DatabaseError, UnicodeError, AttributeError) as exc:
        raise ValueError('WIDE_SQLITE_MALFORMED_OR_UNSUPPORTED') from exc
    finally:
        connection.close()
