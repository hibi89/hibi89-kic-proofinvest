"""Market Reality UI: localhost-only source-labeled input display."""
from __future__ import annotations

import json
import unittest

from proofinvest.market_reality_ui import render_local_market_reality
from test_market_reality import fixture


class Upload:
    def __init__(self, raw):
        self.raw = raw
        self.size = len(raw)
    def getvalue(self):
        return self.raw


class Mock:
    def __init__(self, raw=None):
        self.file = None if raw is None else Upload(raw)
        self.calls = []
    def file_uploader(self, *args, **kw):
        self.calls.append(("uploader", args, kw))
        return self.file
    def __getattr__(self, name):
        if name not in {"subheader", "caption", "warning", "info",
                        "table", "json", "error"}:
            raise AttributeError(name)
        return lambda *args, **kwargs: self.calls.append((name, args, kwargs))


class MarketRealityUITests(unittest.TestCase):
    def test_no_data_no_prediction(self):
        st = Mock()
        self.assertIsNone(render_local_market_reality(
            st, cik="0000000001", as_of="2025-10-16"))
        self.assertNotIn("table", [r[0] for r in st.calls])

    def test_valid_input_displays_real_ols_and_unverified_sources(self):
        raw = json.dumps(fixture()).encode()
        st = Mock(raw)
        self.assertEqual(render_local_market_reality(
            st, cik="0000000001", as_of="2025-10-16"), raw)
        names = [r[0] for r in st.calls]
        self.assertIn("table", names)
        self.assertIn("json", names)
        self.assertNotIn("error", names)
        self.assertIn("market_bubble_proven': False", str(st.calls))

    def test_cross_issuer_upload_blocked(self):
        st = Mock(json.dumps(fixture()).encode())
        self.assertIsNone(render_local_market_reality(
            st, cik="0000000002", as_of="2025-10-16"))
        self.assertIn("error", [r[0] for r in st.calls])
        self.assertNotIn("table", [r[0] for r in st.calls])


if __name__ == "__main__":
    unittest.main()
