"""Local-only Streamlit peer original upload, bounded fail-closed gate."""
from __future__ import annotations

from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from proofinvest.kuodra_local_workspace_ui import (
    _render_peer_companyfacts_inputs, _verify_uploaded_peers,
)
from tests.test_industry_peer_companyfacts import peer_input, PEER_ACCESSION, PEER_CIK


class Upload:
    def __init__(self, raw: bytes, reported_size=None):
        self.raw = raw
        self.size = len(raw) if reported_size is None else reported_size
    def getvalue(self):
        return self.raw


class Stub:
    def __init__(self, enabled, uploaded=None, accession=PEER_ACCESSION):
        self.enabled = enabled
        self.uploaded = uploaded
        self.accession = accession
        self.log = []
    def checkbox(self, label, **kwargs):
        self.log.append(("checkbox", label))
        return self.enabled
    def file_uploader(self, label, **kwargs):
        self.log.append(("file_uploader", label))
        return self.uploaded
    def text_input(self, label, **kwargs):
        self.log.append(("text_input", label))
        return self.accession
    def caption(self, *args):
        self.log.append(("caption", args))
    def warning(self, *args):
        self.log.append(("warning", args))
    def error(self, *args):
        self.log.append(("error", args))


class PeerOriginalUITests(unittest.TestCase):
    def test_no_upload_controls_or_byte_reads_without_opt_in(self):
        data, raw = peer_input()
        view = Stub(False, Upload(raw))
        enabled, inputs = _render_peer_companyfacts_inputs(
            view, json.dumps(data).encode())
        self.assertFalse(enabled)
        self.assertEqual(inputs, [])
        self.assertNotIn("file_uploader", [x[0] for x in view.log])

    def test_explicit_opt_in_with_bounded_peer_original(self):
        data, raw = peer_input()
        initial_sha = sha256(raw).hexdigest()
        view = Stub(True, Upload(raw))
        enabled, inputs = _render_peer_companyfacts_inputs(
            view, json.dumps(data).encode())
        self.assertTrue(enabled)
        self.assertEqual(inputs[0][0], PEER_CIK)
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("NO_EXTERNAL_HTTP")) as network:
            receipt = _verify_uploaded_peers(json.dumps(data).encode(), inputs)
        network.assert_not_called()
        self.assertEqual(receipt["peer_count"], 1)
        self.assertEqual(receipt["peer_records"][0]["companyfacts_sha256"], initial_sha)
        self.assertEqual(sha256(raw).hexdigest(), initial_sha)
        self.assertFalse(receipt["source_authenticated"])
        self.assertFalse(receipt["audit_written"])

    def test_missing_or_tampered_peer_source_cannot_be_accepted(self):
        data, raw = peer_input()
        for uploaded, accession in (
            (None, PEER_ACCESSION),
            (Upload(raw, reported_size=len(raw) + 1), PEER_ACCESSION),
            (Upload(raw), "0000000007-26-999999"),
        ):
            view = Stub(True, uploaded, accession)
            _, inputs = _render_peer_companyfacts_inputs(
                view, json.dumps(data).encode())
            with self.subTest(uploaded=uploaded is not None,
                              accession=accession), self.assertRaises(ValueError):
                _verify_uploaded_peers(json.dumps(data).encode(), inputs)

    def test_oversized_or_malformed_file_never_read_past_size_check(self):
        data, raw = peer_input()
        class FakeOversized:
            size = 24_000_001
            def getvalue(self):
                raise AssertionError("SHOULD_NEVER_READ")
        with self.assertRaisesRegex(ValueError, "PEER_UI_ORIGINAL_SIZE_INVALID"):
            _verify_uploaded_peers(json.dumps(data).encode(),
                                   [(PEER_CIK, PEER_ACCESSION, FakeOversized())])
        with self.assertRaisesRegex(ValueError, "PEER_UI_COMPLETE_INPUTS_REQUIRED"):
            _verify_uploaded_peers(json.dumps(data).encode(), [])


if __name__ == "__main__":
    unittest.main()
