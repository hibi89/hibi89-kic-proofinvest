"""Fictional-only local backend demo: wide CSV + SQLite -> alias -> ML Guard.

No file inputs, real institutions, external providers, credentials, network,
production URLs, publication or trade. Publisher identity and source rights
are NOT established. This is a transparent test fixture / judge replay.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
import sqlite3
from typing import Any

from .kuodra_alias_hybrid import analyze_owner_alias_group_ml
from .kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

_AS_OF = '2026-01-01T00:00:00Z'
_OWNER = VerifiedPrincipal('syntheticOwner', 'syntheticFund', ('owner',), True)


def _fictional_wide_public() -> bytes:
    output = StringIO(newline='')
    w = csv.writer(output, lineterminator='\n')
    w.writerow(('entity_id', 'observation_at', 'available_at', 'priceFactor'))
    for j in range(10):
        for i in range(62):
            date = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            t = date.strftime('%Y-%m-%dT%H:%M:%SZ')
            w.writerow((f'fictionalPublic{j}', t, t, str(round(i + j * 0.4, 3))))
    return output.getvalue().encode('utf-8')


def _fictional_wide_private_db() -> bytes:
    db = sqlite3.connect(':memory:')
    try:
        db.execute('CREATE TABLE measurements (entity_id TEXT, observation_at TEXT, '
                   'available_at TEXT, resultSignal TEXT)')
        rows = []
        for j in range(10):
            for i in range(62):
                date = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
                t = date.strftime('%Y-%m-%dT%H:%M:%SZ')
                rows.append((f'fictionalPrivate{j}', t, t, str(i * 3 + j * 2 + 4)))
        db.executemany('INSERT INTO measurements VALUES (?,?,?,?)', rows)
        return db.serialize()
    finally:
        db.close()


def run_synthetic_wide_alias_ml_demo() -> dict[str, Any]:
    """Run actual owner gateway, two adapters, alias and grouped heldout ML."""
    public = _fictional_wide_public()
    private = _fictional_wide_private_db()
    vault = OwnerLocalGateway('syntheticFund')
    pub = vault.ingest_mapped_wide_csv(
        _OWNER, raw=public, dataset_id='fictionalPublicSource',
        source_id='syntheticCSV', access_level='PUBLIC',
        metric_columns={'priceFactor': ('factor', 'count')})
    priv = vault.ingest_mapped_wide_sqlite(
        _OWNER, raw_db=private, table='measurements',
        dataset_id='fictionalPrivateSource', source_id='syntheticSQLite',
        access_level='PRIVATE',
        metric_columns={'resultSignal': ('outcome', 'usd')})
    if pub['rows'] != 620 or priv['rows'] != 620:
        raise RuntimeError('SYNTHETIC_CANONICAL_ROW_COUNT_CHANGED')
    report = analyze_owner_alias_group_ml(
        vault, _OWNER, public_dataset_id='fictionalPublicSource',
        private_dataset_id='fictionalPrivateSource',
        public_sha256=sha256(public).hexdigest(),
        private_sha256=sha256(private).hexdigest(),
        aliases={f'fictionalPublic{j}': f'fictionalPrivate{j}' for j in range(10)},
        as_of=_AS_OF, target_metric='private.outcome',
        feature_metrics=('public.factor',))
    analysis = report['analysis']
    if (report['decision'] != 'HOLD'
            or report['public_export_allowed'] is not False
            or analysis['status'] != 'EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED'
            or analysis['production_ready'] is not False
            or analysis['calibrated_probability'] is not None):
        raise RuntimeError('SYNTHETIC_HYBRID_ML_REVIEW_POLICY_INVALID')
    result = {
        'schema': 'kuodra.synthetic-wide-alias-group-ml.v1',
        'synthetic_only': True,
        'workflow': 'PUBLIC_WIDE_CSV_PRIVATE_WIDE_SQLITE_EXPLICIT_ALIAS_GROUP_TIME_ML',
        'public_canonical_rows': pub['rows'],
        'private_canonical_rows': priv['rows'],
        'mapping_sha256': report['mapping_sha256'],
        'source_hashes': report['source_hashes'],
        'analysis': analysis, 'decision': 'HOLD',
        'local_owner_authority_emulated': True,
        'institution_host_iam_verified': False,
        'host_os_egress_verified': False,
        'original_issuer_source_verified': False,
        'cross_source_entity_link_verified': False,
        'source_rights_verified': False,
        'calibrated_probability': None,
        'external_api_requests': 0, 'public_export_allowed': False,
        'trade_authorized': False, 'production_ready': False,
    }
    serialized = json.dumps(result, sort_keys=True, allow_nan=False)
    if any(secret in serialized for secret in ('fictionalPublic0', 'fictionalPrivate0',
                                              'syntheticFund', 'syntheticOwner',
                                              'syntheticCSV', 'syntheticSQLite')):
        raise RuntimeError('SYNTHETIC_DEMO_IDENTITY_LEAK')
    return result


def main() -> int:
    print(json.dumps(run_synthetic_wide_alias_ml_demo(),
                     ensure_ascii=True, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
