"""P213 real Chromium: explicitly consented NVDA Guard audit ZIP download and replay.

Local loopback only. No SEC/issuer calls, transactions, private originals, or
persistent customer files. A small source-digest-only browser receipt is emitted.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from zipfile import ZipFile

from proofinvest.nvidia_audit_bundle import verify_nvidia_audit_bundle
from proofinvest.nvidia_real_issuer_review import actual_nvidia_issuer_receipt

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
URL = "http://127.0.0.1:8586"
MODE = "KUODRA · NVIDIA FY2026 공식 발행사 원문 검증 (제한)"
LABEL = "NVIDIA 로컬 검토 보고서 ZIP 내려받기"


def _ready() -> None:
    for _ in range(120):
        try:
            with urlopen(URL + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("P213_LOCAL_STREAMLIT_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="kuodra-p213-home-") as home:
        env = dict(os.environ)
        env.update({"HOME": home, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"})
        with (output / "p213-streamlit.log").open("wb") as server_log:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(APP),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 "--server.port=8586", "--browser.gatherUsageStats=false"],
                cwd=ROOT, env=env, stdout=server_log,
                stderr=subprocess.STDOUT,
            )
            try:
                _ready()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=True, args=["--no-sandbox"])
                    try:
                        context = browser.new_context(accept_downloads=True)
                        blocked_external = []

                        def loopback_only(route):
                            hostname = urlsplit(route.request.url).hostname
                            if hostname not in ("127.0.0.1", "localhost"):
                                blocked_external.append(hostname or "unknown")
                                route.abort()
                            else:
                                route.continue_()

                        context.route("**/*", loopback_only)
                        page = context.new_page()
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text(
                            "KUODRA — 오프라인 합성 데이터",
                        )).to_be_visible(timeout=25000)
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role("option", name=MODE, exact=True).click()
                        expect(page.get_by_role(
                            "heading",
                            name="KUODRA — NVIDIA FY2026 공식 발행사 실적 원문 검증",
                        )).to_be_visible(timeout=25000)
                        download_button = page.get_by_role(
                            "button", name=LABEL, exact=True)
                        guard_button = page.get_by_role(
                            "button", name="NVIDIA Guard HOLD 감사 1회 실행",
                            exact=True)
                        expect(download_button).to_have_count(0)
                        expect(guard_button).to_be_disabled()
                        page.get_by_role(
                            "checkbox",
                            name="NVIDIA 제한적 실자료 계산값을 임시 로컬 감사 DB에 기록하는 데 동의",
                            exact=True,
                        ).check()
                        expect(guard_button).to_be_enabled(timeout=20000)
                        expect(download_button).to_have_count(0)
                        guard_button.click()
                        expect(page.get_by_text(
                            "NVIDIA 실자료 Guard HOLD 감사 체인 검증 완료 (임시 DB 자동 삭제)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        expect(download_button).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=30000) as event:
                            download_button.click()
                        download = event.value
                        if download.suggested_filename != "KUODRA_NVDA_P212_local_review_only.zip":
                            raise AssertionError("P213_DOWNLOAD_FILENAME_MISMATCH")
                        archive = Path(download.path()).read_bytes()
                        digest = sha256(archive).hexdigest()
                        replay = verify_nvidia_audit_bundle(
                            archive, expected_sha256=digest)
                        if (replay.get("status") != "LOCAL_NVDA_BUNDLE_DIGEST_AND_REPLAY_PASS"
                                or replay.get("guard_decision") != "HOLD"
                                or replay.get("sec_original_authenticated") is not False
                                or replay.get("source_rights_verified") is not False
                                or replay.get("trade_executed") is not False):
                            raise AssertionError("P213_DOWNLOADED_REPLAY_FAILED")
                        with ZipFile(BytesIO(archive)) as zipped:
                            if set(zipped.namelist()) != {
                                "review.json", "review.html", "manifest.json"
                            }:
                                raise AssertionError("P213_ZIP_FILESET_INVALID")
                            report = json.loads(zipped.read("review.json"))
                            html = zipped.read("review.html").decode("utf-8")
                        if (report["ticker"] != "NVDA"
                                or report["source"]["issuer_original_sha256"] !=
                                actual_nvidia_issuer_receipt()["source_sha256"]
                                or report["audit"]["guard_decision"] != "HOLD"
                                or report["limitations"]["public_redistribution_authorized"] is not False
                                or "<script" in html.lower()):
                            raise AssertionError("P213_ZIP_OR_SOURCE_MISMATCH")
                        page.screenshot(
                            path=str(output / "p213-real-nvda-audit.png"),
                            full_page=False)
                        # A distinct Streamlit session must require fresh consent.
                        isolated = context.new_page()
                        isolated.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(isolated.get_by_text(
                            "KUODRA — 오프라인 합성 데이터",
                        )).to_be_visible(timeout=25000)
                        isolated.get_by_test_id("stSelectbox").first.click()
                        isolated.get_by_role("option", name=MODE, exact=True).click()
                        expect(isolated.get_by_role(
                            "button", name=LABEL, exact=True,
                        )).to_have_count(0)
                        expect(isolated.get_by_role(
                            "button", name="NVIDIA Guard HOLD 감사 1회 실행",
                            exact=True,
                        )).to_be_disabled()
                        receipt = {
                            "status": "PASS",
                            "scenario": "P213_NVDA_REAL_CHROMIUM_ZIP_DOWNLOAD",
                            "chromium_download_verified": True,
                            "issuer_original_sha256": report["source"]["issuer_original_sha256"],
                            "download_sha256": digest,
                            "download_bytes": len(archive),
                            "replay": replay["status"],
                            "guard_decision": "HOLD",
                            "new_session_consent_required": True,
                            "external_http_allowed": False,
                            "external_attempts_blocked": len(blocked_external),
                            "sec_original_authenticated": False,
                            "source_rights_verified": False,
                            "trade_executed": False,
                            "public_production_verified": False,
                        }
                        (output / "p213-nvda-download-browser.json").write_text(
                            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
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
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m scripts.nvidia_audit_download_browser_smoke OUTPUT_DIR")
    print(json.dumps(run(Path(sys.argv[1])), ensure_ascii=False, sort_keys=True))
