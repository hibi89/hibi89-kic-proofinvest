"""P194 Streamlit actual AppTest reference view and trust rejection."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

_APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
_MODE = "KUODRA · Apple FY2026 실제 공시 수치 검산 (원본 미인증)"


class PublicThreeIssuerStreamlitTests(unittest.TestCase):
    def test_apple_real_fy_reference_panel_actionable_in_streamlit(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(_APP)).run(timeout=20)
        at.selectbox[0].set_value(_MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("공개 실적 참고 비교" in s.value
                            for s in at.subheader))
        self.assertTrue(any("회계연도 종료일" in w.value
                            for w in at.warning))
        self.assertTrue(any("MSFT" in m.value for m in at.markdown))
        self.assertTrue(any("DELL" in m.value for m in at.markdown))
        self.assertGreaterEqual(len(at.dataframe), 2)
        self.assertFalse(at.error)

    def test_untrusted_peer_data_hides_reference_rows(self):
        from streamlit.testing.v1 import AppTest
        from proofinvest import apple_public_peer_reality as peer
        at = AppTest.from_file(str(_APP)).run(timeout=20)
        with patch.object(peer, "review_public_fiscal_peers",
                          return_value={"status": "BLOCKED"}):
            at.selectbox[0].set_value(_MODE).run(timeout=20)
        self.assertFalse(at.exception, [str(x.message) for x in at.exception])
        self.assertTrue(any("기간 계약" in e.value for e in at.error))
        self.assertFalse(any("MSFT" in m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()
