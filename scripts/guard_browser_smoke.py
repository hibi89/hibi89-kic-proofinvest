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
from contextlib import closing
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from proofinvest.guard_audit import GuardAuditStore
from proofinvest.guard_review import GuardReviewStore
from proofinvest.guard_audit_inspector import inspect_guard_snapshot

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
                        # Streamlit may auto-collapse the review expander on
                        # submit. The success message exists in the DOM but
                        # is hidden in that closed panel: browser visibility
                        # is not the durable acceptance criterion. Check that
                        # the actual SQLite review row was committed instead.
                        success_message = page.get_by_text("모의 검토 기록 저장 완료")
                        expect(success_message).to_have_count(1, timeout=15000)
                        with closing(sqlite3.connect(db)) as review_conn:
                            review_rows = review_conn.execute(
                                "SELECT COUNT(*) FROM guard_human_reviews"
                            ).fetchone()[0]
                            saved_action = review_conn.execute(
                                "SELECT action FROM guard_human_reviews"
                            ).fetchone()
                        if (review_rows != 1 or saved_action != ("ACKNOWLEDGE",)
                                or not GuardReviewStore(db).verify_reviews()):
                            raise AssertionError("Browser review not committed or invalid")

                        page.get_by_text("저장된 Guard 감사 이력 조회").click()
                        page.get_by_role("button", name="감사 무결성·이력 조회").click()
                        expect(page.get_by_text(
                            "Guard 결정 감사 체인 검증 통과 (로컬 무결성만)"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(path=str(output / "guard-browser-clickthrough.png"), full_page=True)
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
                        # Streamlit exposes a separate Open control next to
                        # this form combobox. Chromium did not expose any
                        # option after clicking the input alone (CI ARIA log),
                        # so open the menu using the accessible button inside
                        # the group that owns this exact combobox.
                        model_group = page.get_by_role("group").filter(has=model_picker)
                        model_group.get_by_role("button", name="Open").click()
                        mismatch_option = page.get_by_role(
                            "option", name="불일치 제안: SOURCE_REVIEW", exact=True
                        )
                        expect(mismatch_option).to_be_visible(timeout=10000)
                        mismatch_option.click()
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

                        # New integrated SEC -> Verification -> Risk -> Guard
                        # view: run ACTUAL synthetic local inputs, Guard and
                        # disposable SQLite in Chromium, not static mock text.
                        picker = page.get_by_role("combobox", name="자료 유형")
                        picker.click()
                        picker.fill("SEC→Guard 감사 연결")
                        page.get_by_role(
                            "option", name="SEC→Guard 감사 연결 — 합성 오프라인"
                        ).click(timeout=10000)
                        expect(page.get_by_text(
                            "ProofInvest — SEC 근거부터 Guard 감사까지"
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "실행 전에는 DB를 만들지 않습니다.", exact=False
                        )).to_be_visible(timeout=15000)

                        execute = page.get_by_role(
                            "button", name="합성 SEC→Guard 검증 실행"
                        )
                        execute.click()
                        expect(page.get_by_text(
                            "Guard 판정", exact=True
                        )).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "HOLD", exact=True
                        ).first).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "untrusted_html_text_node_literal_located",
                            exact=False
                        ).first).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "sec-guard-synthetic-hold.png"),
                            full_page=True,
                        )

                        scenario = page.get_by_role(
                            "combobox", name="검증 시나리오"
                        )
                        scenario.click()
                        scenario.fill("주장 불일치")
                        page.get_by_role(
                            "option", name="주장 불일치 → REJECT"
                        ).click(timeout=10000)
                        execute.click()
                        expect(page.get_by_text(
                            "REJECT", exact=True
                        ).first).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "sec-guard-synthetic-reject.png"),
                            full_page=True,
                        )

                        scenario.click()
                        scenario.fill("스크립트에만 있는 인용")
                        page.get_by_role(
                            "option", name="스크립트에만 있는 인용 → HOLD"
                        ).click(timeout=10000)
                        execute.click()
                        expect(page.get_by_text(
                            "HOLD", exact=True
                        ).first).to_be_visible(timeout=15000)
                        expect(page.get_by_text(
                            "HTML 인용 검증: unavailable",
                            exact=False
                        )).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "sec-guard-synthetic-script.png"),
                            full_page=True,
                        )

                        # Judge downloads the actual synthetic HTML result:
                        # inspect bytes in Chromium rather than just asserting
                        # that a button exists. No user inputs or live SEC.
                        with page.expect_download(timeout=20000) as got_html:
                            page.get_by_role(
                                "button", name="오프라인 HTML 보고서"
                            ).click()
                        html_receipt = got_html.value
                        if html_receipt.suggested_filename != (
                                "proofinvest_SYNTHETIC_SEC_GUARD_REVIEW.html"):
                            raise AssertionError("Unexpected synthetic HTML filename")
                        html_path = output / "sec-guard-browser-downloaded-script.html"
                        html_receipt.save_as(str(html_path))
                        html = html_path.read_text(encoding="utf-8")
                        if (len(html_path.read_bytes()) > 90000
                                or "UNVERIFIED LOCAL FILES" not in html
                                or "unavailable" not in html
                                or "HOLD" not in html
                                or "<script" in html.lower()
                                or "https://" in html):
                            raise AssertionError("Unsafe synthetic HTML download")

                        # Run all three scenarios through the same Streamlit
                        # screen; validate an ACTUAL browser-downloaded JSON
                        # matrix containing the 3 guarded decisions.
                        page.get_by_role(
                            "button", name="3개 시나리오 일괄 비교"
                        ).click()
                        expect(page.get_by_text(
                            "3가지 사례 · 로컬 실제 코드 실행 비교"
                        )).to_be_visible(timeout=25000)
                        expect(page.get_by_role(
                            "button", name="합성 비교 매트릭스 JSON"
                        )).to_be_visible(timeout=15000)
                        page.screenshot(
                            path=str(output / "sec-guard-compare-browser.png"),
                            full_page=True,
                        )
                        with page.expect_download(timeout=20000) as got_matrix:
                            page.get_by_role(
                                "button", name="합성 비교 매트릭스 JSON"
                            ).click()
                        matrix_receipt = got_matrix.value
                        if matrix_receipt.suggested_filename != (
                                "proofinvest_SYNTHETIC_COMPARISON.json"):
                            raise AssertionError("Unexpected comparison filename")
                        matrix_path = output / "sec-guard-compare-browser.json"
                        matrix_receipt.save_as(str(matrix_path))
                        if matrix_path.stat().st_size > 8192:
                            raise AssertionError("Oversize synthetic compare download")
                        with matrix_path.open("r", encoding="utf-8") as receipt:
                            matrix = json.load(receipt)
                        if (matrix.get("schema") != "proofinvest.synthetic-guard-compare.v1"
                                or matrix.get("evidence_class") !=
                                "SYNTHETIC_ONLY_UNVERIFIED"
                                or any(matrix.get(flag) is not False for flag in (
                                    "source_authenticated", "live_api_called",
                                    "trade_executed", "official_contest_submission"))
                                or not isinstance(matrix.get("cases"), list)
                                or len(matrix["cases"]) != 3
                                or [row["Guard"] for row in matrix["cases"]]
                                != ["HOLD", "REJECT", "HOLD"]
                                or matrix["cases"][-1]["원문 인용"] != "사용 불가"
                                or any(row["실거래"] != "없음" or
                                       row["SQLite 감사"] != "PASS"
                                       for row in matrix["cases"])):
                            raise AssertionError("Browser comparison contract invalid")
                        # Verify the full public synthetic judge ZIP by its
                        # actual browser download, not by trusting UI labels.
                        with page.expect_download(timeout=30000) as got_bundle:
                            page.get_by_role(
                                "button", name="전체 합성 증빙 ZIP (시작 페이지 포함)"
                            ).click()
                        bundle_download = got_bundle.value
                        if bundle_download.suggested_filename != (
                                "proofinvest_SYNTHETIC_GUARD_JUDGE.zip"):
                            raise AssertionError("Unexpected judge ZIP filename")
                        zip_path = output / "sec-guard-browser-judge-pack.zip"
                        bundle_download.save_as(str(zip_path))
                        import zipfile
                        with zipfile.ZipFile(zip_path) as judge_zip:
                            members = set(judge_zip.namelist())
                            manifest = json.loads(judge_zip.read(
                                "SYNTHETIC_JUDGE_MANIFEST.json"
                            ))
                            landing = judge_zip.read("START_HERE.html").decode("utf-8")
                            if (len(members) != 11
                                    or len(manifest["file_list"]) != 10
                                    or manifest["landing_page"] != "START_HERE.html"
                                    or manifest["evidence_class"] !=
                                    "SYNTHETIC_ONLY_UNVERIFIED"
                                    or "SYNTHETIC ONLY / NOT REAL SEC" not in landing
                                    or any(manifest[key] is not False for key in (
                                        "real_sec_authenticated",
                                        "real_agent_executed", "trade_executed",
                                        "official_kic_submission"
                                    ))):
                                raise AssertionError("Unsafe browser judge ZIP")
                        # Independent cold entry from the exact link a KIC
                        # judge will receive. The page must show the guard
                        # landing, but must NOT run the synthetic pipeline
                        # before an explicit click.
                        judge = browser.new_page(
                            viewport={"width": 1440, "height": 900},
                            device_scale_factor=1,
                        )
                        try:
                            judge.goto(URL + "/?demo=guard",
                                       wait_until="domcontentloaded", timeout=30000)
                            expect(judge.get_by_text(
                                "ProofInvest — SEC 근거부터 Guard 감사까지"
                            )).to_be_visible(timeout=20000)
                            expect(judge.get_by_text(
                                "실행 전에는 DB를 만들지 않습니다.", exact=False
                            )).to_be_visible(timeout=15000)
                            expect(judge.get_by_role(
                                "button", name="합성 SEC→Guard 검증 실행"
                            )).to_be_visible(timeout=15000)
                            judge.screenshot(
                                path=str(output / "judge-direct-link-before-run.png"),
                                full_page=True,
                            )
                        finally:
                            judge.close()
                    finally:
                        browser.close()

                audit_ok = GuardAuditStore(db).verify_chain()
                reviews_ok = GuardReviewStore(db).verify_reviews()
                with closing(sqlite3.connect(db)) as conn:
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
                audit_snapshot = inspect_guard_snapshot(db)
                if (audit_snapshot["status"] != "LOCAL_HASH_CHAIN_VALID"
                        or audit_snapshot["audit_events"] != 1
                        or audit_snapshot["human_reviews"] != 1
                        or audit_snapshot["decisions"]["HOLD"] != 1
                        or audit_snapshot["database_authenticated"] is not False
                        or audit_snapshot["sec_issuer_authenticated"] is not False
                        or audit_snapshot["raw_record_content_exported"] is not False):
                    raise AssertionError("Independent read-only audit inspection mismatch")
                (output / "guard-audit-snapshot-inspection.json").write_text(
                    json.dumps(audit_snapshot, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
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
                    "readonly_snapshot_inspection": "LOCAL_HASH_CHAIN_VALID",
                    "readonly_snapshot_receipt": "guard-audit-snapshot-inspection.json",
                    "live_sec_api_called": False,
                    "trade_executed": False,
                    "screenshot": "guard-browser-clickthrough.png",
                    "router_screenshot": "intent-router-browser.png",
                    "sec_guard_synthetic_only": True,
                    "synthetic_html_download_verified": True,
                    "synthetic_html_download": "sec-guard-browser-downloaded-script.html",
                    "judge_deeplink_verified": True,
                    "judge_deeplink_screenshot": "judge-direct-link-before-run.png",
                    "synthetic_comparison_download_verified": True,
                    "synthetic_full_judge_zip_verified": True,
                    "synthetic_full_judge_zip": "sec-guard-browser-judge-pack.zip",
                    "synthetic_comparison_download": "sec-guard-compare-browser.json",
                    "synthetic_comparison_screenshot": "sec-guard-compare-browser.png",
                    "synthetic_comparison_decisions": ["HOLD", "REJECT", "HOLD"],
                    "sec_guard_source_authenticated": False,
                    "sec_guard_trade_executed": False,
                    "sec_guard_scenarios": [
                        {"case": "matched", "guard": "HOLD",
                         "screenshot": "sec-guard-synthetic-hold.png"},
                        {"case": "conflict", "guard": "REJECT",
                         "screenshot": "sec-guard-synthetic-reject.png"},
                        {"case": "script_only_literal", "guard": "HOLD",
                         "html_text_node_status": "unavailable",
                         "screenshot": "sec-guard-synthetic-script.png"},
                    ],
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
