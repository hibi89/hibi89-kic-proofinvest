"""P180 actual Chromium local UI: dual-consent, redacted POST to HTTP emulator.

CI runs on a synthetic reviewer-packet pair. It does NOT run a real LLM or
publish owner files, and forbids all external browser requests.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from proofinvest.ticker_offline_review_builder import build_offline_initial_review
from tests.test_ticker_offline_review_builder import payload

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
URL = "http://127.0.0.1:8584"


class _FakeModel(BaseHTTPRequestHandler):
    posts = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        raw = self.rfile.read(length)
        self.__class__.posts.append((self.path, raw))
        answer = json.dumps({
            "model": "kuodra-ui-test-model", "done": True,
            "response": json.dumps({
                "focus_engine": "B", "decision": "HUMAN_REVIEW_ONLY",
            }),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)


def _ready():
    for _ in range(120):
        try:
            with urllib.request.urlopen(URL + "/_stcore/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("P180_LOCAL_UI_NOT_READY")


def run(output: Path) -> dict:
    from playwright.sync_api import sync_playwright, expect

    fixture = build_offline_initial_review(**payload())
    assert fixture["status"] == "LOCAL_INITIAL_REVIEW_READY_UNVERIFIED"
    output.mkdir(parents=True, exist_ok=True)
    _FakeModel.posts.clear()
    model_server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeModel)
    port = model_server.server_address[1]
    thread = threading.Thread(target=model_server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="kuodra-p180-ui-home-") as home:
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("KUODRA_")}
            env.update({
                "HOME": home, "KUODRA_ENABLE_LOCAL_SOURCE_UI": "1",
                "KUODRA_ENABLE_SEC_FETCH_UI": "0",
                "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
            })
            with (output / "streamlit-local-model-ui.log").open("wb") as log:
                server = subprocess.Popen([
                    sys.executable, "-m", "streamlit", "run", str(APP),
                    "--server.headless=true", "--server.address=127.0.0.1",
                    "--server.port=8584", "--browser.gatherUsageStats=false",
                ], cwd=APP.parent, env=env, stdout=log,
                    stderr=subprocess.STDOUT)
                try:
                    _ready()
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                        try:
                            context = browser.new_context(
                                viewport={"width": 1440, "height": 900})
                            forbidden = []
                            def route_callback(route):
                                url = route.request.url
                                if url == URL or url.startswith(URL + "/"):
                                    route.continue_()
                                else:
                                    forbidden.append(url.split("?")[0][:120])
                                    route.abort()
                            context.route("**/*", route_callback)
                            page = context.new_page()
                            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                            expect(page.get_by_text(
                                "KUODRA — 오프라인 합성 데이터",
                            )).to_be_visible(timeout=25000)
                            page.get_by_test_id("stSelectbox").first.click()
                            page.get_by_role("option",
                                name="KUODRA · 종목 1개 검색 (로컬 전용)", exact=True,
                            ).click()
                            expect(page.get_by_text(
                                "로컬 AI 검토 우선순위 · 별도 실행 (실제 모델 미검증)",
                                exact=True,
                            )).to_be_visible(timeout=25000)
                            pane = page.get_by_text(
                                "로컬 AI 선택 기능 펼치기 (기본 비활성)", exact=True,
                            )
                            pane.click()
                            submit = page.get_by_role(
                                "button",
                                name="A/B/C 로컬 AI 검토 우선순위 요청 (명시적 1회)",
                                exact=True,
                            )
                            expect(submit).to_be_disabled(timeout=12000)
                            def upload(label, name, data):
                                widget = page.get_by_test_id("stFileUploader").filter(
                                    has=page.get_by_text(label, exact=True),
                                ).locator('input[type="file"]')
                                widget.set_input_files({
                                    "name": name, "mimeType": "application/json",
                                    "buffer": data,
                                })
                                expect(page.get_by_role(
                                    "button", name="Remove " + name, exact=True,
                                )).to_be_visible(timeout=22000)
                            review_label = "로컬 AI 입력용 A/B/C 검토 패킷 JSON (미인증)"
                            rights_label = "로컬 AI 입력용 권리 미확인표 JSON (미인증)"
                            upload(review_label, "p180-review.json", fixture["review_packet"])
                            upload(rights_label, "p180-rights.json", fixture["source_clearance_report"])
                            expect(submit).to_be_disabled(timeout=12000)
                            assert not _FakeModel.posts
                            page.get_by_label(
                                "로컬 AI 모델 이름 (사용자 설치 모델)", exact=True,
                            ).fill("kuodra-ui-test-model")
                            local_port = page.get_by_label(
                                "로컬 AI 서버 포트 (1024~65535)", exact=True,
                            )
                            local_port.fill(str(port))
                            local_port.press("Tab")
                            page.get_by_text(
                                "127.0.0.1의 본인 관리 모델 서버임을 확인했습니다 (원격 중계 사용 금지)",
                                exact=True,
                            ).click()
                            expect(submit).to_be_disabled(timeout=12000)
                            assert not _FakeModel.posts
                            page.get_by_text(
                                "원본이 아닌 A/B/C 미인증 상태 코드만 로컬 모델로 전달하는 데 동의합니다",
                                exact=True,
                            ).click()
                            expect(submit).to_be_enabled(timeout=15000)
                            assert not _FakeModel.posts
                            submit.click()
                            expect(page.get_by_text(
                                "로컬 모델 선택 프로토콜 PASS (실제 모델 추론 미검증)",
                                exact=True,
                            )).to_be_visible(timeout=22000)
                            expect(page.get_by_text(
                                "검토 상태: HOLD",
                                exact=True,
                            )).to_have_count(0)  # Don't mistake static HTML for auth.
                            assert len(_FakeModel.posts) == 1
                            endpoint, body = _FakeModel.posts[0]
                            assert endpoint == "/api/generate"
                            prompt = json.loads(body)["prompt"]
                            for forbidden_text in (
                                "NVDA", "companyfacts", "source_hashes",
                                "accession", "http://", "apikey", "10-K",
                            ):
                                assert forbidden_text not in prompt
                            page.screenshot(path=str(output / "p180-consented-local-protocol.png"),
                                            full_page=True)
                            # Alter reviewed bytes: fail before POST, clear old success.
                            upload(review_label, "p180-tampered.json",
                                   fixture["review_packet"] + b" ")
                            expect(page.get_by_text(
                                "로컬 모델 선택 프로토콜 PASS (실제 모델 추론 미검증)",
                                exact=True,
                            )).to_have_count(0, timeout=22000)
                            submit.click()
                            expect(page.get_by_text(
                                "REVIEW_PACKET_OR_CLEARANCE_INVALID",
                                exact=True,
                            )).to_be_visible(timeout=22000)
                            assert len(_FakeModel.posts) == 1

                            # P186: true click-through of the separate
                            # offline numeric draft verifier (NO second POST).
                            page.get_by_text(
                                "오프라인 AI 수치 대조 열기 (기본 비활성)",
                                exact=True,
                            ).click()
                            numeric_submit = page.get_by_role(
                                "button",
                                name="오프라인 수치 일치 검증 (외부 API 없음)",
                                exact=True,
                            )
                            expect(numeric_submit).to_be_disabled(timeout=12000)
                            review_label2 = "수치 대조 A/B/C 검토 패킷 JSON (미인증)"
                            rights_label2 = "수치 대조 권리 미확인표 JSON (미인증)"
                            draft_label = "수치 대조 AI 초안 JSON (모델 원문 아님)"
                            upload(review_label2, "p186-review.json",
                                   fixture["review_packet"])
                            upload(rights_label2, "p186-rights.json",
                                   fixture["source_clearance_report"])
                            expect(numeric_submit).to_be_disabled(timeout=12000)
                            review_obj = json.loads(fixture["review_packet"])
                            correct_gap = review_obj["explanation"]["findings"][0][
                                "simple_return_gap_pp"]
                            numeric_draft = {
                                "schema": "kuodra.local-model-numeric-claim.v1",
                                "engine": "A",
                                "claim_kind": "OBSERVED_PRICE_RETURN_GAP_PP",
                                "gap_pp": correct_gap,
                                "decision": "HUMAN_REVIEW_ONLY",
                            }
                            upload(draft_label, "p186-valid-draft.json",
                                   json.dumps(numeric_draft).encode())
                            expect(numeric_submit).to_be_enabled(timeout=15000)
                            assert len(_FakeModel.posts) == 1
                            numeric_submit.click()
                            expect(page.get_by_text(
                                "로컬 수익률 차이 Decimal 재검산 PASS (발행기관·이용권한 미인증)",
                                exact=True,
                            )).to_be_visible(timeout=22000)
                            page.screenshot(
                                path=str(output / "p186-numeric-review-verified.png"),
                                full_page=True)
                            assert len(_FakeModel.posts) == 1
                            numeric_draft["gap_pp"] = "999.9999"
                            upload(draft_label, "p186-invalid-draft.json",
                                   json.dumps(numeric_draft).encode())
                            expect(page.get_by_text(
                                "로컬 수익률 차이 Decimal 재검산 PASS (발행기관·이용권한 미인증)",
                                exact=True,
                            )).to_have_count(0, timeout=22000)
                            numeric_submit.click()
                            expect(page.get_by_text(
                                "MODEL_NUMERIC_CLAIM_NOT_SUPPORTED", exact=True,
                            )).to_be_visible(timeout=22000)
                            assert len(_FakeModel.posts) == 1
                            assert not forbidden
                        finally:
                            browser.close()
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=8)
    finally:
        model_server.shutdown()
        model_server.server_close()
        thread.join(timeout=2)
    return {
        "status": "PASS",
        "synthetic_packet_only": True,
        "explicit_dual_consent_required": True,
        "actual_browser_clicked": True,
        "localhost_http_emulator_calls": len(_FakeModel.posts),
        "real_model_executed": False,
        "source_rights_verified": False,
        "trade_executed": False,
        "external_browser_requests": 0,
    }


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = run(args.output)
    (args.output / "p180-local-model-browser.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
