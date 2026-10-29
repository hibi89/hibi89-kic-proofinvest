"""Chromium click-through evidence for the local-only SEC Guard UI.

Run on an isolated CI runner with:
  python -m pip install -r requirements-ui.txt playwright
  python -m playwright install chromium
  python -m scripts.guard_browser_smoke OUTPUT_DIRECTORY

No external SEC/API requests, real trading, credentials or customer data.
The screenshot contains only the manually curated public 10-K excerpt.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SEC_MODE = "Apple SEC 10-K 수동 발췌 — 오프라인 검산 (2025/2024)"
URL = "http://127.0.0.1:8566"


def _ready() -> None:
    for _ in range(90):
        try:
            with urllib.request.urlopen(
                URL + "/_stcore/health", timeout=1
            ) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("Local Streamlit server did not become healthy")


def run(output: Path) -> dict:
    from playwright.sync_api import sync_playwright, expect

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kic-guard-browser-home-") as home:
        env = dict(os.environ)
        env["HOME"] = home
        env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        log_path = output / "streamlit-server.log"
        with log_path.open("wb") as log:
            server = subprocess.Popen(
                [
                    sys.executable, "-m", "streamlit", "run", str(APP),
                    "--server.headless=true",
                    "--server.address=127.0.0.1",
                    "--server.port=8566",
                    "--browser.gatherUsageStats=false",
                ],
                stdout=log, stderr=subprocess.STDOUT, env=env,
                cwd=APP.parent,
            )
            try:
                _ready()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(
                        headless=True, args=["--no-sandbox"]
                    )
                    try:
                        page = browser.new_page(
                            viewport={"width": 1440, "height": 1000},
                            device_scale_factor=1,
                        )
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text("ProofInvest — 오프라인 합성 데이터")).to_be_visible(timeout=20000)

                        # The first custom dropdown chooses the manually curated SEC case.
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role("option", name=SEC_MODE).click()
                        expect(page.get_by_text("ProofInvest — SEC 10-K 연매출 검산 (오프라인)")).to_be_visible(timeout=15000)
                        expect(page.get_by_text("HOLD", exact=True).first).to_be_visible(timeout=15000)

                        db = Path(home) / ".proofinvest-guard" / "audit.sqlite"
                        if db.exists():
                            raise AssertionError("Opening the screen wrote the Guard database")
                        page.get_by_role("button", name="Guard 판정·감사 기록 저장 (로컬 모의)").click()
                        expect(page.get_by_text("로컬 감사 기록 저장 완료")).to_be_visible(timeout=15000)
                        if not db.is_file():
                            raise AssertionError("Explicit Guard click did not create SQLite audit")

                        page.get_by_text("사람 검토 기록 — 로컬 모의").click()
                        page.get_by_label("검토자 식별명").fill("browser-judge")
                        page.get_by_label("검토 사유 (5자 이상)").fill(
                            "Reviewed offline calculation with no trading authorization"
                        )
                        # Streamlit reruns after input edits; avoid clicking a
                        # button while the previous widget subtree is replaced.
                        expect(page.get_by_label("검토자 식별명")).to_have_value("browser-judge")
                        expect(page.get_by_label("검토 사유 (5자 이상)")).to_have_value(
                            "Reviewed offline calculation with no trading authorization"
                        )
                        page.wait_for_timeout(1200)
                        page.get_by_role("button", name="검토 기록 저장", exact=True).click()
                        expect(page.get_by_text("모의 검토 기록 저장 완료")).to_be_visible(timeout=15000)

                        page.get_by_text("저장된 Guard 감사 이력 조회").click()
                        page.get_by_role("button", name="감사 무결성·이력 조회").click()
                        expect(page.get_by_text(
                            "Guard 결정 감사 체인 검증 통과 (로컬 무결성만)"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(path=str(output / "guard-browser-clickthrough.png"), full_page=True)
                    finally:
                        browser.close()

                audit_ok = GuardAuditStore(db).verify_chain()
                reviews_ok = GuardReviewStore(db).verify_reviews()
                with sqlite3.connect(db) as conn:
                    decisions = conn.execute(
                        "SELECT COUNT(*) FROM guard_audit_events"
                    ).fetchone()[0]
                    reviews = conn.execute(
                        "SELECT COUNT(*) FROM guard_human_reviews"
                    ).fetchone()[0]
                    action = conn.execute(
                        "SELECT action FROM guard_human_reviews"
                    ).fetchone()[0]
                if not (audit_ok and reviews_ok and decisions == 1
                        and reviews == 1 and action == "ACKNOWLEDGE"):
                    raise AssertionError("Guard browser SQLite evidence mismatch")
                result = {
                    "schema": "proofinvest.guard-browser-evidence.v1",
                    "status": "PASS",
                    "browser": "PLAYWRIGHT_CHROMIUM_HEADLESS",
                    "source_kind": "MANUALLY_CURATED_NOT_AUTHENTICATED",
                    "clicks": ["select_curated_sec", "save_guard_audit",
                               "save_human_review", "verify_and_read_history"],
                    "decision_count": decisions,
                    "review_count": reviews,
                    "review_action": action,
                    "audit_integrity_verified": audit_ok,
                    "reviews_integrity_verified": reviews_ok,
                    "live_sec_api_called": False,
                    "trade_executed": False,
                    "screenshot": "guard-browser-clickthrough.png",
                }
                (output / "guard-browser-evidence.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                return result
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.guard_browser_smoke OUTPUT_DIR")
    print(json.dumps(run(Path(sys.argv[1]).resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
