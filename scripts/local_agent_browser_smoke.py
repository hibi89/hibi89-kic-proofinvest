"""P314 actual Chromium clicks the new fictional KUODRA Agent mode.

Accepts NO real files. All browser traffic is loopback only, SEC/API/LLM
calls are forbidden, no persistent audit database and no live KIC data.
Run: python -B -m scripts.local_agent_browser_smoke /tmp/kic-p314-agent
"""
from __future__ import annotations

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

from proofinvest.kuodra_review_report import _canonical

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "streamlit_app.py"
MODE = "KUODRA · Agent 질문 → SEC/ML/Guard (합성 검증)"
URL = "http://127.0.0.1:8594"
OUTPUT_NAME = "p314-local-agent-browser-receipt.json"
_ALLOWED_HOSTS = frozenset(("127.0.0.1", "localhost"))


def _ready() -> None:
    for _ in range(120):
        try:
            with urlopen(URL + "/_stcore/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("P314_LOCAL_STREAMLIT_HEALTH_FAILED")


def _verify_download(download, *, mode: str, decision: str) -> dict:
    """Independently inspect actual browser-downloaded restricted JSON bytes."""
    if download.suggested_filename != "kuodra-fictional-agent-review.json":
        raise AssertionError("P314_WRONG_DOWNLOAD_FILENAME")
    payload = Path(download.path()).read_bytes()
    if not payload.endswith(b"\n") or len(payload) > 32_768:
        raise AssertionError("P314_DOWNLOAD_ENCODING_OR_SIZE_INVALID")
    packet = json.loads(payload)
    if (type(packet) is not dict or packet.get("schema") !=
            "kuodra.fictional-agent-ui-receipt.v1"
            or packet.get("mode") != mode or packet.get("decision") != decision
            or packet.get("synthetic_only") is not True
            or packet.get("public_export_allowed") is not False
            or packet.get("trade_authorized") is not False
            or packet.get("production_ready") is not False
            or packet.get("human_review_required") is not True
            or packet.get("source_authenticated") is not False
            or packet.get("source_rights_verified") is not False
            or packet.get("cross_source_entity_link_verified") is not False
            or packet.get("finance_model_accuracy_proven") is not False
            or packet.get("host_iam_verified") is not False
            or packet.get("host_no_egress_verified") is not False
            or packet.get("external_model_called") is not False
            or packet.get("network_requests") != 0
            or packet.get("audit_retained") is not False
            or packet.get("tool_calls") != (2 if mode == "SEC_ML" else 1)
            or packet.get("audit_chain_verified_ephemeral") is not
               (mode != "ML_ONLY")):
        raise AssertionError("P314_BROWSER_PACKET_POLICY_INVALID")
    digest = packet.pop("receipt_sha256", None)
    if (type(digest) is not str or len(digest) != 64
            or sha256(_canonical(packet)).hexdigest() != digest):
        raise AssertionError("P314_DOWNLOADED_RECEIPT_CHECKSUM_INVALID")
    if any(secret in payload for secret in (
            b"fakePrivate", b"fakePublic", b"syntheticInstitution",
            b"syntheticOwner", b"fictitiousIssuer",
            b"sk-", b"ghp_", b"AIza")):
        raise AssertionError("P314_BROWSER_REPORT_PRIVATE_IDENTIFIER_LEAK")
    packet["receipt_sha256"] = digest
    if payload != _canonical(packet):
        raise AssertionError("P314_BROWSER_REPORT_NONCANONICAL")
    return {
        "mode": mode, "decision": decision,
        "receipt_sha256": digest, "download_sha256": sha256(payload).hexdigest(),
        "download_bytes": len(payload), "tool_calls": packet["tool_calls"],
        "audit_chain_verified_ephemeral":
            packet["audit_chain_verified_ephemeral"],
        "source_rights_verified": False, "production_ready": False,
    }


def run(output: Path) -> dict:
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="kic-p314-agent-browser-") as home:
        env = dict(os.environ, HOME=home,
                   STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
        with (output / "p314-streamlit.log").open("wb") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(APP),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 "--server.port=8594", "--browser.gatherUsageStats=false"],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                _ready()
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(
                        headless=True, args=["--no-sandbox"])
                    try:
                        context = browser.new_context(
                            accept_downloads=True,
                            viewport={"width": 1440, "height": 960},
                            device_scale_factor=1,
                        )
                        outgoing, js_errors, external_websockets = [], [], []

                        def local_only(route):
                            host = urlsplit(route.request.url).hostname
                            if host in _ALLOWED_HOSTS:
                                route.continue_()
                            else:
                                outgoing.append(host or "unknown")
                                route.abort()

                        context.route("**/*", local_only)
                        page = context.new_page()
                        page.on("pageerror", lambda error: js_errors.append(str(error)))
                        page.on("websocket", lambda ws: external_websockets.append(ws.url)
                                if urlsplit(ws.url).hostname not in _ALLOWED_HOSTS else None)
                        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                        expect(page.get_by_text("KUODRA — 오프라인 합성 데이터")
                               ).to_be_visible(timeout=25000)
                        page.get_by_role("combobox", name="자료 유형").click()
                        page.get_by_role("option", name=MODE, exact=True).click()
                        expect(page.get_by_role("heading",
                            name="KUODRA — 질문 기반 SEC / ML / Guard Agent")
                            ).to_be_visible(timeout=20000)
                        expect(page.get_by_text("SYNTHETIC ONLY", exact=False)
                               ).to_be_visible(timeout=15000)
                        run_button = page.get_by_role(
                            "button", name="선택한 Agent 검토 실행", exact=True)
                        consent = page.get_by_role(
                            "checkbox", name="임시 SQLite 감사 생성·검증·즉시 삭제에 동의 (SEC 선택 시 필수)")
                        claim = page.get_by_role("combobox", name="가상 매출 주장")
                        source = page.get_by_role("combobox", name="가상 자료 선택")
                        question = page.get_by_role("textbox", name="분석 요청 (SEC/공시, ML/다변수 중 명시)")
                        expect(run_button).to_be_disabled()
                        expect(page.get_by_text("근거 연결 · 사람 검토 필요")
                               ).to_have_count(0)
                        assert not any(Path(home).rglob("*.sqlite")), "P314_PASSIVE_SQLITE"
                        receipts = []

                        def execute_and_verify(mode, decision, screenshot=None):
                            expect(run_button).to_be_enabled(timeout=10000)
                            run_button.click()
                            expect(page.get_by_role("heading",
                                name="근거 연결 · 사람 검토 필요")
                                ).to_be_visible(timeout=35000)
                            expect(page.get_by_text("Guard", exact=True)
                                   ).to_be_visible(timeout=10000)
                            if screenshot:
                                page.screenshot(path=str(output / screenshot),
                                                full_page=True)
                            with page.expect_download(timeout=25000) as download_event:
                                page.get_by_role("button",
                                    name="검증된 가상 보고서 JSON").click()
                            record = _verify_download(download_event.value,
                                                      mode=mode, decision=decision)
                            receipts.append(record)
                            return record

                        consent.check()
                        expect(run_button).to_be_enabled(timeout=10000)
                        execute_and_verify("SEC_ML", "HOLD", "p314-agent-hold.png")

                        claim.click()
                        page.get_by_role("option", name="충돌 주장 (REJECT)",
                                         exact=True).click()
                        expect(consent).not_to_be_checked(timeout=10000)
                        expect(run_button).to_be_disabled()
                        consent.check()
                        execute_and_verify("SEC_ML", "REJECT", "p314-agent-reject.png")

                        # An unsafe operator intent must never be runnable,
                        # regardless of an earlier approved synthetic run.
                        question.fill("SEC 공시와 다변수 ML 매수 주문")
                        question.press("Tab")
                        expect(run_button).to_be_disabled(timeout=10000)
                        expect(consent).not_to_be_checked(timeout=10000)
                        expect(page.get_by_text("근거 연결 · 사람 검토 필요")
                               ).to_have_count(0)

                        # Source change MUST choose its own matching question
                        # and disable stale audit consent.
                        source.click()
                        page.get_by_role("option", name="공개/비공개 ML만",
                                         exact=True).click()
                        expect(question).to_have_value("공개/비공개 다변수 ML 결과를 검토해줘")
                        expect(consent).to_be_disabled()
                        execute_and_verify("ML_ONLY", "HOLD",
                                           "p314-agent-ml-only.png")

                        source.click()
                        page.get_by_role("option", name="가상 공시만",
                                         exact=True).click()
                        expect(question).to_have_value("SEC 공시 원문 수치를 검토해줘")
                        expect(consent).not_to_be_checked(timeout=10000)
                        expect(run_button).to_be_disabled()
                        consent.check()
                        execute_and_verify("SEC_ONLY", "REJECT")

                        if js_errors or outgoing or external_websockets:
                            raise AssertionError("P314_BROWSER_RUNTIME_OR_EXTERNAL_REQUEST:"
                                                 + repr((js_errors, outgoing, external_websockets)))
                        if any(Path(home).rglob("*.sqlite")):
                            raise AssertionError("P314_EPHEMERAL_SQLITE_RETAINED")
                        if [r["decision"] for r in receipts] != (
                                ["HOLD", "REJECT", "HOLD", "REJECT"]):
                            raise AssertionError("P314_DECISION_SEQUENCE_INVALID")
                        result = {
                            "schema": "kuodra.p314-agent-real-chromium.v1",
                            "status": "PASS", "actual_chromium": True,
                            "synthetic_only": True,
                            "source_modes": [r["mode"] for r in receipts],
                            "results": receipts,
                            "consent_reset_on_claim": True,
                            "consent_reset_on_question": True,
                            "consent_reset_on_source": True,
                            "unsafe_trade_intent_blocked": True,
                            "downloads_checksum_replayed": True,
                            "ephemeral_audit_cleanup_verified": True,
                            "browser_runtime_errors": len(js_errors),
                            "external_host_attempts": len(outgoing),
                            "external_websocket_attempts": len(external_websockets),
                            "live_sec_requests": 0, "external_llm_requests": 0,
                            "real_publisher_authenticated": False,
                            "rights_verified": False,
                            "institution_iam_verified": False,
                            "production_verified": False,
                            "trade_executed": False,
                        }
                        (output / OUTPUT_NAME).write_bytes(_canonical(result))
                        return result
                    finally:
                        browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=8)


def main(argv: list[str] | None = None) -> int:
    output = Path(argv[0]) if argv else Path("/tmp/kic-p314-agent")
    print(json.dumps(run(output), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
