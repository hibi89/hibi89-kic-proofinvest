"""P165 real Chromium re-upload / click-through of a SYNTHETIC KUODRA packet.

Runs against a loopback-only Streamlit process on an isolated temporary HOME.
No actual SEC/vendor/LLM request, source-rights grant, Guard execution or trade.
The sample packet is generated from existing public *synthetic fixture code*.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from proofinvest.ticker_review_packet import build_review_packet, review_packet_json_bytes
from tests.test_ticker_market_pair_evidence import _build, _prepared

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
URL = "http://127.0.0.1:8572"
_INSPECT = "다운로드 패키지 무결성 검사 (네트워크 없음)"
_UPLOAD = "이전에 다운로드한 검토 패키지 JSON (28KiB 이하)"
_OK = "검토 패키지 내부 무결성 PASS (원본·공급자 인증 아님)"
_ERROR = "REVIEW_PACKET_OFFLINE_INTEGRITY_FAILED"


def _ready() -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(URL + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("P165_LOCAL_STREAMLIT_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import sync_playwright, expect

    # No real network: the full source+price/industry fixture is constructed
    # in this local Python process and only the final redacted JSON is uploaded.
    raw = review_packet_json_bytes(build_review_packet(_build(_prepared())))
    assert 0 < len(raw) <= 28672
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="kuodra-p165-browser-home-") as home:
        # Do not inherit ANY KUODRA provider secrets/approval switches from
        # runner or developer env; CI is an entirely offline review exercise.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("KUODRA_")}
        env.update({
            "HOME": home,
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "KUODRA_ENABLE_SEC_FETCH_UI": "0",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        })

        with (output / "p165-streamlit-server.log").open("wb") as log:
            server = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", str(APP),
                "--server.headless=true", "--server.address=127.0.0.1",
                "--server.port=8572", "--browser.gatherUsageStats=false",
            ], cwd=APP.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                _ready()
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(
                        headless=True, args=["--no-sandbox"],
                    )
                    try:
                        context = browser.new_context(
                            viewport={"width": 1440, "height": 1100},
                            accept_downloads=False,
                        )
                        # Fail closed to external HTTP even when a future UI
                        # accidentally adds a background fetch.
                        forbidden_requests = []
                        def intercept(route):
                            target = route.request.url
                            if target.startswith(URL + "/") or target == URL:
                                route.continue_()
                            else:
                                forbidden_requests.append(target.split("?")[0][:150])
                                route.abort()
                        context.route("**/*", intercept)

                        page = context.new_page()
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text(
                            "KUODRA — 오프라인 합성 데이터",
                        )).to_be_visible(timeout=25000)
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role(
                            "option",
                            name="KUODRA · 종목 1개 검색 (로컬 전용)",
                            exact=True,
                        ).click()
                        expect(page.get_by_text(
                            "다운로드한 A/B/C 검토 패키지 재검사 (오프라인)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        action = page.get_by_role("button", name=_INSPECT, exact=True)
                        expect(action).to_be_disabled()
                        expect(page.get_by_role(
                            "button", name="SEC 원문 4종 자동 수집 실행",
                            exact=True,
                        )).to_be_disabled()
                        expect(page.get_by_text(_OK, exact=True)).to_have_count(0)

                        uploader = page.get_by_test_id("stFileUploader").filter(
                            has=page.get_by_text(_UPLOAD, exact=True),
                        ).locator('input[type="file"]')
                        expect(uploader).to_have_count(1)

                        def upload(name: str, data: bytes) -> None:
                            uploader.set_input_files({
                                "name": name,
                                "mimeType": "application/json",
                                "buffer": data,
                            })
                            expect(page.get_by_role(
                                "button", name="Remove " + name, exact=True,
                            )).to_be_visible(timeout=22000)
                            expect(action).to_be_enabled(timeout=22000)

                        # Upload without explicit click must not claim success.
                        upload("p165-valid-review.json", raw)
                        expect(page.get_by_text(_OK, exact=True)).to_have_count(0)
                        action.click()
                        expect(page.get_by_text(_OK, exact=True)).to_be_visible(
                            timeout=22000,
                        )
                        expect(page.get_by_test_id("stMetric").filter(
                            has_text="검사 대상 종목 (미인증)",
                        )).to_contain_text("NVDA", timeout=12000)
                        expect(page.get_by_text(
                            "내부 무결성 통과는 공급자 원문 인증",
                            exact=False,
                        )).to_be_visible(timeout=12000)
                        expect(page.get_by_text(_ERROR, exact=True)).to_have_count(0)
                        page.screenshot(
                            path=str(output / "p165-valid-packet-browser.png"),
                            full_page=True,
                        )

                        # A new, modified input must not retain previous success.
                        upload("p165-tampered-review.json", raw + b" ")
                        expect(page.get_by_text(_OK, exact=True)).to_have_count(
                            0, timeout=22000,
                        )
                        action.click()
                        expect(page.get_by_text(_ERROR, exact=True)).to_be_visible(
                            timeout=22000,
                        )
                        expect(page.get_by_text(_OK, exact=True)).to_have_count(0)
                        page.screenshot(
                            path=str(output / "p165-rejected-packet-browser.png"),
                            full_page=True,
                        )

                        # Oversized files fail before any integrity parsing.
                        upload("p165-oversized-review.json", b"x" * 28673)
                        expect(page.get_by_text(_ERROR, exact=True)).to_have_count(0)
                        action.click()
                        expect(page.get_by_text(_ERROR, exact=True)).to_be_visible(
                            timeout=22000,
                        )
                        expect(page.get_by_text(_OK, exact=True)).to_have_count(0)
                        if forbidden_requests:
                            raise AssertionError(
                                "P165_EXTERNAL_BROWSER_REQUEST_BLOCKED: "
                                + repr(forbidden_requests),
                            )
                        if (Path(home) / ".proofinvest-guard" / "audit.sqlite").exists():
                            raise AssertionError("P165_UNEXPECTED_GUARD_AUDIT_WRITE")
                        context.close()
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=8)

    result = {
        "schema": "kuodra.p165-review-packet-real-browser-qa.v1",
        "status": "PASS",
        "synthetic_only": True,
        "real_chromium": True,
        "passive_upload_no_approval": True,
        "valid_reupload_internal_integrity_passed": True,
        "changed_bytes_rejected": True,
        "oversized_bytes_rejected": True,
        "live_sec_button_disabled": True,
        "browser_external_requests": 0,
        "sqlite_guard_audit_written": False,
        "publisher_source_authenticated": False,
        "vendor_rights_verified": False,
        "original_sec_and_price_replayed_in_browser": False,
        "trade_executed": False,
        "test_packet_sha256": sha256(raw).hexdigest(),
    }
    (output / "p165-review-packet-browser.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.review_packet_browser_smoke OUTDIR")
    print(json.dumps(run(Path(sys.argv[1])), ensure_ascii=False))
