"""Actual Chromium local owner-upload arbitrary ticker -> 7-stage Guard E2E.

Uses only IN-MEMORY SYNTHETIC TEST FIXTURES; never downloads SEC or market data.
No original bytes, private prompts or screenshots appear in CI artifacts.
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

from tests.test_ticker_local_report_replay import report_case
from proofinvest.owner_source_global_agent import verify_owner_source_answer

ROOT=Path(__file__).resolve().parents[1]
PORT=8592
URL="http://127.0.0.1:"+str(PORT)
MODE="KUODRA · 미국 전 종목 원본 4개 → AI 도구/Guard (로컬)"
OUTPUT_NAME="kuodra-owner-ticker-UNVERIFIED.json"


def main() -> None:
    from playwright.sync_api import sync_playwright, expect
    _,raw=report_case()
    with TemporaryDirectory(prefix="kuodra-owner-source-browser-") as home:
        env=dict(os.environ,HOME=home,KUODRA_ENABLE_LOCAL_SOURCE_UI="1",
                 STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
        proc=subprocess.Popen(
            [sys.executable,"-m","streamlit","run",str(ROOT/"streamlit_app.py"),
             "--server.headless=true","--server.address=127.0.0.1",
             "--server.port="+str(PORT),
             "--browser.gatherUsageStats=false"],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                try:
                    with urlopen(URL+"/_stcore/health",timeout=1) as r:
                        if r.status==200:break
                except (OSError,TimeoutError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("OWNER_BROWSER_LOCAL_SERVER_NOT_READY")
            with sync_playwright() as driver:
                browser=driver.chromium.launch(headless=True,args=["--no-sandbox"])
                try:
                    context=browser.new_context(accept_downloads=True)
                    external=[]
                    errors=[]
                    def local(route):
                        if urlsplit(route.request.url).hostname in ("127.0.0.1","localhost"):
                            route.continue_()
                        else:
                            external.append(urlsplit(route.request.url).hostname)
                            route.abort()
                    context.route("**/*",local)
                    page=context.new_page()
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    page.goto(URL,wait_until="domcontentloaded",timeout=30000)
                    expect(page.get_by_text("KUODRA — 오프라인 합성 데이터")
                           ).to_be_visible(timeout=25000)
                    page.get_by_test_id("stSelectbox").first.click()
                    page.get_by_role("option",name=MODE,exact=True).click()
                    expect(page.get_by_role("heading",name="KUODRA · 미국 전 종목 원본 4개 → 질문 → 검산 → Guard (로컬)")
                           ).to_be_visible(timeout=25000)
                    # Distinct user-selected arbitrary ticker; lower-case UI
                    # is normalized to upper-case and revalidated against map.
                    page.get_by_role("textbox",name="검산할 미국 종목코드").fill("nvda")
                    page.get_by_role("textbox",name="기준일 (YYYY-MM-DD)").fill("2025-10-16")
                    page.get_by_role("textbox",name="검토할 질문").fill("NVDA 매출 성장률 검증")
                    uploads=page.get_by_test_id("stFileUploader")
                    expect(uploads).to_have_count(6)
                    for i,key in enumerate(("ticker_map","submissions","companyfacts","original_10k")):
                        filename=key+(".html" if key=="original_10k" else ".json")
                        payload={"name":filename,
                                 "mimeType":"text/html" if key=="original_10k" else
                                            "application/json",
                                 "buffer":raw[key]}
                        uploads.nth(i).locator('input[type="file"]').set_input_files(payload)
                    submit=page.get_by_role("button",name="원본 4개 검산 + 질문 분석 + Guard",exact=True)
                    submit.click()
                    expect(page.get_by_text("7단계 업로드 원본 검산 완료 · Guard HOLD",exact=True)
                           ).to_be_visible(timeout=30000)
                    expect(page.get_by_text("100.00%",exact=False)
                           ).to_be_visible(timeout=15000)
                    download_button=page.get_by_role("button",name="개인 로컬 검토용 파생 보고서 JSON",exact=True)
                    expect(download_button).to_be_visible(timeout=15000)
                    with page.expect_download(timeout=30000) as dl:
                        download_button.click()
                    downloaded=dl.value
                    if downloaded.suggested_filename!=OUTPUT_NAME:
                        raise AssertionError("OWNER_SOURCE_OUTPUT_NAME_MISMATCH")
                    content=Path(downloaded.path()).read_bytes()
                    report=json.loads(content)
                    if (report.get("ticker")!="NVDA" or
                            report.get("status")!="LOCAL_OWNER_FILE_BACKED_QUESTION_HUMAN_REVIEW" or
                            report.get("executed_financial_tools")!=7 or
                            report.get("guard_policy_preview")!="HOLD" or
                            report.get("source_rights_verified") is not False or
                            report.get("trade_executed") is not False or
                            not verify_owner_source_answer(
                                report,ticker="NVDA",as_of="2025-10-16",
                                question="NVDA 매출 성장률 검증",sources=raw)):
                        raise AssertionError("OWNER_SOURCE_DOWNLOADED_REPLAY_FAILED")
                    if errors:
                        raise AssertionError("OWNER_SOURCE_RUNTIME_ERROR")
                    print(json.dumps({
                        "status":"PASS","source":"SYNTHETIC_TEST_ONLY",
                        "browser_uploads":4,"file_bytes_stored_to_ci":False,
                        "issuer":"NVDA","replayed_report":True,
                        "question_to_seven_tools":True,
                        "guard":"HOLD","stock_api_gets":0,
                        "external_browser_requests_blocked":len(external),
                        "publisher_authenticated":False,
                        "production":False,
                        "report_sha256":sha256(content).hexdigest(),
                    },sort_keys=True))
                finally:
                    browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=8)


if __name__=="__main__":
    main()
