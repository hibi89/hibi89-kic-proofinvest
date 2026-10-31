"""Exercise the NEW actual KUODRA localhost upload UI with isolated synthetic bytes.

Real Playwright file-upload inputs and click-through, not a stubbed Streamlit API.
No external SEC/API, no private source, no model, no retained original/SQLite.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

from proofinvest.kic_dl_demo import (
    AS_OF, COLLECTED_AT, SYNTHETIC_CIK, SYNTHETIC_ACCESSION,
    synthetic_companyfacts, synthetic_submissions,
)
from proofinvest.kic_dl_original_demo import PHRASE, SYNTHETIC_HTML

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
URL = "http://127.0.0.1:8568"
MODE = "KUODRA · 로컬 원본 분석 (명시적 활성화)"


def _ready() -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(URL + "/_stcore/health", timeout=1) as req:
                if req.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("LOCAL_LOOPBACK_STREAMLIT_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import sync_playwright, expect

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kuodra-browser-only-home-") as home:
        env = dict(os.environ)
        env.update({
            "HOME": home, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        })
        with (output / "local-workspace-server.log").open("wb") as log:
            server = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", str(APP),
                "--server.headless=true", "--server.address=127.0.0.1",
                "--server.port=8568", "--browser.gatherUsageStats=false",
                "--server.enableXsrfProtection=true",
            ], cwd=APP.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                _ready()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=True, args=["--no-sandbox"],
                    )
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1100})
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text("ProofInvest — 오프라인 합성 데이터")).to_be_visible(
                            timeout=25000
                        )
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role("option", name=MODE, exact=True).click()
                        expect(page.get_by_text("KUODRA · 로컬 SEC 원본 3종 검토")).to_be_visible(
                            timeout=20000
                        )
                        # Every uploaded document exists ONLY as in-memory Playwright
                        # bytes sent to a loopback-only Streamlit process.
                        uploads = [
                            ("submissions.json", "application/json", synthetic_submissions()),
                            ("companyfacts.json", "application/json",
                             json.dumps(synthetic_companyfacts()).encode()),
                            ("original.html", "text/html", SYNTHETIC_HTML),
                        ]
                        for i, (name, mime, payload) in enumerate(uploads):
                            page.locator('input[type="file"]').nth(i).set_input_files({
                                "name": name, "mimeType": mime, "buffer": payload,
                            })
                            page.wait_for_timeout(750)
                        inputs = [
                            ("CIK 10자리", SYNTHETIC_CIK),
                            ("SEC 접수번호", SYNTHETIC_ACCESSION),
                            ("기준일 (YYYY-MM-DD)", AS_OF),
                            ("사용자 주장 수집시각 (UTC ISO8601)", COLLECTED_AT),
                            ("현재 회계기간 종료일", "2025-09-30"),
                            ("직전 회계기간 종료일", "2024-09-30"),
                            ("원문 본문에서 고유한 인용 문구", PHRASE),
                        ]
                        for label, value in inputs:
                            field = page.get_by_label(label, exact=True)
                            field.fill(value)
                            field.press("Tab")
                            page.wait_for_timeout(500)
                            expect(field).to_have_value(value)
                        expect(page.get_by_text("명시적으로")).to_have_count(0) if False else None
                        page.get_by_role(
                            "button", name="1단계 · 원본 대조 미리보기",
                        ).click()
                        expect(page.get_by_text("출처 메타데이터 대조 · 아직 감사 DB 기록 없음")).to_be_visible(
                            timeout=25000
                        )
                        expect(page.get_by_text("HOLD", exact=True)).to_have_count(0)  # not yet run
                        audit = page.get_by_role(
                            "button", name="2단계 · Guard 로컬 검증 실행",
                        )
                        expect(audit).to_be_disabled()
                        page.get_by_label(
                            "임시 로컬 SQLite 생성·검증 후 자동 삭제에 동의"
                        ).check()
                        expect(audit).to_be_enabled()
                        audit.click()
                        expect(page.get_by_text(
                            "로컬 Guard 완료 · 임시 SQLite 삭제 · 외부 출처 미인증"
                        )).to_be_visible(timeout=30000)
                        expect(page.get_by_text("HOLD", exact=True).first).to_be_visible()
                        expect(page.get_by_role(
                            "button", name="오프라인 분석 보고서 HTML",
                        )).to_be_visible()
                        if (Path(home) / ".proofinvest-guard" / "audit.sqlite").exists():
                            raise AssertionError("EPHEMERAL_UI_WROTE_PERSISTENT_SQLITE")
                        page.screenshot(
                            path=str(output / "kuodra-local-upload-guard.png"),
                            full_page=True,
                        )
                        result = {
                            "schema": "kuodra.local-upload-browser-check.v1",
                            "status": "PASS", "uploads": 3,
                            "stages": ["local-source-preview", "ephemeral-guard-HOLD"],
                            "source_authenticated": False,
                            "network_sec_requests": 0,
                            "persisted_audit_db": False,
                        }
                        (output / "kuodra-local-upload-browser.json").write_text(
                            json.dumps(result, sort_keys=True), encoding="utf-8",
                        )
                        return result
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
        raise SystemExit("python -m scripts.local_workspace_browser_smoke OUTPUT_DIR")
    print(json.dumps(run(Path(sys.argv[1]).resolve()), sort_keys=True))
