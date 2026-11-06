"""Printable human-only local report from exact caller-owned SEC-format bytes.

Refuses a forged digest, stale 10-K, mismatched optional market/peer bytes,
or changed Guard. HTML text is escaped and has no active resources.
"""
from __future__ import annotations

from html import escape
from typing import Any
from .owner_source_global_agent import verify_owner_source_answer


def render_owner_source_html(
    packet: Any, *,ticker: Any,as_of: Any,question: Any,
    sources: Any,market_json: Any=None,industry_json: Any=None,
) -> bytes:
    if not verify_owner_source_answer(
        packet,ticker=ticker,as_of=as_of,question=question,
        sources=sources,market_json=market_json,industry_json=industry_json
    ):
        raise ValueError("OWNER_SOURCE_HTML_REPLAY_REQUIRED")
    e=lambda x:escape(str(x),quote=True)
    if packet["guard_policy_preview"] not in ("HOLD","REJECT"):
        raise ValueError("GUARD_UNVERIFIED")
    rows=[]
    for finding in packet["analysis_findings"]:
        rows.append(
            '<section><h2>'+e(finding["step"])+'. '+e(finding["tool"])+
            '</h2><p>'+e(finding["finding"])+
            '</p><p>결론: '+e(finding["guard"])+
            ' / 검산 보고서 SHA-256: <code>'+
            e(finding["evidence_report_sha256"])+
            '</code></p></section>')
    src=''.join(
        '<tr><th>'+e(name)+'</th><td><code>'+e(digest)+
        '</code></td></tr>'
        for name,digest in sorted(packet["sources_sha256"].items())
    )
    optional=''.join(
        '<tr><th>'+e(key)+'</th><td><code>'+e(packet[key] or
        "UNAVAILABLE")+'</code></td></tr>'
        for key in ("optional_market_sha256","optional_industry_sha256"))
    trace=''.join(
        '<li>'+e(item["step"])+'. '+e(item["tool"])+
        ' · '+e(item["status"])+'</li>'
        for item in packet["tool_trace"])
    html=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src '
        '&apos;none&apos;; style-src &apos;unsafe-inline&apos;; img-src '
        '&apos;none&apos;; base-uri &apos;none&apos;; form-action &apos;none&apos;">'
        '<meta name="referrer" content="no-referrer">'
        '<title>KUODRA | 로컬 원문 근거 투자 검토</title>'
        '<style>body{font:16px/1.65 system-ui,sans-serif;max-width:900px;'
        'margin:2rem auto;padding:0 1rem;color:#222}h1{font-size:1.6rem}'
        'section{border-top:1px solid #aaa;padding:0.6rem 0}'
        'table{width:100%;border-collapse:collapse}td,th{border:1px solid '
        '#bbb;padding:.5rem;text-align:left;overflow-wrap:anywhere}'
        'code{font-size:.8rem;overflow-wrap:anywhere}</style></head><body>'
        '<h1>KUODRA · 미국 기업 근거 기반 다중 검산</h1>'
        '<p><strong>로컬 개인 검토용 · 외부 배포 권리 미확인 · '
        '실제 SEC 발행처 인증 아님 · 투자권고 아님 · '
        '모델 추론 결과에 매매 권한 없음</strong></p>'
        '<p>기업: '+e(packet["ticker"])+
        ' / CIK: '+e(packet["cik"])+
        ' / 기준일: '+e(packet["as_of"])+
        ' / 10-K 접수번호: '+e(packet["filing_accession"])+
        ' / 제출일: '+e(packet["filing_date"])+
        ' / Guard: <strong>'+e(packet["guard_policy_preview"])+
        '</strong></p><h2>질문과 분석 추적</h2><p>질문 SHA-256: <code>'+
        e(packet["question_sha256"])+
        '</code></p><p>실행 분석 항목 '+e(packet["analysis_count"])+
        '개 / 동일 원본의 7단계 도구 재검산 1회</p>'+
        ''.join(rows)+
        '<h2>원본 바이트 해시(발행처 인증과 별개)</h2><table>'+
        src+optional+
        '<tr><th>계산 보고서 SHA-256</th><td><code>'+
        e(packet["local_report_sha256"])+
        '</code></td></tr></table><h2>실행 추적</h2><ol>'+
        trace+'</ol><p>시장 A: '+e(packet["engine_a_status"])+
        ' / 회계 B: '+e(packet["engine_b_status"])+
        ' / 경쟁사 C: '+e(packet["engine_c_status"])+
        '</p><p>외부 네트워크 요청 0회 · 거래 0건 · '
        '추가 권한·제3자 공개 사용 미승인.</p></body></html>'
    ).encode("utf-8")
    if not 0<len(html)<=32768 or b"<script" in html.lower():
        raise ValueError("HTML_BOUNDED_NO_SCRIPT_REQUIRED")
    return html
