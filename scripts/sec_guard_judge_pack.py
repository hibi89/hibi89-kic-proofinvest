"""Reproducible synthetic-only SEC→Guard judge evidence ZIP.

Nine bounded files and a SHA256 manifest, all re-generated from existing
three-scenario offline code. Not a real SEC filing, DAKER submission, or
authenticated agent. ZIP is never extracted to user paths.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

from proofinvest.local_sec_guard_ui import (
    export_synthetic_guard_json,
    export_synthetic_guard_markdown,
    run_synthetic_guard_case,
)
from proofinvest.local_sec_html_report import render_local_sec_html

SCHEMA = "proofinvest.synthetic-sec-guard-judge-pack.v1"
MANIFEST = "SYNTHETIC_JUDGE_MANIFEST.json"
START_PAGE = "START_HERE.html"
CASES = ("matched", "conflict", "script")
MAX_FILE_BYTES = 65536
MAX_ZIP_BYTES = 250000
_EXPECTED_GUARDS = {"matched": "HOLD", "conflict": "REJECT", "script": "HOLD"}


def _json_bytes(value: object) -> bytes:
    return (json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(name: str) -> zipfile.ZipInfo:
    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    # Stored (uncompressed) ZIP has fixed bytes across zlib/platform versions.
    entry.compress_type = zipfile.ZIP_STORED
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    return entry


def landing_page() -> bytes:
    """A zero-network synthetic-only HTML landing page for all 3 cases."""
    cards = (
        ("matched", "01 | 수치 일치", "HOLD", "원문/위험 인증 보류"),
        ("conflict", "02 | 성장률 충돌", "REJECT", "산술 검산과 주장 불일치"),
        ("script", "03 | 스크립트 인용", "HOLD", "본문 출처 인용 불가"),
    )
    rows = "".join(
        '<tr><td>' + label + '</td><td><b>' + decision + '</b></td>'
        '<td>' + explanation + '</td><td><a href="' + key +
        '.html">HTML</a> / <a href="' + key + '.md">Markdown</a> / '
        '<a href="' + key + '.json">JSON</a></td></tr>'
        for key, label, decision, explanation in cards
    )
    markup = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        'style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;">'
        '<title>ProofInvest | SYNTHETIC Judge Start</title>'
        '<style>body{margin:0;background:#0f2035;color:#ebf5ff;font:16px system-ui}'
        'main{max-width:960px;margin:auto;padding:24px}header{background:#1d3b55;'
        'border-radius:15px;padding:27px}h1{margin:.3em 0}p{line-height:1.6}'
        'table{border-collapse:collapse;width:100%;background:#1c3148;'
        'margin-top:25px}td,th{padding:14px;border-bottom:1px solid #425e78;'
        'text-align:left}a{color:#73e2d8}.warning{border-left:5px solid #fd7474;'
        'padding:16px;background:#503036;margin:20px 0}'
        '@media(max-width:650px){table{display:block;overflow-x:auto;white-space:nowrap}'
        'main{padding:12px}header{padding:16px}}</style></head>'
        '<body><main><header><small>PROOFINVEST / EVIDENCE LAB</small>'
        '<h1>심사 시연 · 시작 페이지</h1>'
        '<p>세 가지 SEC 형식 가상 사례를 로컬 Guard 파이프라인에서 실행한 결과입니다.'
        '아래 HTML 보고서는 인터넷 연결 없이 열 수 있습니다.</p></header>'
        '<div class="warning"><strong>SYNTHETIC ONLY / NOT REAL SEC</strong>'
        '<p>가상 기업/수치만 사용. SEC 출처 인증, LLM/AI 실행, 실거래,'
        '공식 KIC 제출 영수증이 아닙니다.</p></div>'
        '<table><thead><tr><th>사례</th><th>Guard</th><th>판정 이유</th>'
        '<th>확인 자료</th></tr></thead><tbody>' + rows + '</tbody></table>'
        '<p>SHA-256 목록: SYNTHETIC_JUDGE_MANIFEST.json'
        ' (로컬 바이트 동일성만 확인)</p></main></body></html>'
    )
    return markup.encode("utf-8")


def build_bytes() -> bytes:
    """Generate exactly 3 validated offline traces, 2 formats each."""
    payload: dict[str, bytes] = {}
    for case in CASES:
        result = run_synthetic_guard_case(case)
        if (result["guard"]["decision"] != _EXPECTED_GUARDS[case]
                or result["audit_chain_valid"] is not True
                or result["limits"]["official_contest_submission"] is not False
                or result["limits"]["external_source_authenticated"] is not False
                or result["limits"]["trade_executed"] is not False):
            raise ValueError("UNSAFE_SYNTHETIC_JUDGE_CASE")
        json_name = case + ".json"
        md_name = case + ".md"
        html_name = case + ".html"
        payload[json_name] = export_synthetic_guard_json(result)
        payload[md_name] = export_synthetic_guard_markdown(result)
        payload[html_name] = render_local_sec_html(result)
    if any(not data or len(data) > MAX_FILE_BYTES for data in payload.values()):
        raise ValueError("SYNTHETIC_JUDGE_FILE_NOT_BOUNDED")
    manifest = {
        "schema": SCHEMA,
        "evidence_class": "SYNTHETIC_ONLY_UNVERIFIED",
        "real_sec_authenticated": False,
        "real_agent_executed": False,
        "trade_executed": False,
        "official_kic_submission": False,
        "file_list": {
            name: {"sha256": _sha(data), "bytes": len(data)}
            for name, data in sorted(payload.items())
        },
        "cases": [
            {"name": case, "guard": _EXPECTED_GUARDS[case]}
            for case in CASES
        ],
    }
    payload[START_PAGE] = landing_page()
    manifest["landing_page"] = START_PAGE
    manifest["file_list"][START_PAGE] = {"sha256": _sha(payload[START_PAGE]), "bytes": len(payload[START_PAGE])}
    payload[MANIFEST] = _json_bytes(manifest)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name in sorted(payload):
            archive.writestr(_entry(name), payload[name])
    packed = out.getvalue()
    if len(packed) > MAX_ZIP_BYTES:
        raise ValueError("SYNTHETIC_JUDGE_ZIP_TOO_LARGE")
    return packed


def verify_bytes(archive: bytes) -> dict:
    """Reject altered bytes, zip bombs, extra paths and stale claims."""
    if type(archive) is not bytes or not 0 < len(archive) <= MAX_ZIP_BYTES:
        raise ValueError("INVALID_SYNTHETIC_JUDGE_ARCHIVE")
    expected = build_bytes()
    if archive != expected:
        raise ValueError("SYNTHETIC_JUDGE_ARCHIVE_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest = json.loads(z.read(MANIFEST).decode("utf-8"))
        names = set(z.namelist())
        if (names != set(manifest["file_list"]) | {MANIFEST}
                or manifest["schema"] != SCHEMA
                or manifest.get("landing_page") != START_PAGE
                or manifest["evidence_class"] != "SYNTHETIC_ONLY_UNVERIFIED"
                or any(manifest[key] is not False for key in (
                    "real_sec_authenticated", "real_agent_executed",
                    "trade_executed", "official_kic_submission",
                ))):
            raise ValueError("SYNTHETIC_JUDGE_MANIFEST_INVALID")
        for name, expected_info in manifest["file_list"].items():
            data = z.read(name)
            if expected_info != {"sha256": _sha(data), "bytes": len(data)}:
                raise ValueError("SYNTHETIC_JUDGE_CHECKSUM_MISMATCH")
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_JUDGE_PACK_VERIFIED",
        "cases": len(CASES),
        "files": len(manifest["file_list"]),
        "synthetic_only": True,
        "external_source_authenticated": False,
        "official_submission": False,
        "sha256": _sha(archive),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic SEC→Guard judge ZIP, never real SEC/DAKER evidence"
    )
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    if args.action == "build":
        # x+b guarantees no replacement of preexisting user archives.
        with args.archive.open("xb") as stream:
            stream.write(build_bytes())
    with args.archive.open("rb") as stream:
        data = stream.read(MAX_ZIP_BYTES + 1)
    print(json.dumps(verify_bytes(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
