"""Offline tests: bounded source-bound KUODRA linked evidence session archive."""
import unittest

from proofinvest.linked_report_session_cache import (
    HISTORY_KEY, LATEST_KEY, MAX_BYTES, MAX_ENTRIES,
    clear_linked_reports, discard_linked_report, find_linked_report,
    keep_linked_report,
)


def fp(value):
    return format(value, "064x")


class LinkedReportSessionCacheTests(unittest.TestCase):
    def test_a_b_a_preserves_distinct_verified_json_bytes(self):
        state = {}
        self.assertTrue(keep_linked_report(state, fp(1), b'{"A":1}\n'))
        self.assertTrue(keep_linked_report(state, fp(2), b'{"B":2}\n'))
        self.assertEqual(find_linked_report(state, fp(1))["data"], b'{"A":1}\n')
        self.assertEqual(find_linked_report(state, fp(2))["data"], b'{"B":2}\n')
        self.assertEqual(state[LATEST_KEY]["fingerprint"], fp(2))
        self.assertEqual(set(state), {LATEST_KEY, HISTORY_KEY})

    def test_session_archive_is_bounded_to_sixteen_exact_inputs(self):
        state = {}
        for i in range(1, MAX_ENTRIES + 4):
            self.assertTrue(keep_linked_report(state, fp(i), b'{"status":"redacted"}\n'))
        self.assertEqual(len(state[HISTORY_KEY]), MAX_ENTRIES)
        self.assertIsNone(find_linked_report(state, fp(1)))
        self.assertIsNotNone(find_linked_report(state, fp(4)))
        self.assertEqual(state[LATEST_KEY]["fingerprint"], fp(MAX_ENTRIES + 3))

    def test_same_input_replaces_without_duplicates(self):
        state = {}
        self.assertTrue(keep_linked_report(state, fp(1), b'{"old":1}\n'))
        self.assertTrue(keep_linked_report(state, fp(1), b'{"new":2}\n'))
        self.assertEqual(len(state[HISTORY_KEY]), 1)
        self.assertEqual(find_linked_report(state, fp(1))["data"], b'{"new":2}\n')

    def test_corrupt_or_oversized_source_never_returned(self):
        state = {}
        self.assertFalse(keep_linked_report(state, "wrong", b'{}'))
        self.assertFalse(keep_linked_report(state, fp(1), b"x" * (MAX_BYTES + 1)))
        self.assertNotIn(HISTORY_KEY, state)
        state[HISTORY_KEY] = [{"fingerprint": fp(1), "data": b"{}"},
                              {"fingerprint": fp(1), "data": b"{}"}]
        self.assertIsNone(find_linked_report(state, fp(1)))
        self.assertNotIn(HISTORY_KEY, state)

    def test_only_exact_fingerprint_can_retrieve_report(self):
        state = {}
        self.assertTrue(keep_linked_report(state, fp(1), b'{"A":1}\n'))
        self.assertIsNone(find_linked_report(state, fp(2)))
        self.assertIsNone(find_linked_report(state, "bad"))
        self.assertIsNone(find_linked_report(None, fp(1)))

    def test_revoke_one_leaves_unrelated_inputs_and_rights_off_clears_all(self):
        state = {}
        self.assertTrue(keep_linked_report(state, fp(1), b'{"A":1}\n'))
        self.assertTrue(keep_linked_report(state, fp(2), b'{"B":2}\n'))
        discard_linked_report(state, fp(1))
        self.assertIsNone(find_linked_report(state, fp(1)))
        self.assertIsNotNone(find_linked_report(state, fp(2)))
        clear_linked_reports(state)
        self.assertNotIn(HISTORY_KEY, state)
        self.assertNotIn(LATEST_KEY, state)


if __name__ == "__main__":
    unittest.main()
