"""P221: real Chromium upload of synthetic local market JSON linked to pinned NVDA facts.

Only loopback browser traffic is allowed. No SEC, market vendor, AI or paid
service is called; browser outputs carry no raw prices or API credentials.
"""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from proofinvest.real_issuer_local_market import verify_derived_ab_checksum
from proofinvest.real_issuer_ticker_review import review_supported_real_ticker

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
URL = "http://127.0.0.1:8589"
MODE = "KUODRA · 실제 발행사 종목 직접 입력 (2종 · 제한)"


def vendor_form(symbol: str, base: int) -> bytes:
    # Synthetic prices; genuine first-party publisher GAAP receipts are separate.
    day = date(2026, 8, 18)
    rows = {}
    i = 0
    while day <= date(2026, 11, 4):
        if day.weekday() < 5:
            rows[day.isoformat()] = {
                "4. close": str(base + i * 2 + (i % 5) * 3)
            }
            i += 1
        day += timedelta(days=1)
    return json.dumps({
        "Meta Data": {"2. Symbol": symbol},
        "Time Series (Daily)": rows,
    }, separators=(",", ":")).encode("utf-8")


def _ready() -> None:
    for _ in range(120):
        try:
            with urlopen(URL + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("P221_LOCAL_STREAMLIT_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    stock = vendor_form("NVDA", 120)
    index = vendor_form("NDX", 10000)
    with TemporaryDirectory(prefix="kuodra-p221-browser-home-") as home:
        env = dict(os.environ)
        env.update({
            "HOME": home,
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
            "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
        })
        with (output / "p221-streamlit.log").open("wb") as server_log:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(APP),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 "--server.port=8589", "--browser.gatherUsageStats=false"],
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

                        def local_only(route):
                            hostname = urlsplit(route.request.url).hostname
                            if hostname not in ("127.0.0.1", "localhost"):
                                blocked_external.append(hostname or "unknown")
                                route.abort()
                            else:
                                route.continue_()

                        context.route("**/*", local_only)
                        page = context.new_page()
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text(
                            "KUODRA — 오프라인 합성 데이터",
                        )).to_be_visible(timeout=25000)
                        page.get_by_test_id("stSelectbox").first.click()
                        page.get_by_role(
                            "option", name=MODE, exact=True).click()
                        expect(page.get_by_role(
                            "heading",
                            name="KUODRA · 종목 입력 → 실제 발행사 제한 재무검토",
                        )).to_be_visible(timeout=25000)
                        # Streamlit text_input commits on Enter/blur, not
                        # necessarily on Playwright fill() alone. Trigger the
                        # actual user commit before expecting upload controls.
                        ticker_input = page.get_by_label(
                            "미국 종목코드 입력 (NVDA 또는 DELL)",
                            exact=True,
                        )
                        ticker_input.fill("NVDA")
                        ticker_input.press("Enter")
                        expect(page.get_by_role(
                            "heading",
                            name="Engine A · 로컬 종목 주가 + 실제 NDX 종목코드 형식 검산",
                        )).to_be_visible(timeout=25000)
                        # Independent P222 real audited AMD 10-K + issuer
                        # press-release comparison must be visible and
                        # downloadable in the same genuine ticker UI.
                        expect(page.get_by_role(
                            "heading",
                            name="Engine C · AMD 공식 10-K 감사 재무 교차검산 (단일 동종기업)",
                        )).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=30000) as peer_event:
                            page.get_by_role(
                                "button",
                                name="AMD 10-K 교차검산 개인용 JSON (이용권 미인증)",
                                exact=True,
                            ).click()
                        peer_download = peer_event.value
                        if peer_download.suggested_filename != (
                                "kuodra-nvda-amd-audited-peer-UNVERIFIED.json"):
                            raise AssertionError("P222_PEER_FILENAME_MISMATCH")
                        peer_report = json.loads(
                            Path(peer_download.path()).read_bytes())
                        if (peer_report["status"] !=
                                "ONE_REAL_AUDITED_10K_PEER_CROSSCHECK_ONLY"
                                or peer_report["amd_filing_accession"] !=
                                   "0000002488-26-000018"
                                or peer_report["amd_two_independent_official_documents_reconciled"] is not True
                                or peer_report["amd_gaap_net_margin_2025_pct"] != "12.51"
                                or peer_report["observed_growth_gap_pp_not_sector_rank"] != "31.14"
                                or peer_report["peer_rights_verified"] is not False
                                or peer_report["engine_c_complete"] is not False
                                or peer_report["guard_policy_preview"] != "HOLD"):
                            raise AssertionError("P222_REAL_PEER_FILING_REPLAY_MISMATCH")
                        # P223: independent second audited issuer (Intel)
                        # and previously verified AMD join to genuine NVDA.
                        expect(page.get_by_role(
                            "heading",
                            name="Engine C · NVIDIA / AMD / Intel 3개사 원문 비교 (제한)",
                        )).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=30000) as cohort_event:
                            page.get_by_role(
                                "button",
                                name="NVDA·AMD·INTC 2개 동종기업 교차검산 JSON (제한)",
                                exact=True,
                            ).click()
                        cohort_download = cohort_event.value
                        if cohort_download.suggested_filename != (
                                "kuodra-nvda-two-official-peers-UNVERIFIED.json"):
                            raise AssertionError("P223_COHORT_DOWNLOAD_FILENAME_INVALID")
                        cohort_report = json.loads(
                            Path(cohort_download.path()).read_bytes())
                        if (cohort_report["status"] !=
                                "TWO_DISTINCT_AUDITED_PEER_REFERENCES_LIMITED"
                                or cohort_report["peer_count"] != 2
                                or [x["ticker"] for x in cohort_report["revenue_growth_observations_not_sector_rank"]]
                                   != ["NVDA", "AMD", "INTC"]
                                or cohort_report["intel_filing_accession"] !=
                                   "0000050863-26-000011"
                                or cohort_report["intel_2025_revenue_usdm"] != "52853"
                                or cohort_report["intel_2025_gross_margin_pct"] != "34.77"
                                or cohort_report["observed_nvda_minus_intc_growth_pp"] != "65.94"
                                or cohort_report["peer_rights_verified"] is not False
                                or cohort_report["representative_peers_verified"] is not False
                                or cohort_report["engine_c_complete"] is not False
                                or cohort_report["guard_policy_preview"] != "HOLD"):
                            raise AssertionError("P223_TWO_PEER_AUDITED_FINANCIAL_REPLAY_FAILED")
                        uploader = page.locator('input[type="file"]')
                        expect(uploader).to_have_count(2, timeout=25000)
                        uploader.nth(0).set_input_files({
                            "name": "synthetic-nvda.json",
                            "mimeType": "application/json",
                            "buffer": stock,
                        })
                        uploader.nth(1).set_input_files({
                            "name": "synthetic-ndx.json",
                            "mimeType": "application/json",
                            "buffer": index,
                        })
                        ack = page.get_by_role(
                            "checkbox",
                            name="내 로컬 파일로 미인증 산술검산만 진행하며 외부 재배포·투자 승인하지 않음",
                            exact=True,
                        )
                        expect(ack).not_to_be_checked()
                        ack.focus()
                        ack.press("Space")
                        expect(ack).to_be_checked(timeout=20000)
                        page.get_by_role(
                            "button",
                            name="실제 발행사 자료와 주가/NDX 계산 연결 (네트워크 0)",
                            exact=True,
                        ).click()
                        expect(page.get_by_text(
                            "실제 발행사 Engine B + 로컬 Engine A 결합 (시장 미인증)",
                            exact=True,
                        )).to_be_visible(timeout=25000)
                        download_button = page.get_by_role(
                            "button",
                            name="발행사 재무 B + 로컬 시장 A 결합 JSON (원본·API키 제외)",
                            exact=True,
                        )
                        expect(download_button).to_be_visible(timeout=20000)
                        with page.expect_download(timeout=30000) as event:
                            download_button.click()
                        download = event.value
                        if (download.suggested_filename !=
                                "kuodra-nvda-ab-UNVERIFIED.json"):
                            raise AssertionError("P221_WRONG_DOWNLOAD_FILENAME")
                        raw = Path(download.path()).read_bytes()
                        report = json.loads(raw)
                        real = review_supported_real_ticker("NVDA")
                        if (not verify_derived_ab_checksum(report)
                                or report["ticker"] != "NVDA"
                                or report["issuer_source_sha256"] !=
                                   real["source_sha256"]
                                or report["engine_b"]["revenue_growth_pct"] !=
                                   real["issuer_revenue_growth_pct"]
                                or report["engine_b"]["fiscal_latest_end"] !=
                                   real["fiscal_latest_end"]
                                or report["local_stock_sha256"] != sha256(stock).hexdigest()
                                or report["local_ndx_sha256"] != sha256(index).hexdigest()
                                or report["guard_policy_preview"] != "HOLD"
                                or report["trade_executed"] is not False
                                or report["market_rights_verified"] is not False
                                or report["full_abc_complete"] is not False
                                or "Time Series (Daily)" in raw.decode("utf-8")
                                or "4. close" in raw.decode("utf-8")):
                            raise AssertionError("P221_REVIEW_PROVENANCE_OR_SAFETY_FAILED")
                        # P224: after the actual operator A/B files and
                        # two audited peer reviews, download ONE A/B/C packet.
                        from proofinvest.real_issuer_abc_local_review import (
                            replay_partial_source_bound_abc,
                        )
                        expect(page.get_by_role(
                            "heading",
                            name="A/B/C · 발행사·로컬 시장·AMD/Intel 출처결합 검산 (제한)",
                        )).to_be_visible(timeout=25000)
                        with page.expect_download(timeout=30000) as abc_event:
                            page.get_by_role(
                                "button",
                                name="실제 발행사 A/B/C 제한 결합 JSON (출처·이용권 미인증)",
                                exact=True,
                            ).click()
                        abc_download=abc_event.value
                        if abc_download.suggested_filename != (
                                "kuodra-nvda-partial-abc-UNVERIFIED.json"):
                            raise AssertionError("P224_ABC_FILENAME_INVALID")
                        abc_bytes=Path(abc_download.path()).read_bytes()
                        abc=json.loads(abc_bytes)
                        if (not replay_partial_source_bound_abc(abc)
                                or abc["engine_ab_partial"]!=report
                                or abc["source_linked_issuer_sha256"]!=real["source_sha256"]
                                or abc["engine_c_partial"]["peer_count"]!=2
                                or abc["engine_c_partial"]["nvda_minus_intc_growth_pp"]!="65.94"
                                or abc["stock_uploaded_sha256"]!=sha256(stock).hexdigest()
                                or abc["ndx_uploaded_sha256"]!=sha256(index).hexdigest()
                                or abc["guard_policy_preview"]!="HOLD"
                                or abc["full_abc_complete"] is not False
                                or abc["market_rights_verified"] is not False
                                or abc["peer_rights_verified"] is not False
                                or abc["trade_executed"] is not False
                                or '"Time Series (Daily)"' in abc_bytes.decode("utf-8")):
                            raise AssertionError("P224_ABC_REPLAY_FAILED")
                        page.screenshot(
                            path=str(output / "p221-ab-review.png"),
                            full_page=False)
                        receipt = {
                            "status": "PASS",
                            "scenario": "P221_REAL_ISSUER_SYNTHETIC_LOCAL_PRICE_JOIN",
                            "actual_streamlit_download": True,
                            "joined_ab_checksum_valid": True,
                            "issuer_source_sha256": report["issuer_source_sha256"],
                            "download_sha256": sha256(raw).hexdigest(),
                            "guard_preview": "HOLD",
                            "stock_ndx_issuer_bound": True,
                            "amd_audited_10k_peer_download_verified": True,
                            "amd_official_10k_and_press_crosschecked": True,
                            "two_distinct_audited_10k_peers_download_verified": True,
                            "intel_official_10k_and_release_crosschecked": True,
                            "single_abc_download_and_replay_verified": True,
                            "market_rights_verified": False,
                            "sec_raw_bytes_verified": False,
                            "trade_executed": False,
                            "external_http_allowed": False,
                            "external_attempts_blocked": len(blocked_external),
                        }
                        (output / "p221-browser-receipt.json").write_text(
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
            "Usage: python -m scripts.real_issuer_ab_browser_smoke OUTPUT_DIR")
    print(json.dumps(run(Path(sys.argv[1])), ensure_ascii=False, sort_keys=True))
