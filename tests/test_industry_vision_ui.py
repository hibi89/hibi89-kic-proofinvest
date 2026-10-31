"""Industry Vision UI: local-only Streamlit-like stub (no network or model)."""
import json
import unittest

from proofinvest.industry_vision_ui import render_local_industry_vision
from test_industry_vision import fixture


class Upload:
    def __init__(self, value):
        self.raw = value
        self.size = len(value)
    def getvalue(self):
        return self.raw


class MockUI:
    def __init__(self, raw=None):
        self.upload = None if raw is None else Upload(raw)
        self.calls = []
    def file_uploader(self, *args, **kwargs):
        self.calls.append(("file_uploader", kwargs))
        return self.upload
    def __getattr__(self, key):
        if key not in {"subheader", "caption", "info", "warning",
                       "write", "table", "json", "error"}:
            raise AttributeError(key)
        return lambda *args, **kwargs: self.calls.append((key, args))


class IndustryVisionUITests(unittest.TestCase):
    def test_no_data_has_no_fictional_vision(self):
        st = MockUI()
        render_local_industry_vision(st, cik="0000320193", as_of="2026-10-31")
        names = [x[0] for x in st.calls]
        self.assertIn("info", names)
        self.assertNotIn("table", names)

    def test_synthetic_comparison_has_sources_and_caveat(self):
        st = MockUI(json.dumps(fixture()).encode())
        render_local_industry_vision(st, cik="0000320193", as_of="2026-10-31")
        names = [x[0] for x in st.calls]
        self.assertIn("warning", names)
        self.assertIn("table", names)
        self.assertNotIn("error", names)
        self.assertIn("industry_outlook_verified': False", str(st.calls))
        self.assertIn("www.bea.gov", str(st.calls))

    def test_mismatched_filing_issuer_blocks_view(self):
        st = MockUI(json.dumps(fixture()).encode())
        render_local_industry_vision(st, cik="0000000001", as_of="2026-10-31")
        names = [x[0] for x in st.calls]
        self.assertIn("error", names)
        self.assertNotIn("table", names)


if __name__ == "__main__":
    unittest.main()
