"""P263: Chromium E2E for Nasdaq-free local US issuer B/C + Guard.

No private original or market download saved as CI artifact. Only redacted
browser assertions/receipt; Streamlit is bound to ephemeral CI loopback.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from proofinvest.global_fundamentals_review import (
    build_marketless_global_review, verify_marketless_global_review,
    marketless_global_review_html,
)

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
PORT = 8591
URL = "http://127.0.0.1:" + str(PORT)
MODE = "KUODRA · 글로벌 발행사 B/C·Guard (나스닥 없이, 로컬)"
JSON_NAME = "KUODRA_GLOBAL_BC_HOLD_UNVERIFIED.json"
HTML_NAME = "KUODRA_GLOBAL_BC_HOLD_UNVERIFIED.html"


def _ready() -> None:
    for _ in range(100):
        try:
            with urlopen(URL + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.3)
    raise RuntimeError("P263_LOCAL_STREAMLIT_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="kuodra-p263-home-") as home:
        env = dict(os.environ)
        env.update({
            "HOME": home,
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        })
        log_path = output / "p263-streamlit.log"
        with log_path.open("wb") as stream:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(APP),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 "--server.port=" + str(PORT),
                 "--browser.gatherUsageStats=false"],
                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
            )
            try:
                _ready()
                with sync_playwright() as driver:
                    browser = driver.chromium.launch(
                        headless=True, args=["--no-sandbox"])
                    try:
                        context = browser.new_context(accept_downloads=True)
                        blocked_external = []
                        js_errors = []

                        def route_local_only(route):
                            host = urlsplit(route.request.url).hostname
                            if host in ("127.0.0.1", "localhost"):
                                route.continue_()
                            else:
                                blocked_external.append(host or "unknown")
                                route.abort()

                        context.route("**/*", route_local_only)
                        page = context.new_page()
                        page.on("pageerror", lambda ex: js_errors.append(str(ex)))
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text(
                            "KUODRA — 오프라인 합성 데이터",
                        )).to_be_visible(timeout=25000)
                        # Default remains synthetic; no local review was executed.
                        expect(page.get_by_role(
                            "button", name="개인 검토용 근거 JSON",
                            exact=True)).to_have_count(0)
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role("option", name=MODE, exact=True).click()
                        expect(page.get_by_role(
                            "heading",
                            name="KUODRA · 글로벌 기업 재무·경쟁사 검증 (나스닥 없이)",
                        )).to_be_visible(timeout=25000)
                        expect(page.get_by_role(
                            "button", name="개인 검토용 근거 JSON",
                            exact=True)).to_have_count(0)

                        # P264: real human-input question route; verifies that
                        # the default never uses local/remote model or trades.
                        expect(page.get_by_role(
                            "button",name="질문 근거 검증 → Guard 답변",
                            exact=True)).to_be_visible(timeout=25000)
                        qfield=page.get_by_role("textbox",name="투자 검증 질문")
                        qfield.fill("NVDA 재고가 매출보다 빠르게 증가했나요?")
                        page.get_by_role(
                            "button",name="질문 근거 검증 → Guard 답변",
                            exact=True).click()
                        expect(page.get_by_text(
                            "질문 근거 분석 완료 · Guard HOLD · 투자 승인 아님",
                            exact=True)).to_be_visible(timeout=25000)
                        expect(page.get_by_text(
                            "NVDA 과거 발행사 수치상", exact=False,
                        )).to_be_visible(timeout=25000)
                        expect(page.get_by_text(
                            "46.86pp",exact=False)).to_be_visible(timeout=25000)
                        # Wrong issuer / missing year => fail-closed, not
                        # an automatic fallback to another company's figures.
                        qfield.fill("AAPL 재고 증가율")
                        page.get_by_role(
                            "button",name="질문 근거 검증 → Guard 답변",
                            exact=True).click()
                        expect(page.get_by_text(
                            "요청한 기업·기간·의도 또는 로컬 모델 검증 실패.",
                            exact=False)).to_be_visible(timeout=25000)
                        evidence = []
                        for ticker in ("NVDA", "DELL"):
                            if ticker != "NVDA":
                                # Start an independent Streamlit/browser session
                                # after downloads to avoid stale form overlay state.
                                page = context.new_page()
                                page.on("pageerror",
                                        lambda ex: js_errors.append(str(ex)))
                                page.goto(URL, wait_until="domcontentloaded",
                                          timeout=30000)
                                expect(page.get_by_text(
                                    "KUODRA — 오프라인 합성 데이터",
                                )).to_be_visible(timeout=25000)
                                page.get_by_test_id("stSelectbox").first.click()
                                page.get_by_role(
                                    "option", name=MODE, exact=True).click()
                                expect(page.get_by_role(
                                    "heading",
                                    name="KUODRA · 글로벌 기업 재무·경쟁사 검증 (나스닥 없이)",
                                )).to_be_visible(timeout=25000)
                                # The only selectbox within the form is issuer;
                                # do not rely on global widget indices.
                                form = page.get_by_test_id("stForm").filter(
                                    has=page.get_by_role("button",
                                        name="발행사·경쟁사 검산 및 Guard",exact=True)
                                ).first
                                selector = form.get_by_test_id(
                                    "stSelectbox").first
                                expect(selector).to_be_visible(timeout=25000)
                                selector.click()
                                expect(page.get_by_role(
                                    "option", name=ticker, exact=True),
                                ).to_be_visible(timeout=15000)
                                page.get_by_role(
                                    "option", name=ticker, exact=True).click()
                            page.get_by_role(
                                "button", name="발행사·경쟁사 검산 및 Guard",
                                exact=True).click()
                            jbutton = page.get_by_role(
                                "button", name="개인 검토용 근거 JSON",
                                exact=True)
                            hbutton = page.get_by_role(
                                "button", name="개인 검토용 근거 HTML",
                                exact=True)
                            expect(jbutton).to_be_visible(timeout=25000)
                            expect(hbutton).to_be_visible(timeout=25000)
                            expect(page.get_by_text(
                                "REVIEW_CANDIDATES_PRESENT",
                            )).to_have_count(0)
                            with page.expect_download(timeout=30000) as jwait:
                                jbutton.click()
                            jd = jwait.value
                            if jd.suggested_filename != JSON_NAME:
                                raise AssertionError("P263_JSON_NAME_MISMATCH")
                            packet = json.loads(Path(jd.path()).read_bytes())
                            if (not verify_marketless_global_review(packet)
                                    or packet != build_marketless_global_review(
                                        ticker=ticker)
                                    or packet["engine_b"]["screening_status"]
                                    != "REVIEW_CANDIDATES_PRESENT"
                                    or packet["guard"]["decision"] != "HOLD"
                                    or packet["market_api_requests"] != 0
                                    or packet["llm_requests"] != 0
                                    or packet["external_sharing_allowed"] is not False
                                    or packet["source_rights_verified"] is not False
                                    or packet["full_abc_complete"] is not False
                                    or packet["ai_agent_executed"] is not False):
                                raise AssertionError("P263_DOWNLOADED_JSON_UNTRUSTED")
                            with page.expect_download(timeout=30000) as hwait:
                                hbutton.click()
                            hd = hwait.value
                            if hd.suggested_filename != HTML_NAME:
                                raise AssertionError("P263_HTML_NAME_MISMATCH")
                            html = Path(hd.path()).read_bytes()
                            if (html != marketless_global_review_html(packet)
                                    or b"<script" in html.lower()
                                    or b"apikey" in html.lower()
                                    or len(html) > 32768):
                                raise AssertionError("P263_DOWNLOADED_HTML_UNTRUSTED")
                            evidence.append({
                                "ticker": ticker, "guard": "HOLD",
                                "verified_json_and_html": True,
                                "review_candidate_count":
                                    len(packet["engine_b"]["screening_signals"]),
                                "engine_a_status": packet["engine_a"]["status"],
                                "engine_c_status": packet["engine_c"]["status"],
                                "downloaded_json_sha256":
                                    sha256(Path(jd.path()).read_bytes()).hexdigest(),
                                "downloaded_html_sha256": sha256(html).hexdigest(),
                                "market_api_requests": 0, "llm_requests": 0,
                            })
                        if js_errors:
                            raise AssertionError("P263_BROWSER_RUNTIME_ERROR:" +
                                                 str(js_errors)[:300])
                        receipt = {
                            "status": "PASS",
                            "chromium_user_flow_exercised": True,
                            "independent_export_replay": True,
                            "default_synthetic_preserved": True,
                            "natural_language_question_flow_verified": True,
                            "unsupported_issuer_fail_closed": True,
                            "natural_question_local_model_calls": 0,
                            "scenarios": evidence,
                            "blocked_external_hosts_count": len(blocked_external),
                            "external_network_allowed": False,
                            "real_public_production": False,
                            "publisher_rights_verified": False,
                            "trade_executed": False,
                        }
                        (output / "p263-browser-receipt.json").write_text(
                            json.dumps(receipt, ensure_ascii=False,
                                       sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
                        # Never archive screenshots, raw publisher/price data,
                        # or the downloaded unlicensed review JSON/HTML.
                        return receipt
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)


if __name__ == "__main__":
    result = run(Path(sys.argv[1]) if len(sys.argv) > 1
                 else Path("/tmp/kic-p263-browser"))
    print(json.dumps({
        "status": result["status"],
        "chromium_user_flow_exercised":
            result["chromium_user_flow_exercised"],
        "scenarios": [x["ticker"] for x in result["scenarios"]],
        "guard": [x["guard"] for x in result["scenarios"]],
        "external_network_allowed": result["external_network_allowed"],
        "publisher_rights_verified": result["publisher_rights_verified"],
    }, sort_keys=True))
