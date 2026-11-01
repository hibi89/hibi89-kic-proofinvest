"""Real Chromium E2E for P79 reviewed SEC WEB -> simulated Guard Streamlit UI.

Never opens SEC links, uses credentials, calls a remote provider, persists an
audit, or edits an original source. Every UI scenario requires an actual click.
Run: python -B -m scripts.sec_web_guard_browser_smoke /tmp/kic-web-guard
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
PORT = 8577
URL = f"http://127.0.0.1:{PORT}"
CASES = (
    ("30% 성장 주장 — 수동 검산과 충돌", "CONFLICT", "REJECT", "web-guard-conflict.png"),
    ("6.43% 성장 주장 — 수동 검산과 일치", "VERIFIED", "HOLD", "web-guard-matched.png"),
    ("성장률 주장 없음 — 비교 불가", "UNAVAILABLE", "HOLD", "web-guard-missing.png"),
)


def _healthy() -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(URL + "/_stcore/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("LOCAL_STREAMLIT_HEALTH_TIMEOUT")


def _guard_metric(page):
    return page.get_by_test_id("stMetric").filter(has_text="데모 Guard 판정")


def _numeric_metric(page):
    return page.get_by_test_id("stMetric").filter(has_text="숫자 주장 비교")


def run(output: Path) -> dict:
    from playwright.sync_api import sync_playwright, expect

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kic-sec-web-guard-chromium-") as home:
        env = dict(os.environ)
        env["HOME"] = home
        env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        env["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] = "true"
        env["STREAMLIT_SERVER_ENABLE_CORS"] = "true"
        log_path = output / "web-guard-streamlit.log"
        with log_path.open("wb") as logfile:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(APP),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 f"--server.port={PORT}", "--browser.gatherUsageStats=false"],
                stdout=logfile, stderr=subprocess.STDOUT, cwd=APP.parent, env=env,
            )
            try:
                _healthy()
                with sync_playwright() as browser_driver:
                    browser = browser_driver.chromium.launch(
                        headless=True, args=["--no-sandbox"]
                    )
                    try:
                        page = browser.new_page(viewport={"width": 1400, "height": 930})
                        external_requests = []
                        def audit_http(request):
                            from urllib.parse import urlsplit
                            parsed = urlsplit(request.url)
                            if (parsed.hostname not in ("127.0.0.1", "localhost")
                                    or parsed.port != PORT):
                                external_requests.append(
                                    {"scheme": parsed.scheme, "host": parsed.hostname}
                                )
                        page.on("request", audit_http)

                        page.goto(URL + "/?demo=sec-web-guard",
                                  wait_until="domcontentloaded", timeout=30000)
                        expect(page).to_have_title(
                            "KUODRA | 오프라인 출처 시연", timeout=30000
                        )
                        expect(page.locator(".pi-brand")).to_contain_text(
                            "KUODRA", timeout=15000
                        )
                        expect(page.locator(".pi-brand")).not_to_contain_text(
                            "PROOFINVEST", timeout=15000
                        )
                        expect(page.get_by_text(
                            "KUODRA · Apple SEC 웹 수동검산 → 데모 Guard"
                        )).to_be_visible(timeout=30000)
                        expect(page.get_by_text(
                            "SEC_RENDERED_WEB_TEXT", exact=False
                        ).first).to_be_visible(timeout=10000)
                        # Deep-link selects the mode but MUST NOT execute Guard.
                        expect(_guard_metric(page)).to_have_count(0)
                        expect(page.get_by_text(
                            "버튼을 누르기 전에는 분석 함수·Guard를 실행하지 않습니다."
                        )).to_be_visible()
                        # Independent Engine B click must not execute Guard.
                        expect(page.get_by_text(
                            "별도 버튼을 누르기 전에는 Engine B를 실행하지 않습니다."
                        )).to_be_visible()
                        page.get_by_role(
                            "button", name="Engine B 오프라인 회계 신호 계산"
                        ).click()
                        expect(page.get_by_test_id("stMetric").filter(
                            has_text="회계 검토 질문 · 이상행위 확정 아님"
                        )).to_contain_text("3건", timeout=30000)
                        for v in ("12.63pp", "-26.63pp", "-15.66pp", "387.22%"):
                            expect(page.get_by_text(v, exact=True)).to_be_visible()
                        expect(_guard_metric(page)).to_have_count(0)
                        # Real browser download contains exact operands,
                        # trace formulas and a self-consistency SHA, never auth.
                        with page.expect_download(timeout=15000) as trace_info:
                            page.get_by_role(
                                "button",
                                name="회계 근거 보고서 JSON 다운로드 (오프라인)",
                                exact=True,
                            ).click()
                        trace_download = trace_info.value
                        if trace_download.suggested_filename != (
                                "kuodra-accounting-trace-OFFLINE.json"):
                            raise AssertionError("ENGINE_B_TRACE_DOWNLOAD_FILENAME")
                        import hashlib
                        report = json.loads(Path(trace_download.path()).read_text(
                            encoding="utf-8"
                        ))
                        report_copy = dict(report)
                        digest = report_copy.pop("report_sha256", None)
                        canonical = (json.dumps(
                            report_copy, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False,
                        ) + "\n").encode("utf-8")
                        if (report.get("schema") !=
                                "kuodra.manual-sec-web-accounting-trace.v1"
                                or digest != hashlib.sha256(canonical).hexdigest()
                                or report.get("review_prompt_count") != 3
                                or len(report.get("trace_cells", [])) != 7
                                or [s["value"] for s in report["signals"]] != [
                                    "12.63", "-26.63", "-15.66", "387.22"
                                ]
                                or report.get("digest_proves_sec_origin") is not False
                                or report.get("source_authenticated") is not False
                                or report.get("guard_decision_changed") is not False
                                or report.get("external_http_called") is not False):
                            raise AssertionError("ENGINE_B_TRACE_DOWNLOAD_INVALID")
                        expect(_guard_metric(page)).to_have_count(0)
                        page.screenshot(path=str(output / "web-engine-b-click.png"),
                                        full_page=True)
                        page.screenshot(path=str(output / "web-guard-before-click.png"),
                                        full_page=True)

                        audit_path = Path(home) / ".proofinvest-guard" / "audit.sqlite"
                        if audit_path.exists():
                            raise AssertionError("UNEXPECTED_AUDIT_CREATED_BEFORE_CLICK")

                        recorded = []
                        for index, (label, verdict, decision, filename) in enumerate(CASES):
                            if index:
                                page.get_by_test_id("stSelectbox").nth(1).click()
                                page.get_by_role("option", name=label, exact=True).click()
                                # Streamlit rerender must withdraw the previous
                                # result so a changed claim cannot show stale Guard.
                                expect(_guard_metric(page)).to_have_count(0, timeout=15000)
                                expect(page.get_by_text(
                                    "버튼을 누르기 전에는 분석 함수·Guard를 실행하지 않습니다."
                                )).to_be_visible(timeout=15000)
                            # The Streamlit combobox input value is not a
                            # standalone text node (Playwright aria snapshot
                            # confirms the selected value). The actual Guard
                            # verdict after clicking is the durable assertion.

                            page.get_by_role(
                                "button", name="오프라인 수동 검산 → 데모 Guard 실행",
                            ).click()
                            expect(_guard_metric(page)).to_contain_text(
                                decision, timeout=30000
                            )
                            expect(_numeric_metric(page)).to_contain_text(
                                verdict, timeout=10000
                            )
                            expect(page.get_by_test_id("stMetric").filter(
                                has_text="매출 성장률 · 수동 검산"
                            )).to_contain_text("6.43%", timeout=10000)
                            if audit_path.exists():
                                raise AssertionError("DEMO_MUST_NOT_PERSIST_SQLITE")
                            if external_requests:
                                raise AssertionError("BROWSER_ATTEMPTED_EXTERNAL_REQUEST")
                            page.screenshot(path=str(output / filename),
                                            full_page=True)
                            recorded.append({
                                "case": ("CONFLICT", "MATCHED", "MISSING")[index],
                                "numeric_verdict": verdict,
                                "guard_decision": decision,
                                "risk_available": False,
                                "issuer_source_authenticated": False,
                                "sqlite_audit_created": False,
                                "external_http_called": False,
                                "trade_executed": False,
                            })

                        assert [r["guard_decision"] for r in recorded] == [
                            "REJECT", "HOLD", "HOLD",
                        ]
                        # P85: exercise the P84 custom textbox in ACTUAL Chromium,
                        # reusing this local browser/server, not another test app.
                        page.get_by_test_id("stSelectbox").nth(1).click()
                        page.get_by_role(
                            "option", name="직접 입력 — 성장률(%)", exact=True
                        ).click()
                        custom_input = page.get_by_test_id("stTextInput").locator("input")
                        expect(custom_input).to_be_visible(timeout=15000)
                        expect(_guard_metric(page)).to_have_count(0, timeout=15000)

                        for claim, numeric, guard, filename in (
                            ("8.25", "CONFLICT", "REJECT", "web-guard-custom-conflict.png"),
                            ("6.43", "VERIFIED", "HOLD", "web-guard-custom-matched.png"),
                        ):
                            custom_input.fill(claim)
                            custom_input.press("Tab")  # commit Streamlit textbox on blur
                            # Typing cannot execute Guard or preserve the old result.
                            expect(_guard_metric(page)).to_have_count(0, timeout=15000)
                            expect(page.get_by_text(
                                "버튼을 누르기 전에는 분석 함수·Guard를 실행하지 않습니다."
                            )).to_be_visible(timeout=15000)
                            page.get_by_role(
                                "button", name="오프라인 수동 검산 → 데모 Guard 실행"
                            ).click()
                            expect(_guard_metric(page)).to_contain_text(
                                guard, timeout=30000
                            )
                            expect(_numeric_metric(page)).to_contain_text(
                                numeric, timeout=10000
                            )
                            if claim == "8.25":
                                expect(page.get_by_text(
                                    "가상 8.25% 성장 주장", exact=False
                                )).to_be_visible(timeout=10000)
                            if audit_path.exists():
                                raise AssertionError("CUSTOM_DEMO_MUST_NOT_PERSIST_SQLITE")
                            if external_requests:
                                raise AssertionError("CUSTOM_DEMO_EXTERNAL_REQUEST")
                            page.screenshot(path=str(output / filename), full_page=True)
                            recorded.append({
                                "case": "CUSTOM_CONFLICT" if claim == "8.25" else "CUSTOM_MATCHED",
                                "claim_growth_pct": claim,
                                "numeric_verdict": numeric,
                                "guard_decision": guard,
                                "issuer_source_authenticated": False,
                                "sqlite_audit_created": False,
                                "external_http_called": False,
                                "trade_executed": False,
                            })
                            if claim == "8.25":
                                custom_input.fill("NaN")
                                custom_input.press("Tab")  # commit before stale-result check
                                expect(_guard_metric(page)).to_have_count(0, timeout=15000)
                                page.get_by_role(
                                    "button", name="오프라인 수동 검산 → 데모 Guard 실행"
                                ).click()
                                expect(page.get_by_text(
                                    "입력값 또는 수동 근거", exact=False
                                )).to_be_visible(timeout=10000)
                                expect(_guard_metric(page)).to_have_count(0)
                                expect(_numeric_metric(page)).to_have_count(0)
                                if audit_path.exists() or external_requests:
                                    raise AssertionError("INVALID_CUSTOM_CLAIM_SIDE_EFFECT")
                                page.screenshot(
                                    path=str(output / "web-guard-custom-invalid.png"),
                                    full_page=True,
                                )
                                recorded.append({
                                    "case": "CUSTOM_INVALID_NAN_BLOCKED",
                                    "claim_growth_pct": None,
                                    "numeric_verdict": "BLOCKED",
                                    "guard_decision": None,
                                    "issuer_source_authenticated": False,
                                    "sqlite_audit_created": False,
                                    "external_http_called": False,
                                    "trade_executed": False,
                                })

                        # P87: actual browser download must agree with current
                        # custom claim and cannot silently imply authenticated SEC.
                        with page.expect_download(timeout=15000) as download_info:
                            page.get_by_role(
                                "button", name="검산 영수증 JSON 다운로드 (데모 전용)",
                                exact=True,
                            ).click()
                        download = download_info.value
                        if download.suggested_filename != "kuodra-sec-web-guard-DEMO.json":
                            raise AssertionError("UNEXPECTED_DEMO_RECEIPT_FILENAME")
                        receipt_payload = json.loads(
                            Path(download.path()).read_text(encoding="utf-8")
                        )
                        if (receipt_payload.get("schema") !=
                                "kuodra.manual-sec-web-guard-receipt.v1"
                                or receipt_payload.get("status") !=
                                "OFFLINE_DEMO_ONLY_ORIGINAL_UNVERIFIED"
                                or receipt_payload.get("numeric_check", {}).get(
                                    "claim_growth_pct") != "6.43"
                                or receipt_payload["numeric_check"]["numeric_verdict"] != "VERIFIED"
                                or receipt_payload["simulated_guard"]["decision"] != "HOLD"
                                or receipt_payload["source"]["issuer_original_authenticated"] is not False
                                or any(value is not False for value in
                                       receipt_payload["limits"].values())
                                or receipt_payload["simulated_guard"]["human_approved"] is not False):
                            raise AssertionError("BROWSER_DOWNLOAD_TRUST_CONTRACT_BROKEN")
                        if external_requests or audit_path.exists():
                            raise AssertionError("DOWNLOAD_TRIGGERED_SIDE_EFFECT")
                        assert [r["guard_decision"] for r in recorded] == [
                            "REJECT", "HOLD", "HOLD", "REJECT", None, "HOLD",
                        ]
                        receipt = {
                            "schema": "kuodra.sec-web-guard-chromium-e2e.v2",
                            "status": "PASS",
                            "runner": "ACTUAL_LOCAL_CHROMIUM_NOT_PRODUCTION",
                            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                            "source_kind": "SEC_RENDERED_WEB_TEXT_MANUALLY_REVIEWED_NOT_RAW",
                            "manual_web_cells_checked": 28,
                            "browser_scenarios": recorded,
                            "pre_click_guard_executed": False,
                            "prior_guard_result_cleared_on_claim_change": True,
                            "custom_textbox_chromium_tested": True,
                            "download_receipt_verified": True,
                            "engine_b_actual_chromium_click": True,
                            "engine_b_review_prompt_count": 3,
                            "engine_b_guard_not_executed": True,
                            "engine_b_trace_download_verified": True,
                            "invalid_custom_claim_fail_closed": True,
                            "browser_external_requests": external_requests,
                            "sqlite_audit_created": False,
                            "external_sec_original_authenticated": False,
                            "real_a_b_c_e2e": False,
                            "live_llm_called": False,
                            "production_deployed": False,
                            "contest_submitted": False,
                        }
                        (output / "web-guard-browser-evidence.json").write_text(
                            json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True),
                            encoding="utf-8",
                        )
                        return receipt
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m scripts.sec_web_guard_browser_smoke OUTPUT_DIRECTORY")
    result = run(Path(sys.argv[1]))
    print(json.dumps({
        "status": result["status"],
        "scenarios": len(result["browser_scenarios"]),
        "decisions": [row["guard_decision"] for row in result["browser_scenarios"]],
        "external_requests": len(result["browser_external_requests"]),
        "sqlite_audit_created": result["sqlite_audit_created"],
        "real_sec_original_authenticated": result["external_sec_original_authenticated"],
    }, sort_keys=True))
