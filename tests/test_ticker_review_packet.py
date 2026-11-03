"""P159 offline reviewer packet: A/B/C source evidence + explanation + Guard."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from proofinvest.ticker_review_packet import (
    build_review_packet, review_packet_json_bytes, inspect_review_packet_bytes,
)
from tests.test_ticker_market_pair_evidence import _build, _prepared


def rehash(packet):
    unsigned = {k: v for k, v in packet.items() if k != "packet_sha256"}
    raw = (json.dumps(unsigned, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False) + "\n").encode()
    packet["packet_sha256"] = sha256(raw).hexdigest()


class ReviewPacketTests(unittest.TestCase):
    def test_real_replayed_a_b_c_report_can_be_checked_offline(self):
        linked = _build(_prepared())
        self.assertEqual(linked["status"],
                         "LOCAL_AND_MARKET_MATH_REPLAYED_UNVERIFIED")
        packet = build_review_packet(linked)
        raw = review_packet_json_bytes(packet)
        check = inspect_review_packet_bytes(raw)
        self.assertEqual(check["status"],
                         "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED")
        self.assertEqual(check["linked_evidence_sha256"],
                         linked["evidence_sha256"])
        self.assertEqual(packet["explanation"]["linked_evidence_sha256"],
                         linked["evidence_sha256"])
        self.assertEqual([finding["engine"] for finding in
                          packet["explanation"]["findings"]], ["A", "B", "C"])
        self.assertEqual(packet["guard_policy_preview"], "HOLD")
        self.assertIs(packet["source_authenticated"], False)
        self.assertIs(packet["source_rights_verified"], False)
        self.assertIs(packet["ai_agent_executed"], False)
        self.assertIs(packet["trade_executed"], False)
        self.assertLessEqual(len(raw), 28672)
        self.assertNotIn(b"close_observations", raw)
        self.assertNotIn(b"apikey", raw.lower())
        self.assertNotIn(b"<html", raw.lower())

    def test_modified_source_receipt_cannot_be_hidden_by_new_packet_hash(self):
        packet = build_review_packet(_build(_prepared()))
        changed = deepcopy(packet)
        changed["linked_evidence"]["premium_engine_a"]["beta"] = "99"
        rehash(changed)
        with self.assertRaises(ValueError):
            review_packet_json_bytes(changed)

    def test_modified_explanation_cannot_be_hidden_by_new_packet_hash(self):
        packet = build_review_packet(_build(_prepared()))
        changed = deepcopy(packet)
        changed["explanation"]["findings"][0]["simple_return_gap_pp"] = "9999"
        rehash(changed)
        with self.assertRaisesRegex(ValueError, "LINK"):
            review_packet_json_bytes(changed)

    def test_fake_approval_or_extra_secret_cannot_be_exported(self):
        original = build_review_packet(_build(_prepared()))
        for key in ("source_rights_verified", "external_sharing_allowed",
                    "ai_agent_executed", "trade_executed"):
            changed = deepcopy(original)
            changed[key] = True
            rehash(changed)
            with self.subTest(field=key), self.assertRaisesRegex(
                    ValueError, "CONTRACT"):
                review_packet_json_bytes(changed)
        changed = deepcopy(original)
        changed["raw_vendor_body"] = "<SECRET>"
        rehash(changed)
        with self.assertRaisesRegex(ValueError, "CONTRACT"):
            review_packet_json_bytes(changed)

    def test_exact_canonical_json_and_duplicate_keys_required(self):
        raw = review_packet_json_bytes(build_review_packet(_build(_prepared())))
        self.assertEqual(inspect_review_packet_bytes(raw)["guard_policy_preview"], "HOLD")
        with self.assertRaisesRegex(ValueError, "NONCANONICAL"):
            inspect_review_packet_bytes(raw + b" ")
        duplicate = raw.replace(
            b'"ai_agent_executed":false,',
            b'"ai_agent_executed":false,"ai_agent_executed":true,', 1)
        self.assertNotEqual(raw, duplicate)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            inspect_review_packet_bytes(duplicate)
        with self.assertRaises(ValueError):
            inspect_review_packet_bytes(b"x" * 28673)
        with self.assertRaises(ValueError):
            inspect_review_packet_bytes(None)

    def test_modified_packet_checksum_refused(self):
        raw = review_packet_json_bytes(build_review_packet(_build(_prepared())))
        changed = bytearray(raw)
        index = changed.index(b'LOCAL_REPLAYED_REVIEW_ONLY_UNVERIFIED')
        changed[index:index + 5] = b'OTHER'
        with self.assertRaises(ValueError):
            inspect_review_packet_bytes(bytes(changed))


if __name__ == "__main__":
    unittest.main()
