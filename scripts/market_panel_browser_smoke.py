"""P270: actual Chromium 4 synthetic JSON uploads -> shared NDX -> Guard export."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from proofinvest.market_panel_review import verify_local_market_panel
from tests.test_market_panel_offline import raw

ROOT = Path(__file__).resolve().parents[1]
PORT = 8594
URL = "http://127.0.0.1:" + str(PORT)
MODE = "KUODRA · 미국 3~5종목 + I:NDX Engine A (로컬)"


def main() -> None:
    from playwright.sync_api import expect, sync_playwright

    symbols = ["NVDA", "AAPL", "MSFT"]
    sources = {ticker: raw(ticker) for ticker in ["I:NDX", *symbols]}
    filings = {ticker: "2026-07-31" for ticker in symbols}
    with TemporaryDirectory(prefix="kuodra-p270-") as home:
        env = dict(os.environ, HOME=home, KUODRA_ENABLE_LOCAL_SOURCE_UI="1",
                   STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
        server = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run",
             str(ROOT/"streamlit_app.py"), "--server.headless=true",
             "--server.address=127.0.0.1", "--server.port=" + str(PORT),
             "--browser.gatherUsageStats=false"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                try:
                    with urlopen(URL + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    time.sleep(.25)
            else:
                raise AssertionError("P270_LOOPBACK_NOT_READY")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True, args=["--no-sandbox"])
                try:
                    context = browser.new_context(accept_downloads=True)
                    violations = []
                    errors = []

                    def offline(route):
                        if urlsplit(route.request.url).hostname in (
                                "127.0.0.1", "localhost"):
                            route.continue_()
                        else:
                            violations.append(urlsplit(route.request.url).hostname)
                            route.abort()

                    context.route("**/*", offline)
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                    expect(page.get_by_text("KUODRA — 오프라인 합성 데이터")
                           ).to_be_visible(timeout=25000)
                    page.get_by_test_id("stSelectbox").first.click()
                    page.get_by_role("option", name=MODE, exact=True).click()
                    expect(page.get_by_role("heading",
                        name="KUODRA · 미국 3~5종목 + 실제 I:NDX 형식 Engine A (로컬)")
                        ).to_be_visible(timeout=25000)
                    uploads = page.get_by_test_id("stFileUploader")
                    expect(uploads).to_have_count(4)
                    as_of_input = page.get_by_role(
                        "textbox", name="시장 데이터 기준일 (YYYY-MM-DD)")
                    expect(as_of_input).to_have_value("")
                    as_of_input.fill("2026-10-01")
                    for ticker in symbols:
                        filed_input = page.get_by_role(
                            "textbox", name=ticker + " 원본 10-K 제출일 (YYYY-MM-DD)")
                        expect(filed_input).to_have_value("")
                        filed_input.fill("2026-07-31")
                    for index, ticker in enumerate(["I:NDX", *symbols]):
                        uploads.nth(index).locator('input[type="file"]').set_input_files({
                            "name": ticker.replace(":", "_") + ".json",
                            "mimeType": "application/json",
                            "buffer": sources[ticker],
                        })
                    page.get_by_role("button",
                        name="로컬 3~5종목 Engine A 계산 → Guard HOLD",
                        exact=True).click()
                    expect(page.get_by_text(
                        "3~5종목 시장수익률·회귀 계산 완료 · Guard HOLD · 미인증",
                        exact=True)).to_be_visible(timeout=30000)
                    with page.expect_download(timeout=30000) as event:
                        page.get_by_role("button",
                            name="로컬 Engine A 근거 JSON (미인증)",
                            exact=True).click()
                    downloaded = event.value
                    if downloaded.suggested_filename != (
                            "KUODRA_LOCAL_NDX_3_TO_5_UNVERIFIED.json"):
                        raise AssertionError("P270_JSON_FILENAME")
                    report = json.loads(Path(downloaded.path()).read_bytes())
                    if (not verify_local_market_panel(
                            report,sources,symbols,filings,as_of="2026-10-01")
                            or report["issuer_count"] != 3
                            or report["source_rights_verified"] is not False
                            or report["guard_decision"] != "HOLD"
                            or report["network_requests"] != 0):
                        raise AssertionError("P270_JSON_REPLAY")
                    if violations or errors:
                        raise AssertionError("P270_UNEXPECTED_BROWSER_IO_OR_ERROR")
                    print(json.dumps({
                        "status": "PASS", "actual_chromium": True,
                        "uploaded_synthetic_json": 4,
                        "index": "I:NDX", "issuer_count": 3,
                        "json_download_replayed": True,
                        "guard": "HOLD", "external_hosts": 0,
                        "market_api_requests": 0, "rights_verified": False,
                        "production_verified": False}, sort_keys=True))
                finally:
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=8)


if __name__ == "__main__":
    main()
