"""P140 Streamlit-like provider UI click gates, offline only."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from proofinvest import market_provider_alpha_vantage as av
from tests.test_market_provider_alpha_vantage import fixture, GATES, KEY


class FakeUI:
    def __init__(self, *, click=False, check=False):
        self.click, self.check = click, check
        self.events = []
    def subheader(self, x): self.events.append(("subheader", x))
    def caption(self, x): self.events.append(("caption", x))
    def warning(self, x): self.events.append(("warning", x))
    def checkbox(self, *_args, **_kwargs): return self.check
    def button(self, label, **kwargs):
        self.events.append(("button", {"label": label, "disabled": kwargs.get("disabled")}))
        return self.click and not kwargs.get("disabled")
    def metric(self, *args): self.events.append(("metric", args))
    def json(self, x): self.events.append(("json", x))
    def code(self, x, **_kwargs): self.events.append(("code", x))


class DailyPricePanelTests(unittest.TestCase):
    def test_default_disabled_never_fetches(self):
        ui = FakeUI(click=True, check=True)
        with patch.dict(os.environ, {}, clear=True), patch.object(
                av, "fetch_daily_close", side_effect=AssertionError("HTTP")) as fetch:
            av.render_daily_price_panel(ui, ticker="AAPL", as_of="2026-11-03", ticker_valid=True)
        fetch.assert_not_called()
        self.assertTrue(ui.events[-1][1]["disabled"])

    def test_ack_or_invalid_ticker_prevents_fetch(self):
        for ticker_valid, checked in ((True, False), (False, True)):
            ui = FakeUI(click=True, check=checked)
            with patch.dict(os.environ, {**GATES, "KUODRA_ALPHA_VANTAGE_API_KEY": KEY}), patch.object(
                    av, "fetch_daily_close", side_effect=AssertionError("HTTP")) as fetch:
                av.render_daily_price_panel(ui, ticker="AAPL", as_of="2026-11-03",
                                            ticker_valid=ticker_valid)
            fetch.assert_not_called()

    def test_approved_click_displays_bounded_price_only(self):
        ui = FakeUI(click=True, check=True)
        mocked = av.parse_daily_close_bytes(fixture(), ticker="AAPL", as_of="2026-11-03")
        with patch.dict(os.environ, {**GATES, "KUODRA_ALPHA_VANTAGE_API_KEY": KEY}), patch.object(
                av, "fetch_daily_close", return_value=mocked) as fetch:
            av.render_daily_price_panel(ui, ticker="AAPL", as_of="2026-11-03", ticker_valid=True)
        fetch.assert_called_once()
        self.assertEqual([k for k, _ in ui.events].count("metric"), 1)
        overview = next(v for k, v in ui.events if k == "json")
        self.assertFalse(overview["full_a_b_c_ready"])
        self.assertNotIn(KEY, repr(ui.events))
        self.assertFalse(any(k == "code" for k, _ in ui.events))

    def test_provider_error_shows_no_metrics(self):
        ui = FakeUI(click=True, check=True)
        with patch.dict(os.environ, {**GATES, "KUODRA_ALPHA_VANTAGE_API_KEY": KEY}), patch.object(
                av, "fetch_daily_close", return_value=av._hold("PROVIDER_NOTICE_OR_LIMIT")) as fetch:
            av.render_daily_price_panel(ui, ticker="AAPL", as_of="2026-11-03", ticker_valid=True)
        fetch.assert_called_once()
        self.assertFalse(any(k == "metric" for k, _ in ui.events))
        self.assertTrue(any(k == "code" for k, _ in ui.events))


if __name__ == "__main__":
    unittest.main()
