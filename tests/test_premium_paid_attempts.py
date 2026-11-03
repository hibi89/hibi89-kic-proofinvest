"""Offline deterministic checks for bounded, privacy-safe premium call history."""
import unittest

from proofinvest.premium_paid_attempts import (
    _HISTORY_KEY, _MAX_HISTORY, register_premium_pair_attempt,
)


def fp(i):
    return format(i, "064x")


class PremiumPaidAttemptTests(unittest.TestCase):
    def test_a_b_a_b_does_not_rebill_within_session(self):
        state = {}
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "NEW")
        self.assertEqual(register_premium_pair_attempt(state, fp(2)), "NEW")
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "DUPLICATE")
        self.assertEqual(register_premium_pair_attempt(state, fp(2)), "DUPLICATE")
        self.assertEqual(state[_HISTORY_KEY], [fp(1), fp(2)])
        self.assertEqual(set(state), {_HISTORY_KEY, "kuodra_p141_pair_attempt"})

    def test_malformed_history_fails_closed(self):
        for history in ("not-a-list", ["bad"], [fp(1), fp(1)], [fp(i) for i in range(65)]):
            state = {_HISTORY_KEY: history}
            self.assertEqual(register_premium_pair_attempt(state, fp(77)), "INVALID")
            self.assertNotIn("kuodra_p141_pair_attempt", state)
        self.assertEqual(register_premium_pair_attempt({}, "not-a-hash"), "INVALID")

    def test_legacy_marker_still_blocks_exact_repeat(self):
        state = {"kuodra_p141_pair_attempt": fp(4)}
        self.assertEqual(register_premium_pair_attempt(state, fp(4)), "DUPLICATE")
        self.assertEqual(register_premium_pair_attempt(state, fp(5)), "NEW")
        self.assertEqual(register_premium_pair_attempt(state, fp(5)), "DUPLICATE")

    def test_preupgrade_a_then_b_then_a_does_not_rebill(self):
        # P154 wrote only the last attempt. P157 migration must preserve it
        # before a different B is recorded in the P155 bounded ledger.
        state = {"kuodra_p141_pair_attempt": fp(1)}
        self.assertEqual(register_premium_pair_attempt(state, fp(2)), "NEW")
        self.assertEqual(state[_HISTORY_KEY], [fp(1), fp(2)])
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "DUPLICATE")
        self.assertEqual(register_premium_pair_attempt(state, fp(2)), "DUPLICATE")
        self.assertEqual(state[_HISTORY_KEY], [fp(1), fp(2)])

    def test_legacy_marker_migrates_even_on_duplicate_first_click(self):
        state = {"kuodra_p141_pair_attempt": fp(1)}
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "DUPLICATE")
        self.assertEqual(state[_HISTORY_KEY], [fp(1)])
        self.assertEqual(register_premium_pair_attempt(state, fp(2)), "NEW")
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "DUPLICATE")

    def test_corrupt_legacy_fails_closed_before_new_paid_call(self):
        for legacy in ("bad", "", True, 4, ["x"]):
            state = {"kuodra_p141_pair_attempt": legacy}
            self.assertEqual(register_premium_pair_attempt(state, fp(2)), "INVALID")
            self.assertNotIn(_HISTORY_KEY, state)

    def test_bounded_history_and_session_limit(self):
        state = {}
        for i in range(1, 68):
            self.assertEqual(register_premium_pair_attempt(state, fp(i)), "NEW")
        self.assertEqual(len(state[_HISTORY_KEY]), _MAX_HISTORY)
        self.assertEqual(state[_HISTORY_KEY][0], fp(4))
        self.assertEqual(register_premium_pair_attempt(state, fp(4)), "DUPLICATE")
        # Old entries may be retried after 64 different explicitly clicked
        # input sets; this is a bounded-memory contract, not a billing DB.
        self.assertEqual(register_premium_pair_attempt(state, fp(1)), "NEW")

    def test_missing_session_state_keeps_existing_mock_behavior(self):
        self.assertEqual(register_premium_pair_attempt(None, fp(8)), "NEW")


if __name__ == "__main__":
    unittest.main()
