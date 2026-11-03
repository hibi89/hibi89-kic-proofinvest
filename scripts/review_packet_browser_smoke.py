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
from tests.test_ticker_market_pair_evidence import _build, _prepared, _body

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
                            accept_downloads=True,
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
                        # P166: actual Chromium full original-byte replay,
                        # not merely the cached packet's internal checksum.
                        upload("p166-complete-review.json", raw)
                        mode = page.get_by_text(
                            "원본 SEC·주가·NDX 파일로 독립 산술 재검산 펼치기 (로컬 전용)",
                            exact=True,
                        )
                        mode.click()
                        verifier = page.get_by_role(
                            "button",
                            name="원본 SEC + 주가·NDX A/B/C 독립 재계산 (네트워크 없음)",
                            exact=True,
                        )
                        expect(verifier).to_be_disabled(timeout=12000)

                        _, sec_sources, market, industry, _, _ = _prepared()
                        def upload_original(label, name, payload):
                            widget = page.get_by_test_id("stFileUploader").filter(
                                has=page.get_by_text(label, exact=True),
                            ).locator('input[type="file"]')
                            expect(widget).to_have_count(1, timeout=12000)
                            widget.set_input_files({
                                "name": name,
                                "mimeType": "application/json",
                                "buffer": payload,
                            })
                            expect(page.get_by_role(
                                "button", name="Remove " + name, exact=True,
                            )).to_be_visible(timeout=22000)

                        originals = (
                            ("원본 SEC ticker_map JSON (재검산)", "p166-map.json",
                             sec_sources["ticker_map"]),
                            ("원본 SEC submissions JSON (재검산)", "p166-submissions.json",
                             sec_sources["submissions"]),
                            ("원본 SEC CompanyFacts JSON (재검산)", "p166-facts.json",
                             sec_sources["companyfacts"]),
                            ("원본 SEC 10-K HTML (재검산)", "p166-original.xhtml",
                             sec_sources["original_10k"]),
                            ("종목 일별 응답 JSON 원본 (재검산)", "p166-stock.json",
                             _body("NVDA")),
                            ("실제 Nasdaq-100 NDX 일별 응답 JSON 원본 (재검산)",
                             "p166-ndx.json", _body("NDX", 10000)),
                            ("기존 Engine A 로컬 입력 JSON (패키지에 포함된 경우 필수)",
                             "p166-market.json", market),
                            ("기존 Engine C 로컬 입력 JSON (패키지에 포함된 경우 필수)",
                             "p166-industry.json", industry),
                        )
                        for label, name, payload in originals:
                            upload_original(label, name, payload)
                        expect(verifier).to_be_enabled(timeout=22000)
                        verifier.click()
                        expect(page.get_by_text(
                            "원본 6종 해시 + SEC/Engine A/B/C 산술 재계산 PASS (출처 미인증)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        expect(page.get_by_text(
                            "EXACT_ORIGINAL_BYTES_HASH_MISMATCH", exact=True,
                        )).to_have_count(0)
                        page.screenshot(
                            path=str(output / "p166-valid-source-browser.png"),
                            full_page=True,
                        )
                        # Even a whitespace-only changed market source is a
                        # different exact byte input, so replay must fail.
                        upload_original(
                            "종목 일별 응답 JSON 원본 (재검산)",
                            "p166-tampered-stock.json", _body("NVDA") + b" ",
                        )
                        expect(page.get_by_text(
                            "원본 6종 해시 + SEC/Engine A/B/C 산술 재계산 PASS (출처 미인증)",
                            exact=True,
                        )).to_have_count(0, timeout=22000)
                        verifier.click()
                        expect(page.get_by_text(
                            "EXACT_ORIGINAL_BYTES_HASH_MISMATCH", exact=True,
                        )).to_be_visible(timeout=22000)
                        page.screenshot(
                            path=str(output / "p166-rejected-source-browser.png"),
                            full_page=True,
                        )
                        # P167: produce the FIRST A/B/C review packet
                        # using caller-supplied SEC + true NDX provider-shape
                        # bytes; NO paid API permission or prior packet.
                        date_input = page.get_by_label(
                            "조회 기준일 (YYYY-MM-DD)", exact=True,
                        )
                        date_input.fill("2026-02-01")
                        date_input.press("Tab")
                        expect(date_input).to_have_value("2026-02-01")
                        initial_button = page.get_by_role(
                            "button",
                            name=("로컬 SEC + 종목·실제 NDX A/B/C 통합 "
                                  "검토 파일 생성 (외부 요청 0회)"),
                            exact=True,
                        )
                        expect(initial_button).to_be_disabled()
                        for label, name, payload in (
                            ("SEC ticker 목록 JSON (로컬 선택)", "p167-map.json",
                             sec_sources["ticker_map"]),
                            ("선택 기업 SEC submissions.json (선택)",
                             "p167-submissions.json", sec_sources["submissions"]),
                            ("CompanyFacts JSON (로컬 검산용 선택)",
                             "p167-companyfacts.json", sec_sources["companyfacts"]),
                            ("동일 10-K 원문 HTML/XHTML (로컬 문맥 검토용 선택)",
                             "p167-original.xhtml", sec_sources["original_10k"]),
                            ("주가·지수 시계열 JSON (개발·검증용 선택)",
                             "p167-market.json", market),
                            ("산업·경쟁사 비교 JSON (개발·검증용 선택)",
                             "p167-industry.json", industry),
                            ("종목 일별 종가 응답 JSON (로컬 분석 전용)",
                             "p167-stock.json", _body("NVDA")),
                            ("Nasdaq-100 NDX 일별 지수 응답 JSON (로컬 분석 전용)",
                             "p167-ndx.json", _body("NDX", 10000)),
                        ):
                            upload_original(label, name, payload)
                        page.get_by_text(
                            "로컬 계산만 수행하며 원본 진위·재사용권·투자 승인으로 취급하지 않습니다",
                            exact=True,
                        ).click()
                        expect(initial_button).to_be_enabled(timeout=22000)
                        expect(page.get_by_role(
                            "button",
                            name="로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)",
                            exact=True,
                        )).to_have_count(0)
                        initial_button.click()
                        expect(page.get_by_text(
                            "SEC 4원본 + 종목·실제 NDX 오프라인 재계산 PASS (출처 미인증)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=20000) as download:
                            page.get_by_role(
                                "button",
                                name="로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)",
                                exact=True,
                            ).click()
                        packet_download = download.value
                        if packet_download.suggested_filename != (
                                "kuodra-offline-a-b-c-review-UNVERIFIED.json"):
                            raise AssertionError("P167_PACKET_FILENAME_MISMATCH")
                        from proofinvest.ticker_review_packet import inspect_review_packet_bytes
                        downloaded_packet = Path(packet_download.path()).read_bytes()
                        receipt = inspect_review_packet_bytes(downloaded_packet)
                        if (receipt["status"] !=
                                "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"
                                or receipt["ticker"] != "NVDA"):
                            raise AssertionError("P167_PACKET_CONTRACT_INVALID")
                        # P168 real Chromium: a *separate*, redacted
                        # original-input hash and legal-rights gap sheet.
                        with page.expect_download(timeout=20000) as gaps:
                            page.get_by_role(
                                "button",
                                name="원본·이용권한 미확인 항목 JSON 다운로드 (승인 아님)",
                                exact=True,
                            ).click()
                        gap_download = gaps.value
                        if gap_download.suggested_filename != (
                                "kuodra-source-rights-GAPS-UNVERIFIED.json"):
                            raise AssertionError("P168_CLEARANCE_FILENAME_INVALID")
                        from proofinvest.ticker_source_clearance_packet import (
                            inspect_source_clearance_packet,
                        )
                        rights_bytes = Path(gap_download.path()).read_bytes()
                        match = inspect_source_clearance_packet(
                            rights_bytes, review_packet=downloaded_packet,
                        )
                        rights = json.loads(rights_bytes)
                        if (
                            match["status"] !=
                                "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING"
                            or match["source_rights_verified"] is not False
                            or len(rights["files"]) != 8
                            or rights["guard_policy_preview"] != "HOLD"
                            or rights["external_sharing_allowed"] is not False
                            or rights["contest_submission_approved"] is not False
                            or b"close_observations" in rights_bytes
                        ):
                            raise AssertionError("P168_RIGHTS_GAP_REPORT_INVALID")
                        page.screenshot(
                            path=str(output / "p168-rights-gaps-browser.png"),
                            full_page=True,
                        )
                        page.screenshot(
                            path=str(output / "p167-first-offline-packet-browser.png"),
                            full_page=True,
                        )
                        # Invalid benchmark metadata MUST NOT silently use an
                        # S&P500 response as the actual Nasdaq-100.
                        upload_original(
                            "Nasdaq-100 NDX 일별 지수 응답 JSON (로컬 분석 전용)",
                            "p167-wrong-index.json", _body("SPX", 10000),
                        )
                        expect(page.get_by_role(
                            "button",
                            name="로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)",
                            exact=True,
                        )).to_have_count(0, timeout=22000)
                        initial_button.click()
                        expect(page.get_by_text(
                            "INVALID_SOURCE_OR_MARKET_RESPONSE", exact=True,
                        )).to_be_visible(timeout=22000)
                        page.screenshot(
                            path=str(output / "p167-wrong-index-blocked-browser.png"),
                            full_page=True,
                        )
                        # P169: switch the same real Chromium session
                        # from the provider-shape JSON file pair to a strict
                        # locally supplied CSV pair, with *no vendor GET*.
                        page.get_by_role(
                            "button", name="Remove p167-stock.json", exact=True,
                        ).click()
                        page.get_by_role(
                            "button", name="Remove p167-wrong-index.json", exact=True,
                        ).click()
                        expect(initial_button).to_be_disabled(timeout=15000)

                        from tests.test_local_market_csv_bridge import local_csv
                        def upload_csv(label, name, contents):
                            holder = page.get_by_test_id("stFileUploader").filter(
                                has=page.get_by_text(label, exact=True),
                            ).locator('input[type="file"]')
                            expect(holder).to_have_count(1, timeout=15000)
                            holder.set_input_files({
                                "name": name,
                                "mimeType": "text/csv",
                                "buffer": contents,
                            })
                            expect(page.get_by_role(
                                "button", name="Remove " + name, exact=True,
                            )).to_be_visible(timeout=22000)

                        upload_csv(
                            "종목 일별 CSV (JSON 대신, 원본 미인증)",
                            "p169-nvda-source.csv", local_csv("NVDA"),
                        )
                        upload_csv(
                            "Nasdaq-100 NDX 일별 CSV (JSON 대신, 원본 미인증)",
                            "p169-ndx-source.csv", local_csv("NDX", 10000),
                        )
                        expect(initial_button).to_be_enabled(timeout=22000)
                        initial_button.click()
                        expect(page.get_by_text(
                            "SEC 4원본 + 종목·실제 NDX 오프라인 재계산 PASS (출처 미인증)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=20000) as local_review:
                            page.get_by_role(
                                "button",
                                name="로컬 A/B/C 검토 패키지 JSON 다운로드 (미인증)",
                                exact=True,
                            ).click()
                        csv_review_bytes = Path(local_review.value.path()).read_bytes()
                        if inspect_review_packet_bytes(csv_review_bytes)["status"] != (
                                "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"):
                            raise AssertionError("P169_CSV_REVIEW_PACKET_INVALID")
                        with page.expect_download(timeout=20000) as lineage:
                            page.get_by_role(
                                "button",
                                name="로컬 CSV 원본·JSON 변환 이력 JSON 다운로드 (미인증)",
                                exact=True,
                            ).click()
                        lineage_bytes = Path(lineage.value.path()).read_bytes()
                        from proofinvest.local_market_csv_bridge import (
                            inspect_csv_lineage_receipt,
                        )
                        csv_check = inspect_csv_lineage_receipt(
                            lineage_bytes, packet=csv_review_bytes,
                        )
                        if (csv_check["status"] != "CSV_LINEAGE_MATCHED_RIGHTS_PENDING"
                                or csv_check["source_rights_verified"] is not False
                                or b"close_observations" in lineage_bytes):
                            raise AssertionError("P169_ORIGINAL_CSV_LINEAGE_NOT_SAFE")
                        # P170: download and actually render the human-readable
                        # printable HTML from the same validated synthetic
                        # CSV-backed report + source rights and lineage.
                        with page.expect_download(timeout=20000) as csv_gap:
                            page.get_by_role(
                                "button",
                                name="원본·이용권한 미확인 항목 JSON 다운로드 (승인 아님)",
                                exact=True,
                            ).click()
                        csv_gap_bytes = Path(csv_gap.value.path()).read_bytes()
                        with page.expect_download(timeout=20000) as html_d:
                            page.get_by_role(
                                "button",
                                name="단일 종목 A/B/C HTML 보고서 다운로드 (오프라인·미인증)",
                                exact=True,
                            ).click()
                        html_download = html_d.value
                        if html_download.suggested_filename != (
                                "kuodra-single-ticker-review-UNVERIFIED.html"):
                            raise AssertionError("P170_HTML_FILENAME_INVALID")
                        downloaded_html = Path(html_download.path()).read_bytes()
                        from proofinvest.ticker_reviewer_html import render_reviewer_html
                        expected_html = render_reviewer_html(
                            review_packet=csv_review_bytes,
                            rights_gap_report=csv_gap_bytes,
                            csv_lineage=lineage_bytes,
                        )
                        if (downloaded_html != expected_html
                                or b"Content-Security-Policy" not in downloaded_html
                                or b"<script" in downloaded_html.lower()
                                or b"close_observations" in downloaded_html):
                            raise AssertionError("P170_HTML_SOURCE_LINK_OR_SAFETY_INVALID")
                        report_tab = context.new_page()
                        report_tab.set_content(
                            downloaded_html.decode("utf-8"),
                            wait_until="load", timeout=20000,
                        )
                        expect(report_tab.get_by_role(
                            "heading", name="NVDA · 1종목 근거 검토",
                        )).to_be_visible(timeout=15000)
                        for engine in ("시장·가격 비교 / Engine A",
                                       "회계·현금흐름 / Engine B",
                                       "동종기업·산업 / Engine C"):
                            expect(report_tab.get_by_role(
                                "heading", name=engine, exact=True,
                            )).to_be_visible(timeout=15000)
                        expect(report_tab.get_by_text(
                            "검토 상태: HOLD", exact=False,
                        )).to_be_visible()
                        report_tab.screenshot(
                            path=str(output / "p170-printable-a-b-c-report-chromium.png"),
                            full_page=True,
                        )
                        report_tab.close()
                        # P171: one-click reviewer bundle must contain the
                        # same exact packet, gap receipt and rendered HTML.
                        with page.expect_download(timeout=20000) as bundle_dl:
                            page.get_by_role(
                                "button",
                                name="단일 종목 근거 묶음 ZIP 다운로드 (로컬·미인증)",
                                exact=True,
                            ).click()
                        bundle = bundle_dl.value
                        if bundle.suggested_filename != (
                                "kuodra-review-evidence-UNVERIFIED.zip"):
                            raise AssertionError("P171_REVIEW_BUNDLE_FILENAME_INVALID")
                        from proofinvest.ticker_review_bundle import (
                            inspect_review_bundle_bytes,
                        )
                        import zipfile
                        from io import BytesIO
                        bundle_bytes = Path(bundle.path()).read_bytes()
                        bundle_receipt = inspect_review_bundle_bytes(bundle_bytes)
                        if (bundle_receipt["status"] !=
                                "INTERNAL_CONTENT_VERIFIED_ORIGIN_RIGHTS_PENDING"
                                or bundle_receipt["files_verified"] != 4
                                or bundle_receipt["source_rights_verified"] is not False
                                or bundle_receipt["contest_submission_approved"] is not False):
                            raise AssertionError("P171_BUNDLE_INSPECTOR_INVALID")
                        with zipfile.ZipFile(BytesIO(bundle_bytes)) as saved:
                            if (saved.read("review-packet.json") != csv_review_bytes
                                    or saved.read("source-rights-GAPS.json") !=
                                        csv_gap_bytes
                                    or saved.read("market-csv-lineage.json") !=
                                        lineage_bytes
                                    or saved.read("single-ticker-review.html") !=
                                        downloaded_html):
                                raise AssertionError("P171_REVIEW_BUNDLE_CONTENT_MISMATCH")
                        page.screenshot(
                            path=str(output / "p171-evidence-bundle-browser.png"),
                            full_page=True,
                        )
                        page.screenshot(
                            path=str(output / "p169-stock-ndx-csv-replay-browser.png"),
                            full_page=True,
                        )

                        upload_csv(
                            "Nasdaq-100 NDX 일별 CSV (JSON 대신, 원본 미인증)",
                            "p169-wrong-qqq.csv", local_csv("QQQ", 10000),
                        )
                        expect(page.get_by_role(
                            "button",
                            name="로컬 CSV 원본·JSON 변환 이력 JSON 다운로드 (미인증)",
                            exact=True,
                        )).to_have_count(0, timeout=22000)
                        initial_button.click()
                        expect(page.get_by_text(
                            "LOCAL_SOURCE_FILE_READ_INVALID", exact=True,
                        )).to_be_visible(timeout=22000)
                        page.screenshot(
                            path=str(output / "p169-wrong-index-csv-blocked-browser.png"),
                            full_page=True,
                        )
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
        "synthetic_original_sec_and_price_replayed_in_browser": True,
        "tampered_original_blocked_in_browser": True,
        "initial_offline_review_packet_generated_and_downloaded": True,
        "initial_review_wrong_index_rejected": True,
        "source_clearance_gap_json_real_browser_downloaded": True,
        "local_csv_original_to_normalized_json_review_downloaded": True,
        "csv_lineage_packet_hash_verified": True,
        "qqq_csv_as_ndx_blocked": True,
        "printable_report_html_downloaded_and_rendered_in_chromium": True,
        "html_exact_review_rights_and_csv_lineage_bound": True,
        "html_external_content_and_source_rows_absent": True,
        "single_zip_downloaded_actual_chromium": True,
        "bundle_contains_exact_review_rights_html_lineage": True,
        "bundle_no_rights_or_trade_grants": True,
        "rights_report_bound_to_exact_review_packet": True,
        "source_and_license_rights_remain_unverified": True,
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
