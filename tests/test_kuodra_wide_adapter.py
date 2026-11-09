"""Synthetic wide CSV mapping, ACL, source lineage and release-time gates."""
import csv
from hashlib import sha256
from io import StringIO
import unittest

from proofinvest.kuodra_wide_adapter import normalize_mapped_wide_csv
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

FIELDS = {'closeUSD': ('close', 'usd'), 'salesUSD': ('sales', 'usd')}
OWNER = VerifiedPrincipal('ownerDemo', 'fundDemo', ('owner',), True)
ANALYST = VerifiedPrincipal('analystDemo', 'fundDemo', ('analyst',), True)
WRONG = VerifiedPrincipal('analystWrong', 'otherFund', ('analyst',), True)


def make_wide(*, rows=24, late=False, formula=False, duplicate=False, extra=False):
    output = StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    header = ('available_at', 'salesUSD', 'entity_id', 'observation_at', 'closeUSD')
    writer.writerow(header + (('rogueColumn',) if extra else ()))
    for day in range(1, rows + 1):
        when = f'2026-01-{day:02d}T00:00:00Z'
        available = '2026-02-15T00:00:00Z' if late else when
        row = (available, str(day*2), 'issuerLocal', when,
               '=1+1' if formula and day == 1 else str(day))
        writer.writerow(row + (('unexpected',) if extra else ()))
    if duplicate:
        writer.writerow((when, '2', 'issuerLocal', when, '1'))
    return output.getvalue().encode('utf-8')


class WideCanonicalTest(unittest.TestCase):
    def _normalize(self, raw, **kwargs):
        return normalize_mapped_wide_csv(raw, dataset_id='mapped', source_id='operator',
                                         access_level='PRIVATE', consent=True,
                                         metric_columns=FIELDS, **kwargs)

    def test_normalizes_both_zones_and_keeps_original_hash(self):
        raw = make_wide()
        a = normalize_mapped_wide_csv(raw, dataset_id='pub', source_id='source',
                access_level='PUBLIC', metric_columns=FIELDS)
        b = self._normalize(raw)
        self.assertEqual(a['rows'], b['rows'])
        self.assertEqual(a['rows'], 48)
        self.assertEqual(b['source_sha256'], sha256(raw).hexdigest())
        self.assertNotEqual(b['source_sha256'], b['normalized_csv_sha256'])
        self.assertEqual(a['mapping_sha256'], b['mapping_sha256'])
        self.assertTrue(all(row['evidence_sha256'] == b['source_sha256'] and
                    row['mapping_sha256'] == b['mapping_sha256'] for row in b['records']))
        self.assertFalse(b['source_authenticated'])
        self.assertFalse(b['inferred_units'])
        self.assertFalse(b['issuer_identity_authenticated'])

    def test_gateway_owner_ingests_and_analyst_reads_descriptive(self):
        vault = OwnerLocalGateway('fundDemo')
        raw = make_wide()
        receipt = vault.ingest_mapped_wide_csv(OWNER, raw=raw, dataset_id='mapped',
             source_id='operator', access_level='PRIVATE', metric_columns=FIELDS)
        self.assertEqual(receipt['rows'], 48)
        answer = vault.descriptive(ANALYST, dataset_id='mapped',
                 metrics=('sales', 'close'), as_of='2026-02-01T00:00:00Z')
        self.assertEqual(answer['status'], 'DESCRIPTIVE_ONLY')
        self.assertEqual(answer['insights'][0]['paired_n'], 24)
        self.assertEqual(answer['guard'], 'HOLD')
        self.assertEqual(vault.export_to_public(ANALYST, dataset_id='mapped')['data_disclosed'], False)
        with self.assertRaises(PermissionError):
            vault.descriptive(WRONG, dataset_id='mapped', metrics=('sales', 'close'),
                              as_of='2026-02-01T00:00:00Z')

    def test_late_release_is_not_backfilled(self):
        vault = OwnerLocalGateway('fundDemo')
        vault.ingest_mapped_wide_csv(OWNER, raw=make_wide(late=True),
             dataset_id='mapped', source_id='operator', access_level='PRIVATE',
             metric_columns=FIELDS)
        answer = vault.descriptive(ANALYST, dataset_id='mapped',
                 metrics=('sales', 'close'), as_of='2026-02-01T00:00:00Z')
        self.assertEqual(answer['status'], 'INSUFFICIENT_EVIDENCE')

    def test_rejects_undeclared_extra_column(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_CSV_EXACT_HEADER_REQUIRED'):
            self._normalize(make_wide(extra=True))

    def test_rejects_formula_injection(self):
        with self.assertRaisesRegex(ValueError, 'CANONICAL_VALUE_INVALID'):
            self._normalize(make_wide(formula=True))

    def test_duplicate_time_metric_fails(self):
        with self.assertRaisesRegex(ValueError, 'CANONICAL_DUPLICATE'):
            self._normalize(make_wide(duplicate=True))

    def test_unknown_metric_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_METRIC_MAPPING_INVALID'):
            normalize_mapped_wide_csv(make_wide(), dataset_id='mapped',
                source_id='operator', access_level='PUBLIC',
                metric_columns={'salesUSD': ('same', 'usd'),
                                'closeUSD': ('same', 'usd')})

    def test_private_requires_consent(self):
        with self.assertRaisesRegex(ValueError, 'WIDE_SOURCE_OR_MAPPING_DENIED'):
            normalize_mapped_wide_csv(make_wide(), dataset_id='mapped',
                source_id='operator', access_level='PRIVATE',
                metric_columns=FIELDS)

    def test_zero_metric_rows_rejected(self):
        raw = b'entity_id,observation_at,available_at,salesUSD,closeUSD\nissuerLocal,2026-01-01T00:00:00Z,2026-01-01T00:00:00Z,,\n'
        with self.assertRaisesRegex(ValueError, 'WIDE_NO_NUMERIC_METRICS'):
            self._normalize(raw)


if __name__ == '__main__':
    unittest.main()
