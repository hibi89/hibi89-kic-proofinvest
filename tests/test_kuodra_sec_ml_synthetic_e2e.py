"""Real local SEC and ML call-chain acceptance with fictional input only."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

from proofinvest.kuodra_sec_ml_synthetic_e2e import run_synthetic_sec_ml_e2e


class SyntheticSecMlEndToEnd(unittest.TestCase):
    def test_original_sec_guard_with_private_ml_preserves_reject(self):
        report = run_synthetic_sec_ml_e2e()
        self.assertTrue(report['synthetic_only'])
        self.assertEqual([case['decision'] for case in report['cases']],
                         ['HOLD', 'REJECT'])
        self.assertEqual([case['sec_numeric_status'] for case in report['cases']],
                         ['calculated_unverified', 'conflict'])
        self.assertTrue(all(case['local_sqlite_audit_valid'] and
                            case['local_source_pins_matched'] for case in report['cases']))
        self.assertTrue(all(len(case['bridge_receipt_sha256']) == 64
                            for case in report['cases']))
        self.assertFalse(report['independent_issuer_link_verified'])
        self.assertFalse(report['public_export_allowed'])
        self.assertFalse(report['real_data_rights_verified'])
        self.assertFalse(report['institution_host_iam_verified'])
        self.assertFalse(report['production_ready'])
        self.assertEqual(report['live_sec_requests'], 0)
        self.assertNotIn('fictionalLocalML', json.dumps(report))

    def test_all_paths_offline(self):
        with patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('UNEXPECTED_NETWORK')) as connect:
            report = run_synthetic_sec_ml_e2e()
            connect.assert_not_called()
        self.assertEqual(report['cases'][1]['decision'], 'REJECT')

    def test_cli_result_reproducible_and_redacted(self):
        process = subprocess.run([sys.executable, '-B', '-m',
             'proofinvest.kuodra_sec_ml_synthetic_e2e'],
             capture_output=True, text=True, timeout=60, check=True)
        result = json.loads(process.stdout)
        self.assertEqual(len(result['cases']), 2)
        self.assertNotIn('fictionalMLSource', process.stdout)
        self.assertEqual(result['cases'][0]['decision'], 'HOLD')
        self.assertEqual(result['cases'][1]['decision'], 'REJECT')


if __name__ == '__main__':
    unittest.main()
