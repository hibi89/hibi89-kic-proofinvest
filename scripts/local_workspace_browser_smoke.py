"""Exercise the NEW actual KUODRA localhost upload UI with isolated synthetic bytes.

Real Playwright file-upload inputs and click-through, not a stubbed Streamlit API.
No external SEC/API, no private source, no model, no retained original/SQLite.
"""
from __future__ import annotations

import json
from decimal import Decimal
from hashlib import sha256
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
                        # P35: only CIK/accession/as-of/collection need
                        # manual entry. Real SEC-shaped uploaded bytes provide
                        # a human-selectable read-only period/needle candidate.
                        identity_inputs = [
                            ("기준일 (YYYY-MM-DD)", AS_OF),
                            ("사용자 주장 수집시각 (UTC ISO8601)", COLLECTED_AT),
                        ]
                        for label, value in identity_inputs:
                            field = page.get_by_label(label, exact=True)
                            field.fill(value)
                            field.press("Tab")
                            page.wait_for_timeout(500)
                            expect(field).to_have_value(value)
                        page.get_by_role(
                            "button", name="업로드한 공시 목록에서 10-K 대상 찾기 (읽기 전용)",
                        ).click()
                        expect(page.get_by_text(
                            "10-K 공시 대상 후보 (원본과 대조 후 선택)", exact=True,
                        )).to_be_visible(timeout=18000)
                        page.get_by_role(
                            "button", name="선택한 공시의 CIK·접수번호 입력",
                        ).click()
                        expect(page.get_by_label("CIK 10자리", exact=True)).to_have_value(
                            SYNTHETIC_CIK, timeout=15000,
                        )
                        expect(page.get_by_label("SEC 접수번호", exact=True)).to_have_value(
                            SYNTHETIC_ACCESSION, timeout=15000,
                        )
                        page.get_by_text(
                            "원문 인용 문구 후보를 이 로컬 화면에 표시하는 데 동의",
                            exact=True,
                        ).click()
                        page.get_by_role(
                            "button", name="원본에서 연매출 기간 후보 찾기 (읽기 전용)",
                        ).click()
                        expect(page.get_by_text(
                            "연매출 기간 후보: 원본 형식 검증 결과이며 재무 사실 인증이 아닙니다."
                        )).to_be_visible(timeout=20000)
                        expect(page.get_by_text(
                            "원문 텍스트 후보 (사용자가 검토·선택)",
                            exact=True,
                        )).to_be_visible()
                        page.get_by_role(
                            "button", name="선택한 기간·문구를 입력란에 적용",
                        ).click()
                        for label, value in (
                            ("현재 회계기간 종료일", "2025-09-30"),
                            ("직전 회계기간 종료일", "2024-09-30"),
                            ("원문 본문에서 고유한 인용 문구", PHRASE),
                        ):
                            expect(page.get_by_label(label, exact=True)).to_have_value(
                                value, timeout=12000,
                            )
                        # P45: actual Chromium market upload (reject mismatched
                        # issuer before accepting matching historic observations).
                        # The existing local SEC/Guard path must remain unchanged.
                        from tests.test_market_reality import fixture as market_fixture
                        market_input = market_fixture()
                        market_raw = json.dumps(
                            market_input, sort_keys=True, separators=(",", ":"),
                        ).encode("utf-8")
                        different_issuer = dict(market_input)
                        different_issuer["issuer_cik"] = "0000000002"
                        price_upload = page.locator('input[type="file"]').last
                        price_upload.set_input_files({
                            "name": "market-wrong-cik.json",
                            "mimeType": "application/json",
                            "buffer": json.dumps(different_issuer).encode("utf-8"),
                        })
                        expect(page.get_by_text(
                            "Engine A 차단: 가격·시장지수 날짜/단위/출처·발행사를 확인하십시오."
                        )).to_be_visible(timeout=20000)
                        price_upload = page.locator('input[type="file"]').last
                        price_upload.set_input_files({
                            "name": "market-synthetic.json",
                            "mimeType": "application/json",
                            "buffer": market_raw,
                        })
                        expect(page.get_by_text(
                            "KUODRA · Engine A — Market Reality", exact=True,
                        )).to_be_visible(timeout=20000)
                        expect(page.get_by_text(
                            "베타 (표본회귀)", exact=True,
                        ).first).to_be_visible(timeout=20000)
                        expect(page.get_by_text(
                            "이 입력은 독립 출처 인증 전입니다.", exact=False,
                        )).to_be_visible(timeout=20000)
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
                        # React-Aria places an interactive label over the
                        # checkbox input. Click the actual visible label,
                        # rather than an input intercepted by the label.
                        page.get_by_text(
                            "임시 로컬 SQLite 생성·검증 후 자동 삭제에 동의",
                            exact=True,
                        ).click()
                        expect(audit).to_be_enabled()
                        audit.click()
                        expect(page.get_by_text(
                            "로컬 Guard 완료 · 임시 SQLite 삭제 · 외부 출처 미인증"
                        )).to_be_visible(timeout=30000)
                        expect(page.get_by_text("HOLD", exact=True).first).to_be_visible()
                        expect(page.get_by_text(
                            "Engine A · 시장 회귀 + SEC 실적 맥락", exact=True,
                        )).to_be_visible(timeout=20000)
                        with page.expect_download(timeout=15000) as market_json_download:
                            page.get_by_role(
                                "button", name="오프라인 분석 보고서 JSON",
                            ).click()
                        json_report = json.loads(
                            Path(market_json_download.value.path()).read_text(encoding="utf-8")
                        )
                        market_card = json_report.get("market_reality")
                        if (not isinstance(market_card, dict)
                                or market_card.get("status") != "REPORTED_UNVERIFIED"
                                or abs(Decimal(market_card["beta"]) - Decimal("1.5"))
                                   > Decimal("0.002")
                                or market_card.get("source", {}).get("upload_sha256")
                                   != sha256(market_raw).hexdigest()
                                or market_card.get("audit_included") is not False
                                or market_card.get("source_authenticated") is not False
                                or market_card.get("market_bubble_proven") is not False
                                or market_card.get("guard_policy_modified") is not False
                                or market_card.get("trade_signal") is not False
                                or json_report.get("guard", {}).get("decision") != "HOLD"
                                or json_report.get("limits", {}).get("live_api_called") is not False
                                or market_card.get("sec_revenue_context", {}).get(
                                    "growth_pct_calculated_unverified"
                                ) != json_report["verification"]["growth_pct"]
                                or market_card["sec_revenue_context"]["companyfacts_sha256"]
                                   != json_report["source"]["companyfacts_sha256"]):
                            raise AssertionError("ENGINE_A_BROWSER_DOWNLOAD_OR_SEC_JOIN_INVALID")
                        expect(page.get_by_role(
                            "button", name="오프라인 분석 보고서 HTML",
                        )).to_be_visible()
                        expect(page.get_by_text(
                            "KUODRA · 비인증 재무 검산 근거"
                        )).to_be_visible()
                        with page.expect_download(timeout=15000) as html_download:
                            page.get_by_role(
                                "button", name="오프라인 분석 보고서 HTML"
                            ).click()
                        html_bytes = Path(html_download.value.path()).read_bytes()
                        if (b"KUODRA | OFFLINE UNVERIFIED Review" not in html_bytes
                                or b"STRUCTURAL_NUMERIC_COMPARISON_ONLY" not in html_bytes
                                or b"RevenueFromContractWithCustomerExcludingAssessedTax" not in html_bytes
                                or b"Engine A" not in html_bytes
                                or b"Guard " not in html_bytes
                                or sha256(market_raw).hexdigest().encode() not in html_bytes):
                            raise AssertionError("HTML_REPORT_NOT_EVIDENCE_LINKED")
                        if (Path(home) / ".proofinvest-guard" / "audit.sqlite").exists():
                            raise AssertionError("EPHEMERAL_UI_WROTE_PERSISTENT_SQLITE")
                        page.screenshot(
                            path=str(output / "kuodra-local-upload-guard.png"),
                            full_page=True,
                        )
                        # P37: second isolated browser session exercises the
                        # complete historical four-upload path (not only Python).
                        from tests.test_kuodra_history import PAGE as HISTORY_PAGE, data as history_data
                        base_submissions, raw_history = history_data()
                        hist = browser.new_page(
                            viewport={"width": 1440, "height": 1100}
                        )
                        try:
                            hist.goto(URL, wait_until="domcontentloaded", timeout=30000)
                            expect(hist.get_by_text(
                                "ProofInvest — 오프라인 합성 데이터"
                            )).to_be_visible(timeout=25000)
                            hist.get_by_test_id("stSelectbox").first.click()
                            hist.get_by_role("option", name=MODE, exact=True).click()
                            expect(hist.get_by_text(
                                "KUODRA · 로컬 SEC 원본 3종 검토"
                            )).to_be_visible(timeout=25000)
                            historical_uploads = [
                                ("submissions.json", "application/json", base_submissions),
                                ("companyfacts.json", "application/json",
                                 json.dumps(synthetic_companyfacts()).encode()),
                                ("original.html", "text/html", SYNTHETIC_HTML),
                                (HISTORY_PAGE, "application/json", raw_history),
                            ]
                            for k, (name, mime, payload) in enumerate(historical_uploads):
                                hist.locator('input[type="file"]').nth(k).set_input_files({
                                    "name": name, "mimeType": mime, "buffer": payload,
                                })
                                hist.wait_for_timeout(650)
                            history_inputs = [
                                ("이력 페이지 파일명 (해당하는 경우 filings.files.name 그대로)",
                                 HISTORY_PAGE),
                                ("기준일 (YYYY-MM-DD)", AS_OF),
                                ("사용자 주장 수집시각 (UTC ISO8601)", COLLECTED_AT),
                            ]
                            for label, value in history_inputs:
                                field = hist.get_by_label(label, exact=True)
                                field.fill(value)
                                field.press("Tab")
                                hist.wait_for_timeout(450)
                                expect(field).to_have_value(value)
                            hist.get_by_role(
                                "button", name="업로드한 공시 목록에서 10-K 대상 찾기 (읽기 전용)",
                            ).click()
                            expect(hist.get_by_text(
                                "10-K 공시 대상 후보 (원본과 대조 후 선택)", exact=True,
                            )).to_be_visible(timeout=18000)
                            hist.get_by_role(
                                "button", name="선택한 공시의 CIK·접수번호 입력",
                            ).click()
                            expect(hist.get_by_label("CIK 10자리", exact=True)).to_have_value(
                                SYNTHETIC_CIK, timeout=15000,
                            )
                            expect(hist.get_by_label("SEC 접수번호", exact=True)).to_have_value(
                                SYNTHETIC_ACCESSION, timeout=15000,
                            )
                            hist.get_by_text(
                                "원문 인용 문구 후보를 이 로컬 화면에 표시하는 데 동의",
                                exact=True,
                            ).click()
                            hist.get_by_role(
                                "button", name="원본에서 연매출 기간 후보 찾기 (읽기 전용)",
                            ).click()
                            expect(hist.get_by_text(
                                "연매출 기간 후보: 원본 형식 검증 결과이며 재무 사실 인증이 아닙니다."
                            )).to_be_visible(timeout=25000)
                            hist.get_by_role(
                                "button", name="선택한 기간·문구를 입력란에 적용",
                            ).click()
                            expect(hist.get_by_label(
                                "현재 회계기간 종료일", exact=True,
                            )).to_have_value("2025-09-30")
                            hist.get_by_role(
                                "button", name="1단계 · 원본 대조 미리보기",
                            ).click()
                            expect(hist.get_by_text(
                                "출처 메타데이터 대조 · 아직 감사 DB 기록 없음"
                            )).to_be_visible(timeout=30000)
                            hist.get_by_text(
                                "임시 로컬 SQLite 생성·검증 후 자동 삭제에 동의",
                                exact=True,
                            ).click()
                            hist.get_by_role(
                                "button", name="2단계 · Guard 로컬 검증 실행",
                            ).click()
                            expect(hist.get_by_text(
                                "로컬 Guard 완료 · 임시 SQLite 삭제 · 외부 출처 미인증"
                            )).to_be_visible(timeout=30000)
                            with hist.expect_download(timeout=15000) as downloaded:
                                hist.get_by_role(
                                    "button", name="오프라인 분석 보고서 JSON"
                                ).click()
                            result_file = downloaded.value.path()
                            report_json = json.loads(Path(result_file).read_text(
                                encoding="utf-8"
                            ))
                            if (report_json["source"]["source_index_kind"] != "PINNED_HISTORY"
                                    or report_json["guard"]["decision"] != "HOLD"
                                    or report_json["source"]["history_page_sha256"] is None
                                    or report_json["operator_reviewed_source_digests_matched"] is not True
                                    or report_json["limits"]["live_api_called"] is not False):
                                raise AssertionError("HISTORY_UI_GUARD_PROVENANCE_FAILURE")
                            with hist.expect_download(timeout=15000) as history_html_download:
                                hist.get_by_role(
                                    "button", name="오프라인 분석 보고서 HTML",
                                ).click()
                            history_html = Path(history_html_download.value.path()).read_bytes()
                            if (b"PINNED_HISTORY" not in history_html
                                    or b"SEC Historical Page JSON" not in history_html
                                    or report_json["source"]["history_page_sha256"].encode() not in history_html):
                                raise AssertionError("HISTORY_HTML_FOURTH_SOURCE_MISSING")
                            hist.screenshot(
                                path=str(output / "kuodra-local-history-guard.png"),
                                full_page=True,
                            )
                        finally:
                            hist.close()
                        result = {
                            "schema": "kuodra.local-upload-browser-check.v1",
                            "status": "PASS", "uploads": 3, "historical_uploads": 4,
                            "stages": [
                                "explicit-local-text-disclosure",
                                "offline-period-and-needle-choice",
                                "local-source-preview", "ephemeral-guard-HOLD",
                                "four-source-pinned-history-Guard-HOLD",
                                "three-and-four-source-html-evidence",
                                "index-bound-10k-identity-choice",
                                "engine-a-cross-issuer-upload-blocked",
                                "engine-a-real-chromium-upload-decimal-ols",
                                "engine-a-sec-context-json-and-html-download",
                                "engine-a-does-not-change-guard-or-audit",

                            ],
                            "source_authenticated": False,
                            "market_beta": market_card["beta"],
                            "market_upload_sha256": sha256(market_raw).hexdigest(),
                            "market_sec_context_bound": True,
                            "market_guard_policy_modified": False,
                            "market_in_guard_audit": False,
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
