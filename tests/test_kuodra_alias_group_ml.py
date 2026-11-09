"""Cross-issuer alias ML must not bypass source checks, embargo or HOLD."""
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
import json
import socket
import unittest
from unittest.mock import patch

from proofinvest.kuodra_alias_hybrid import analyze_owner_alias_group_ml
from proofinvest.kuodra_private_gateway import OwnerLocalGateway, VerifiedPrincipal

OWNER = VerifiedPrincipal('fictionalOwner', 'fictionalFund', ('owner',), True)
ANALYST = VerifiedPrincipal('fictionalAnalyst', 'fictionalFund', ('analyst',), True)
AS_OF = '2026-01-01T00:00:00Z'


def raw(zone):
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(('entity_id', 'metric_id', 'observation_at', 'available_at', 'value', 'unit'))
    for j in range(10):
        for i in range(62):
            t = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            ts = t.strftime('%Y-%m-%dT%H:%M:%SZ')
            if zone == 'PUBLIC':
                writer.writerow((f'publicEntity{j}', 'factor', ts, ts,
                                 str(round(i + j * 0.4, 3)), 'count'))
            else:
                writer.writerow((f'privateKey{j}', 'outcome', ts, ts,
                                 str(i * 3 + j * 2 + 4), 'usd'))
    return stream.getvalue().encode()


def fixture():
    vault = OwnerLocalGateway('fictionalFund')
    public = raw('PUBLIC')
    private = raw('PRIVATE')
    vault.ingest_csv(OWNER, raw=public, dataset_id='fictionalPublic',
                     source_id='fictionalCSV', access_level='PUBLIC')
    vault.ingest_csv(OWNER, raw=private, dataset_id='fictionalPrivate',
                     source_id='fictionalCSV', access_level='PRIVATE')
    arguments = {
        'public_dataset_id': 'fictionalPublic',
        'private_dataset_id': 'fictionalPrivate',
        'public_sha256': sha256(public).hexdigest(),
        'private_sha256': sha256(private).hexdigest(),
        'aliases': {f'publicEntity{j}': f'privateKey{j}' for j in range(10)},
        'as_of': AS_OF,
        'target_metric': 'private.outcome',
        'feature_metrics': ('public.factor',),
    }
    return vault, arguments


class AliasGroupTimeMLTest(unittest.TestCase):
    def test_true_backend_group_time_pipeline_with_operator_alias(self):
        vault, arguments = fixture()
        before = json.dumps(vault._datasets, sort_keys=True)
        packet = analyze_owner_alias_group_ml(vault, OWNER, **arguments)
        self.assertEqual(packet['decision'], 'HOLD')
        self.assertFalse(packet['cross_source_entity_link_verified'])
        self.assertFalse(packet['public_export_allowed'])
        self.assertFalse(packet['host_iam_verified'])
        self.assertFalse(packet['host_egress_verified'])
        self.assertEqual(packet['analysis']['status'],
                         'EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED')
        self.assertEqual(packet['analysis']['split'],
                         'DISJOINT_ISSUER_LATER_TIME_WITH_RELEASE_EMBARGO')
        self.assertFalse(packet['analysis']['production_ready'])
        self.assertIsNone(packet['analysis']['calibrated_probability'])
        self.assertEqual(before, json.dumps(vault._datasets, sort_keys=True))
        self.assertNotIn('privateKey', json.dumps(packet))
        self.assertNotIn('publicEntity', json.dumps(packet))
        self.assertNotIn('fictionalPublic', json.dumps(packet))

    def test_analyst_cannot_link_issuers(self):
        vault, arguments = fixture()
        with self.assertRaises(PermissionError):
            analyze_owner_alias_group_ml(vault, ANALYST, **arguments)

    def test_modified_sha_prevents_model_training(self):
        vault, arguments = fixture()
        arguments['public_sha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'ALIAS_SOURCE_RECEIPT_OR_SCOPE_INVALID'):
            analyze_owner_alias_group_ml(vault, OWNER, **arguments)

    def test_invalid_entity_map_prevents_model_training(self):
        vault, arguments = fixture()
        arguments['aliases']['publicEntity3'] = 'wrongCompany'
        with self.assertRaisesRegex(ValueError, 'ALIAS_SOURCE_ENTITY_MISSING'):
            analyze_owner_alias_group_ml(vault, OWNER, **arguments)

    def test_no_outbound_network_path(self):
        vault, arguments = fixture()
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('NETWORK')) as connect:
            packet = analyze_owner_alias_group_ml(vault, OWNER, **arguments)
            connect.assert_not_called()
        self.assertEqual(packet['network_requests'], 0)


if __name__ == '__main__':
    unittest.main()
