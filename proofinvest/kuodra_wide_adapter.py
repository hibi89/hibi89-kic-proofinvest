"""Explicit column-mapped wide CSV -> KUODRA canonical long observations.

Requires operator-approved field mapping. No guessed units, release dates,
issuer identity, license or trusted host authentication. Bytes remain local;
source hash and mapping hash are separately retained. This is not a sandbox.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from io import StringIO
import json
from typing import Any

from .kuodra_unified_core import (_MAX_CSV, _MAX_ROWS, HEADER, _id,
                                   _instant, normalize_local_csv)

_PREFIX = ('entity_id', 'observation_at', 'available_at')


def normalize_mapped_wide_csv(raw: bytes, *, dataset_id: str, source_id: str,
                              access_level: str,
                              metric_columns: dict[str, tuple[str, str]],
                              consent: bool = False) -> dict[str, Any]:
    """Transform a bounded wide table with explicit metric+unit mappings.

    Every wide row must supply exact entity and observation/release timestamps;
    metric cells may be blank and are skipped, but metadata cannot be missing.
    All numeric, unit and duplicate checks run through the existing canonical
    long parser. No unpublished private records leave this in-memory function.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= _MAX_CSV
            or not _id(dataset_id) or not _id(source_id)
            or access_level not in ('PUBLIC', 'PRIVATE')
            or type(consent) is not bool or (access_level == 'PRIVATE' and not consent)
            or type(metric_columns) is not dict or not 1 <= len(metric_columns) <= 12):
        raise ValueError('WIDE_SOURCE_OR_MAPPING_DENIED')
    mapped = []
    metric_names = set()
    for field, spec in metric_columns.items():
        if (not _id(field) or field in _PREFIX or type(spec) is not tuple
                or len(spec) != 2 or not _id(spec[0]) or not _id(spec[1])
                or spec[0] in metric_names):
            raise ValueError('WIDE_METRIC_MAPPING_INVALID')
        metric_names.add(spec[0])
        mapped.append((field, spec[0], spec[1]))
    mapped.sort()
    try:
        decoded = raw.decode('utf-8', errors='strict')
        if '\x00' in decoded or '\r' in decoded.replace('\r\n', ''):
            raise ValueError('WIDE_CSV_INVALID')
        reader = csv.reader(StringIO(decoded, newline=''), strict=True)
        header = tuple(next(reader))
        expected = set(_PREFIX) | set(metric_columns)
        if (len(header) != len(expected) or len(set(header)) != len(header)
                or set(header) != expected):
            raise ValueError('WIDE_CSV_EXACT_HEADER_REQUIRED')
        columns = {name: index for index, name in enumerate(header)}
        output = StringIO(newline='')
        writer = csv.writer(output, lineterminator='\n')
        writer.writerow(HEADER)
        total = 0
        for row in reader:
            if len(row) != len(header):
                raise ValueError('WIDE_CSV_ROW_INVALID')
            entity = row[columns['entity_id']]
            observed = row[columns['observation_at']]
            available = row[columns['available_at']]
            if not _id(entity) or _instant(available) < _instant(observed):
                raise ValueError('WIDE_ROW_ENTITY_OR_RELEASE_INVALID')
            for field, metric, unit in mapped:
                value = row[columns[field]]
                if value == '':
                    continue
                total += 1
                if total > _MAX_ROWS:
                    raise ValueError('WIDE_CANONICAL_ROW_LIMIT_EXCEEDED')
                writer.writerow((entity, metric, observed, available, value, unit))
        if total == 0:
            raise ValueError('WIDE_NO_NUMERIC_METRICS')
    except (UnicodeError, csv.Error, StopIteration) as exc:
        raise ValueError('WIDE_CSV_INVALID') from exc

    canonical_bytes = output.getvalue().encode('utf-8')
    result = normalize_local_csv(canonical_bytes, dataset_id=dataset_id,
                                  source_id=source_id,
                                  access_level=access_level, consent=consent)
    original_digest = sha256(raw).hexdigest()
    normalized_digest = result['source_sha256']
    mapping = {field: {'metric_id': metric, 'unit': unit}
               for field, metric, unit in mapped}
    mapping_digest = sha256((json.dumps(mapping, sort_keys=True,
                   separators=(',', ':'), ensure_ascii=True) + '\n').encode('utf-8')).hexdigest()
    result.update(source_type='EXPLICIT_WIDE_CSV_LOCAL_UNVERIFIED',
                  source_sha256=original_digest,
                  normalized_csv_sha256=normalized_digest,
                  mapping_sha256=mapping_digest,
                  inferred_units=False, issuer_identity_authenticated=False)
    for record in result['records']:
        record['evidence_sha256'] = original_digest
        record['mapping_sha256'] = mapping_digest
    return result
