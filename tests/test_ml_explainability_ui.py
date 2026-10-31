"""Stubbed local Streamlit checks: explainable ML review never calls a provider."""
import json
import unittest

from proofinvest.ml_explainability_ui import render_local_ml_evaluation
from test_ml_explainability import example


class Upload:
    def __init__(self, raw):
        self.raw = raw
        self.size = len(raw)
    def getvalue(self):
        return self.raw


class St:
    def __init__(self, raw=None):
        self.raw = raw
        self.lines = []
    def file_uploader(self, *a, **kw):
        self.lines.append("file_uploader")
        return None if self.raw is None else Upload(self.raw)
    def __getattr__(self, name):
        if name not in ("subheader", "caption", "warning", "write", "json", "table", "error"):
            raise AttributeError(name)
        return lambda *args, **kwargs: self.lines.append((name, args))


class MlExplanationUITests(unittest.TestCase):
    def test_empty_does_not_invent_model(self):
        st = St()
        render_local_ml_evaluation(st, cik="0000320193", as_of="2026-10-31")
        self.assertIn("file_uploader", st.lines)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "json" for x in st.lines))

    def test_evaluated_displays_model_sources_and_not_authenticated(self):
        st = St(json.dumps(example()).encode())
        render_local_ml_evaluation(st, cik="0000320193", as_of="2026-10-31")
        self.assertIn("table", [x[0] for x in st.lines if isinstance(x, tuple)])
        self.assertIn("warning", [x[0] for x in st.lines if isinstance(x, tuple)])
        self.assertNotIn("error", [x[0] for x in st.lines if isinstance(x, tuple)])
        rendered = str(st.lines)
        self.assertIn("source_authenticated': False", rendered)
        self.assertIn("https://www.sec.gov", rendered)

    def test_issuer_mismatch_blocked_before_display(self):
        st = St(json.dumps(example()).encode())
        render_local_ml_evaluation(st, cik="0000000001", as_of="2026-10-31")
        self.assertIn("error", [x[0] for x in st.lines if isinstance(x, tuple)])
        self.assertNotIn("table", [x[0] for x in st.lines if isinstance(x, tuple)])


if __name__ == "__main__":
    unittest.main()
