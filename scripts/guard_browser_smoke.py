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
    from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

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

                        page.get_by_text("사람 검토 기록 — 로컬 모의").last.click()
                        # Commit each Streamlit input sequentially. Filling a
                        # second field during the first widget rerun can lose
                        # the value before the user has a chance to submit.
                        reviewer_field = page.get_by_label("검토자 식별명")
                        reviewer_field.fill("browser-judge")
                        reviewer_field.press("Tab")
                        page.wait_for_timeout(800)
                        expect(reviewer_field).to_have_value("browser-judge")
                        reason_text = "Reviewed offline calculation with no trading authorization"
                        reason_field = page.get_by_label("검토 사유 (5자 이상)")
                        for _ in range(3):
                            reason_field.fill(reason_text)
                            reason_field.press("Tab")
                            page.wait_for_timeout(800)
                            if reason_field.input_value() == reason_text:
                                break
                        else:
                            raise AssertionError("Streamlit did not retain review reason")
                        review_button = page.get_by_role("button", name="검토 기록 저장", exact=True)
                        if review_button.count() == 0 or not review_button.is_visible():
                            # Streamlit may close the expander on a rerender.
                            page.get_by_text("사람 검토 기록 — 로컬 모의").last.click()
                        expect(review_button).to_be_visible(timeout=10000)
                        review_button.click()
                        # A successful Streamlit form submit rerenders a collapsed
                        # expander; the success is present but initially hidden.
                        success_message = page.get_by_text("모의 검토 기록 저장 완료")
                        expect(success_message).to_have_count(1, timeout=15000)
                        if not success_message.is_visible():
                            page.get_by_text("사람 검토 기록 — 로컬 모의").last.click()
                        expect(success_message).to_be_visible(timeout=10000)

                        page.get_by_text("저장된 Guard 감사 이력 조회").click()
                        page.get_by_role("button", name="감사 무결성·이력 조회").click()
                        expect(page.get_by_text(
                            "Guard 결정 감사 체인 검증 통과 (로컬 무결성만)"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(path=str(output / "guard-browser-clickthrough.png"), full_page=True)
                        # Verify the NEW DL/Guard report screen through a real
                        # Chromium click: no implicit disk writes, no SEC calls.
                        # Streamlit selectbox options can be virtualized and its
                        # keyword filter asynchronously re-rendered. Retry the
                        # *same exact destination* with shorter search terms.
                        # A failed search must never select another source.
                        option_name = "DL → Guard → SQLite 감사 보고서 — 오프라인"
                        for search_term in ("감사", "DL", "SQLite"):
                            dl_picker = page.get_by_role("combobox", name="자료 유형")
                            dl_picker.click()
                            dl_picker.fill(search_term)
                            option = page.get_by_role("option", name=option_name, exact=True)
                            try:
                                option.click(timeout=4500)
                                break
                            except PlaywrightTimeoutError:
                                dl_picker.press("Escape")
                        else:
                            raise AssertionError("DL Guard screen option unavailable after bounded retries")
                        expect(page.get_by_text(
                            "ProofInvest — DL → Guard 감사 보고서"
                        )).to_be_visible(timeout=15000)
                        if not page.get_by_role(
                            "button", name="합성 DL → Guard 감사·보고서 실행"
                        ).is_visible():
                            raise AssertionError("Missing explicit DL Guard run button")
                        page.get_by_role(
                            "button", name="합성 DL → Guard 감사·보고서 실행"
                        ).click()
                        expect(page.get_by_text(
                            "합성 자료 E2E 실행 및 임시 감사 검증 완료"
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "HOLD", exact=True
                        ).first).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "PASS", exact=True
                        ).first).to_be_visible(timeout=15000)
                        if not db.is_file():
                            raise AssertionError("Existing curated Guard ledger missing")
                        with sqlite3.connect(db) as existing:
                            if existing.execute(
                                "SELECT count(*) FROM guard_audit_events"
                            ).fetchone()[0] != 1:
                                raise AssertionError("Synthetic DL run wrote curated Guard DB")
                        page.screenshot(
                            path=str(output / "dl-guard-browser-report.png"),
                            full_page=True,
                        )
                        # Exercise the separate deterministic question router
                        # in a real Chromium session, never a live LLM agent.
                        # Search the selectbox rather than assuming all
                        # options are mounted (Streamlit virtualizes its menu).
                        picker = page.get_by_role("combobox", name="자료 유형")
                        picker.click()
                        picker.fill("질문별 로컬 도구 선택")
                        page.get_by_role(
                            "option", name="질문별 로컬 도구 선택 — 규칙 기반 시연"
                        ).click(timeout=10000)
                        expect(page.get_by_text(
                            "ProofInvest — 질문별 로컬 도구 선택"
                        )).to_be_visible(timeout=15000)
                        page.get_by_role(
                            "button", name="로컬 도구 선택·검증"
                        ).click()
                        expect(page.get_by_text(
                            "GROWTH_CHECK", exact=True
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "REJECT", exact=True
                        )).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "intent-router-browser.png"),
                            full_page=True,
                        )
                        # Mock model suggestions exercise the real LLM
                        # proposal gate, but NEVER call Gemini or SEC APIs.
                        page.get_by_role(
                            "button", name="모의 LLM 제안 검증"
                        ).click()
                        expect(page.get_by_text(
                            "ACCEPTED", exact=True
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "모의 제안 경로 Guard"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "mock-llm-proposal-accepted.png"),
                            full_page=True,
                        )
                        model_picker = page.get_by_role(
                            "combobox", name="모의 모델 응답"
                        )
                        model_picker.click()
                        model_picker.fill("불일치 제안")
                        page.get_by_role(
                            "option", name="불일치 제안: SOURCE_REVIEW"
                        ).click(timeout=10000)
                        page.get_by_role(
                            "button", name="모의 LLM 제안 검증"
                        ).click()
                        expect(page.get_by_text(
                            "BLOCKED", exact=True
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "로컬 도구 실행 0회 · 추출 데이터 없음"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "mock-llm-proposal-blocked.png"),
                            full_page=True,
                        )
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
                    "router_screenshot": "intent-router-browser.png",
                    "dl_guard_screenshot": "dl-guard-browser-report.png",
                    "dl_guard_status": "SYNTHETIC_HOLD_WITH_VERIFIED_TEMP_AUDIT",
                    "router_status": "REJECT",
                    "router_intent": "GROWTH_CHECK",
                    "mock_llm_api_calls": 0,
                    "mock_model_proposal_cases": [
                        {"proposal": "GROWTH_CHECK", "preflight": "ACCEPTED",
                         "local_guard": "REJECT"},
                        {"proposal": "SOURCE_REVIEW", "preflight": "BLOCKED",
                         "local_tool_calls": 0},
                    ],
                    "mock_model_screenshots": [
                        "mock-llm-proposal-accepted.png",
                        "mock-llm-proposal-blocked.png",
                    ],
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
