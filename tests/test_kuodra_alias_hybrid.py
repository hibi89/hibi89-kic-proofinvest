"""Cross-source aliasing must require owner mapping, verified digests and HOLD."""
from hashlib import sha256
from io import StringIO
import csv
import json
import socket
import unittest
from unittest.mock import patch

from proofinvest.kuodra_alias_hybrid import analyze_owner_alias_hybrid
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER = VerifiedPrincipal('ownerLocal', 'ownerFund', ('owner',), True)
ANALYST = VerifiedPrincipal('analystLocal', 'ownerFund', ('analyst',), True)
WHEN = '2026-01-01T00:00:00Z'
AS_OF = '2026-02-01T00:00:00Z'


def csv_source(prefix, metric):
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(('entity_id', 'metric_id', 'observation_at', 'available_at', 'value', 'unit'))
    for i in range(1, 46):
        writer.writerow((f'{prefix}{i}', metric, WHEN, WHEN,
                         str(i if metric == 'revenue' else i * 3 + 2), 'usd'))
    return stream.getvalue().encode()


def fixture():
    vault = OwnerLocalGateway('ownerFund')
    public = csv_source('publicIssuer', 'revenue')
    private = csv_source('internalKey', 'cost')
    vault.ingest_csv(OWNER, raw=public, dataset_id='publicData',
                     source_id='publicSource', access_level='PUBLIC')
    vault.ingest_csv(OWNER, raw=private, dataset_id='privateData',
                     source_id='privateSource', access_level='PRIVATE')
    args = dict(public_dataset_id='publicData', private_dataset_id='privateData',
                public_sha256=sha256(public).hexdigest(),
                private_sha256=sha256(private).hexdigest(),
                aliases={f'publicIssuer{i}': f'internalKey{i}' for i in range(1, 46)},
                as_of=AS_OF, observation_at=WHEN,
                metrics=('public.revenue', 'private.cost'))
    return vault, args


class AliasHybridTest(unittest.TestCase):
    def test_source_bound_alias_enables_local_fdr_only(self):
        vault, args = fixture()
        before = json.dumps(vault._datasets, sort_keys=True)
        r = analyze_owner_alias_hybrid(vault, OWNER, **args)
        self.assertEqual(r['status'], 'OWNER_LOCAL_EXPLORATION_ONLY')
        self.assertEqual(r['decision'], 'HOLD')
        self.assertFalse(r['cross_source_entity_link_verified'])
        self.assertFalse(r['public_export_allowed'])
        self.assertFalse(r['source_rights_verified'])
        self.assertEqual(r['joined_entity_times'], 45)
        self.assertEqual(r['alias_count'], 45)
        self.assertEqual(len(r['mapping_sha256']), 64)
        self.assertEqual(r['analysis']['status'], 'EXPLORATORY_INDEPENDENCE_UNVERIFIED')
        self.assertEqual(before, json.dumps(vault._datasets, sort_keys=True))
        self.assertNotIn('publicIssuer1', json.dumps(r))
        self.assertNotIn('internalKey1', json.dumps(r))

    def test_non_owner_cannot_create_links(self):
        vault, args = fixture()
        with self.assertRaises(PermissionError):
            analyze_owner_alias_hybrid(vault, ANALYST, **args)

    def test_stale_source_sha_rejected(self):
        vault, args = fixture()
        args['public_sha256'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'ALIAS_SOURCE_RECEIPT_OR_SCOPE_INVALID'):
            analyze_owner_alias_hybrid(vault, OWNER, **args)

    def test_missing_mapping_target_rejected(self):
        vault, args = fixture()
        args['aliases']['publicIssuer1'] = 'notActuallyInPrivate'
        with self.assertRaisesRegex(ValueError, 'ALIAS_SOURCE_ENTITY_MISSING'):
            analyze_owner_alias_hybrid(vault, OWNER, **args)

    def test_noninjective_aliases_rejected(self):
        vault, args = fixture()
        args['aliases']['publicIssuer1'] = args['aliases']['publicIssuer2']
        with self.assertRaisesRegex(ValueError, 'ALIAS_MAPPING_CONTRACT_INVALID'):
            analyze_owner_alias_hybrid(vault, OWNER, **args)

    def test_no_network(self):
        vault, args = fixture()
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK')) as connect:
            r = analyze_owner_alias_hybrid(vault, OWNER, **args)
            connect.assert_not_called()
        self.assertEqual(r['network_requests'], 0)


if __name__ == '__main__':
    unittest.main()
