"""Fictional-only wide public/private alias+group ML integration acceptance."""
import json
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

from proofinvest.kuodra_wide_alias_synthetic_demo import run_synthetic_wide_alias_ml_demo


class SyntheticWideAliasMLTest(unittest.TestCase):
    def test_fictional_wide_sources_really_join_through_group_time_ml(self):
        result = run_synthetic_wide_alias_ml_demo()
        self.assertEqual(result['public_canonical_rows'], 620)
        self.assertEqual(result['private_canonical_rows'], 620)
        self.assertEqual(result['analysis']['status'],
                         'EXPLORATORY_GROUP_TIME_HOLDOUT_MEASURED')
        self.assertEqual(result['analysis']['split'],
                         'DISJOINT_ISSUER_LATER_TIME_WITH_RELEASE_EMBARGO')
        self.assertFalse(result['analysis']['production_ready'])
        self.assertFalse(result['cross_source_entity_link_verified'])
        self.assertFalse(result['institution_host_iam_verified'])
        self.assertFalse(result['source_rights_verified'])
        self.assertFalse(result['public_export_allowed'])
        self.assertEqual(result['decision'], 'HOLD')
        self.assertEqual(len(result['mapping_sha256']), 64)
        self.assertEqual(len(result['source_hashes']), 2)
        self.assertEqual(result['external_api_requests'], 0)
        self.assertIsNone(result['calibrated_probability'])
        self.assertNotIn('fictionalPrivate', json.dumps(result))

    def test_mocked_socket_denies_network(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('UNEXPECTED_NETWORK')) as network:
            result = run_synthetic_wide_alias_ml_demo()
            network.assert_not_called()
        self.assertFalse(result['production_ready'])

    def test_real_cli_renders_safe_json_only(self):
        process = subprocess.run([sys.executable, '-B', '-m',
            'proofinvest.kuodra_wide_alias_synthetic_demo'],
            capture_output=True, text=True, check=True, timeout=60)
        packet = json.loads(process.stdout)
        self.assertTrue(packet['synthetic_only'])
        self.assertEqual(packet['decision'], 'HOLD')
        for token in ('syntheticFund', 'fictionalPublic0', 'fictionalPrivate0',
                      'syntheticOwner', 'syntheticCSV'):
            self.assertNotIn(token, process.stdout)


if __name__ == '__main__':
    unittest.main()
