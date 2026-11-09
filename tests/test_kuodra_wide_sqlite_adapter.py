"""Explicit private wide SQLite source-to-canonical and owner ACL tests."""
from hashlib import sha256
import sqlite3
import unittest

from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal
from proofinvest.kuodra_wide_sqlite_adapter import normalize_mapped_wide_sqlite

OWNER = VerifiedPrincipal('ownerDemo', 'fundDemo', ('owner',), True)
ANALYST = VerifiedPrincipal('analystDemo', 'fundDemo', ('analyst',), True)
MAPPING = {'cash': ('cashflow', 'usd'), 'sales': ('revenue', 'usd')}


def sample(*, bad_type=False, rogue=False):
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute('CREATE TABLE measurements (entity_id TEXT, observation_at TEXT, '
                     'available_at TEXT, cash TEXT, sales TEXT' +
                     (', secret TEXT' if rogue else '') + ')')
        for day in range(1, 25):
            ts = f'2026-01-{day:02d}T00:00:00Z'
            vals = ('issuerLocal', ts, ts, sqlite3.Binary(b'nottext') if bad_type and day == 1 else str(day),
                    str(day * 2))
            conn.execute('INSERT INTO measurements VALUES (' +
                         ','.join('?' for _ in range(6 if rogue else 5)) + ')',
                         vals + (('private',) if rogue else ()))
        return conn.serialize()
    finally:
        conn.close()


class WideSQLiteTest(unittest.TestCase):
    def test_reuses_canonical_with_pinned_original_db(self):
        raw = sample()
        record = normalize_mapped_wide_sqlite(raw, table='measurements',
            dataset_id='measured', source_id='uploaded',
            access_level='PRIVATE', metric_columns=MAPPING, consent=True)
        self.assertEqual(record['rows'], 48)
        self.assertEqual(record['source_sha256'], sha256(raw).hexdigest())
        self.assertNotEqual(record['source_sha256'], record['wide_csv_sha256'])
        self.assertEqual(record['source_type'], 'MAPPED_WIDE_SQLITE_IN_MEMORY_UNVERIFIED')
        self.assertFalse(record['source_authenticated'])
        self.assertTrue(all(r['evidence_sha256'] == record['source_sha256']
                            for r in record['records']))

    def test_owner_scope_to_descriptive_and_denied_export(self):
        vault = OwnerLocalGateway('fundDemo')
        receipt = vault.ingest_mapped_wide_sqlite(OWNER, raw_db=sample(),
            table='measurements', dataset_id='measured', source_id='uploaded',
            access_level='PRIVATE', metric_columns=MAPPING)
        self.assertEqual(receipt['rows'], 48)
        r = vault.descriptive(ANALYST, dataset_id='measured',
            metrics=('cashflow', 'revenue'), as_of='2026-02-01T00:00:00Z')
        self.assertEqual(r['status'], 'DESCRIPTIVE_ONLY')
        self.assertEqual(r['insights'][0]['paired_n'], 24)
        self.assertFalse(vault.export_to_public(ANALYST, dataset_id='measured')['data_disclosed'])

    def test_extra_column_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_SQLITE_EXACT_COLUMNS_REQUIRED'):
            normalize_mapped_wide_sqlite(sample(rogue=True), table='measurements',
                dataset_id='measured', source_id='uploaded',
                access_level='PUBLIC', metric_columns=MAPPING)

    def test_implicit_numeric_type_denied(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_SQLITE_TEXT_CELLS_REQUIRED'):
            normalize_mapped_wide_sqlite(sample(bad_type=True), table='measurements',
                dataset_id='measured', source_id='uploaded',
                access_level='PUBLIC', metric_columns=MAPPING)

    def test_injected_table_identifier_denied(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_SQLITE_INPUT_OR_TABLE_DENIED'):
            normalize_mapped_wide_sqlite(sample(), table='measurements"; DROP TABLE',
                dataset_id='measured', source_id='uploaded',
                access_level='PUBLIC', metric_columns=MAPPING)

    def test_private_must_consent(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_SOURCE_OR_MAPPING_DENIED'):
            normalize_mapped_wide_sqlite(sample(), table='measurements',
                dataset_id='measured', source_id='uploaded',
                access_level='PRIVATE', metric_columns=MAPPING)


if __name__ == '__main__':
    unittest.main()
