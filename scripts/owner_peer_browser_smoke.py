"""P268 real Chromium upload 8 synthetic filings, compare + Guard + two downloads."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen
from urllib.parse import urlsplit

from tests.test_owner_peer_compare import paired_synthetic_sources
from proofinvest.owner_peer_compare import verify_owner_peer,render_owner_peer_html

ROOT=Path(__file__).resolve().parents[1]
PORT=8593
URL="http://127.0.0.1:"+str(PORT)
MODE="KUODRA · 2개 미국기업 원본 대조 Engine C (로컬)"


def main()->None:
    from playwright.sync_api import expect,sync_playwright
    primary,peer=paired_synthetic_sources()
    with TemporaryDirectory(prefix="kuodra-p268-peer-") as home:
        env=dict(os.environ,HOME=home,KUODRA_ENABLE_LOCAL_SOURCE_UI="1",
                 STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
        server=subprocess.Popen(
            [sys.executable,"-m","streamlit","run",str(ROOT/"streamlit_app.py"),
             "--server.headless=true","--server.address=127.0.0.1",
             "--server.port="+str(PORT),"--browser.gatherUsageStats=false"],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:
            for i in range(120):
                try:
                    with urlopen(URL+"/_stcore/health",timeout=1) as r:
                        if r.status==200:break
                except (OSError,TimeoutError):
                    time.sleep(.25)
            else:raise AssertionError("P268_LOCAL_LOOPBACK_NOT_READY")
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
                try:
                    context=browser.new_context(accept_downloads=True)
                    violations=[]
                    js_errors=[]
                    def offline(route):
                        if urlsplit(route.request.url).hostname in ("127.0.0.1","localhost"):
                            route.continue_()
                        else:
                            violations.append(urlsplit(route.request.url).hostname)
                            route.abort()
                    context.route("**/*",offline)
                    page=context.new_page()
                    page.on("pageerror",lambda e:js_errors.append(str(e)))
                    page.goto(URL,wait_until="domcontentloaded",timeout=30000)
                    expect(page.get_by_text("KUODRA — 오프라인 합성 데이터")
                           ).to_be_visible(timeout=25000)
                    page.get_by_test_id("stSelectbox").first.click()
                    page.get_by_role("option",name=MODE,exact=True).click()
                    expect(page.get_by_role("heading",
                        name="KUODRA · 미국 두 기업 공시 원본 직접 비교 (Engine C)")
                        ).to_be_visible(timeout=25000)
                    page.get_by_role("textbox",name="대상 종목").fill("nvda")
                    page.get_by_role("textbox",name="비교 종목").fill("aapl")
                    page.get_by_role("textbox",name="비교 기준일 (YYYY-MM-DD)"
                                     ).fill("2025-10-16")
                    uploads=page.get_by_test_id("stFileUploader")
                    expect(uploads).to_have_count(8)
                    keys=("ticker_map","submissions","companyfacts","original_10k")
                    for i,raws in enumerate((primary,peer)):
                        for j,key in enumerate(keys):
                            uploads.nth(i*4+j).locator('input[type="file"]').set_input_files({
                                "name":key+(".html" if key=="original_10k" else ".json"),
                                "mimeType":"text/html" if key=="original_10k" else "application/json",
                                "buffer":raws[key]})
                    page.get_by_role("button",
                        name="두 기업 각각 검산 → Engine C 비교 → Guard",
                        exact=True).click()
                    expect(page.get_by_text("독립 원본 2세트 · 14단계 검산 완료 · Guard HOLD",
                        exact=True)).to_be_visible(timeout=30000)
                    expect(page.get_by_text("-100.00",exact=False)
                           ).to_be_visible(timeout=15000)
                    with page.expect_download(timeout=30000) as request:
                        page.get_by_role("button",name="로컬 비교 근거 JSON",exact=True).click()
                    jdl=request.value
                    if jdl.suggested_filename!="KUODRA_TWO_ISSUERS_UNVERIFIED.json":
                        raise AssertionError("P268_JSON_DOWNLOAD_NAME")
                    packet=json.loads(Path(jdl.path()).read_bytes())
                    kwargs={"ticker":"NVDA","peer_ticker":"AAPL",
                            "as_of":"2025-10-16","sources":primary,"peer_sources":peer}
                    if (not verify_owner_peer(packet,**kwargs)
                            or packet["comparison_guard"]!="HOLD"
                            or packet["growth_gap_primary_minus_peer_pp"]!="-100.00"
                            or packet["network_requests"]!=0
                            or packet["tool_calls"]!=14
                            or packet["source_authenticated"] is not False
                            or packet["peer_reuse_rights_verified"] is not False):
                        raise AssertionError("P268_JSON_REPLAY_FAILED")
                    with page.expect_download(timeout=30000) as request:
                        page.get_by_role("button",name="로컬 비교 인쇄 HTML",exact=True).click()
                    hdl=request.value
                    if hdl.suggested_filename!="KUODRA_TWO_ISSUERS_UNVERIFIED.html":
                        raise AssertionError("P268_HTML_DOWNLOAD_NAME")
                    if Path(hdl.path()).read_bytes()!=render_owner_peer_html(packet,**kwargs):
                        raise AssertionError("P268_HTML_REPLAY_FAILED")
                    if js_errors:raise AssertionError("P268_BROWSER_RUNTIME_ERROR")
                    print(json.dumps({
                        "status":"PASS","real_chromium":True,"synthetic_sources_only":True,
                        "two_distinct_ciks":True,"two_verified_file_uploads":8,
                        "separate_original_replays":2,"tool_calls":14,"guard":"HOLD",
                        "json_html_downloads_replayed":True,"network_requests":0,
                        "external_hosts_attempted":len(violations),
                        "publisher_authenticated":False,"rights_verified":False,
                        "investment_recommendation":False,"trade_executed":False,
                    },sort_keys=True))
                finally:browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=8)


if __name__=="__main__":
    main()
