"""P170: one-page offline A/B/C reviewer report from validated, redacted receipts.

Readable and printer-friendly HTML; NO raw SEC/stock/index bodies, external
requests, scripts, persistent storage, publisher authentication, licensing,
trade or model inference. The existing canonical JSON receipts remain the
authoritative machine-readable evidence.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from typing import Any

from .ticker_review_packet import inspect_review_packet_bytes
from .ticker_source_clearance_packet import inspect_source_clearance_packet
from .local_market_csv_bridge import inspect_csv_lineage_receipt

_MAX_HTML = 80_000


def _e(value: Any) -> str:
    """Escape every dynamic value; untrusted JSON is never HTML markup."""
    if value is None:
        return "UNAVAILABLE"
    if type(value) is not str and type(value) is not int:
        raise ValueError("REVIEW_HTML_VALUE_TYPE_INVALID")
    return escape(str(value), quote=True)


def render_reviewer_html(
    *, review_packet: bytes, rights_gap_report: bytes,
    csv_lineage: bytes | None = None,
) -> bytes:
    """Produce deterministic static HTML only if all receipts link exactly.

    Source hash association is not a vendor signature or licensed use grant.
    This function is local only and imposes no permissions/state changes.
    """
    review = inspect_review_packet_bytes(review_packet)
    rights = inspect_source_clearance_packet(
        rights_gap_report, review_packet=review_packet,
    )
    if (review["status"] != "LOCAL_PACKET_INTERNAL_INTEGRITY_PASS_UNVERIFIED"
            or rights["status"] != "MATCHED_REPORT_EXTERNAL_CLEARANCES_STILL_PENDING"
            or rights["source_rights_verified"] is not False):
        raise ValueError("REVIEW_HTML_INVALID_LINKED_RECEIPTS")
    if csv_lineage is not None:
        lineage = inspect_csv_lineage_receipt(
            csv_lineage, packet=review_packet,
        )
        if lineage["status"] != "CSV_LINEAGE_MATCHED_RIGHTS_PENDING":
            raise ValueError("REVIEW_HTML_CSV_LINEAGE_INVALID")
    packet = json.loads(review_packet.decode("utf-8"))
    rights_data = json.loads(rights_gap_report.decode("utf-8"))
    explanation = packet["explanation"]
    issuer = packet["issuer"]
    market = packet["linked_evidence"]["premium_engine_a"]
    findings = explanation["findings"]
    if [f["engine"] for f in findings] != ["A", "B", "C"]:
        raise ValueError("REVIEW_HTML_FINDINGS_INVALID")
    # A/B/C text originates from the existing deterministic explanation
    # allowlist, not from any LLM, external HTML or user's raw source.
    labels = ("시장·가격 비교 / Engine A", "회계·현금흐름 / Engine B",
              "동종기업·산업 / Engine C")
    cards = []
    for label, finding in zip(labels, findings):
        detail = ""
        if finding["engine"] == "A":
            detail = (
                '<dl class="metrics">'
                f'<div><dt>종목 가격 수익률</dt><dd>{_e(finding["security_return_pct"])}%</dd></div>'
                f'<div><dt>NDX 가격 수익률</dt><dd>{_e(finding["benchmark_return_pct"])}%</dd></div>'
                f'<div><dt>단순 차이 (pp)</dt><dd>{_e(finding["simple_return_gap_pp"])}</dd></div>'
                f'<div><dt>동일 거래일</dt><dd>{_e(finding["matched_sessions"])}</dd></div>'
                '</dl>'
            )
        cards.append(
            '<section class="finding">'
            f'<h3>{_e(label)}</h3><p class="status">{_e(finding["status"])}</p>'
            f'{detail}<p>{_e(finding["interpretation"])}</p></section>'
        )
    rows = []
    for file in rights_data["files"]:
        rows.append(
            '<tr>'
            f'<td>{_e(file["role"])}</td>'
            f'<td>{_e(file["input_state"])}</td>'
            f'<td>{_e(file["bytes"])}</td>'
            f'<td><code>{_e(file["sha256"])}</code></td>'
            '</tr>'
        )
    unresolved = "".join(
        f"<li>{_e(key)}</li>"
        for key in rights_data["unresolved_clearances"]
    )
    csv_mark = (
        '<span>CSV 원본→정규화 JSON 계보 연결: PASS / '
        '공급자·이용권리 미인증</span>'
        if csv_lineage is not None else
        '<span>시장 입력 모드: 원본 JSON / 공급자 미인증</span>'
    )
    # No active content. The static report is explicitly personal/offline
    # review, not an authorization to upload copyrighted source-derived data.
    result = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>KUODRA | {_e(issuer["ticker"])} | 오프라인 근거 검토 (미인증)</title>
<style>
:root{{color-scheme:light;--ink:#0f2632;--muted:#536875;--line:#d4e0e8;--pale:#f3f7fa;--accent:#006b70}}
*{{box-sizing:border-box}}body{{font-family:system-ui,-apple-system,'Malgun Gothic',sans-serif;color:var(--ink);background:#f3f7fa;line-height:1.6;margin:0}}
main{{max-width:1000px;margin:24px auto;padding:38px 42px;background:white;border:1px solid var(--line);border-radius:12px}}
h1{{font-size:2rem;letter-spacing:-.035em;margin:8px 0}}h2{{font-size:1.15rem;margin:34px 0 12px;border-bottom:2px solid var(--line);padding-bottom:6px}}
h3{{font-size:1rem;margin:0}}.eyebrow{{font-size:.75rem;letter-spacing:.13em;font-weight:750;color:var(--accent)}}
.lead{{color:var(--muted);font-size:.94rem}}.flag{{font-size:.85rem;font-weight:750;background:#eef4f7;border-left:4px solid #7a96a5;padding:12px 15px;margin:18px 0}}
.meta{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}}.meta>div{{background:var(--pale);padding:11px 13px;border-radius:6px}}
dt{{font-size:.73rem;color:var(--muted);font-weight:600}}dd{{font-weight:700;margin:0;word-break:break-word}}
.findings{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.finding{{border:1px solid var(--line);border-radius:8px;padding:15px}}
.finding p{{font-size:.87rem}}.status{{font-size:.72rem!important;color:var(--accent);overflow-wrap:anywhere;font-weight:700}}
.metrics{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:13px 0}}
table{{border-collapse:collapse;width:100%;font-size:.78rem}}th,td{{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:var(--pale)}}code{{font-family:ui-monospace,Consolas,monospace;font-size:.72rem;overflow-wrap:anywhere}}
ul{{font-size:.86rem}}li{{margin:4px 0}}.foot{{font-size:.75rem;color:var(--muted);border-top:1px solid var(--line);margin-top:24px;padding-top:14px}}
@media(max-width:720px){{main{{margin:0;padding:18px;border-radius:0}}.findings,.meta{{grid-template-columns:1fr}}.table-scroll{{overflow-x:auto}}}}
@media print{{body{{background:white}}main{{border:0;margin:0;max-width:none;padding:0}}.finding,th,li{{break-inside:avoid}}h2{{break-after:avoid}}}}
</style>
</head>
<body>
<main>
<div class="eyebrow">KUODRA · SOURCE-BOUND EVIDENCE BRIEF / OFFLINE</div>
<h1>{_e(issuer["ticker"])} · 1종목 근거 검토</h1>
<p class="lead">로컬 SEC 4종 + 종목 일별 가격 + 실제 NDX 표기 자료를 사용한 결정론적 A/B/C 산술 요약. 원본 출처·시장 시점·공개 권한은 별도 확인이 필요합니다.</p>
<div class="flag">검토 상태: HOLD · 출처 미인증 · 자료 이용권한 미확인 · 매매·투자 추천·공식 제출 승인 아님</div>
<dl class="meta">
<div><dt>티커</dt><dd>{_e(issuer["ticker"])}</dd></div>
<div><dt>CIK</dt><dd>{_e(issuer["cik"])}</dd></div>
<div><dt>SEC 접수번호</dt><dd>{_e(issuer["accession"])}</dd></div>
<div><dt>공시일</dt><dd>{_e(issuer["filing_date"])}</dd></div>
<div><dt>분석 기준일</dt><dd>{_e(issuer["as_of"])}</dd></div>
<div><dt>시장 관측 기간</dt><dd>{_e(market["matched_period_start"])} ~ {_e(market["matched_period_end"])}</dd></div>
</dl>
<h2>엔진별 검토</h2>
<div class="findings">{''.join(cards)}</div>
<p class="lead">NDX와 종목의 가격 수익률 비교는 알파·버블 검증 완료나 인과관계의 증거가 아닙니다. 동종기업 수치가 없으면 Engine C의 결론은 UNAVAILABLE/보류합니다.</p>
<h2>근거 원본 해시와 보류 항목</h2>
<p class="lead">패킷 SHA-256: <code>{_e(sha256(review_packet).hexdigest())}</code></p>
<p class="lead">출처·권리 검토표 SHA-256: <code>{_e(sha256(rights_gap_report).hexdigest())}</code></p>
<p class="lead">{csv_mark}</p>
<div class="table-scroll"><table><thead><tr><th>자료</th><th>원본 결합 상태</th><th>bytes</th><th>SHA-256 (로컬 입력 식별자)</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>승인되지 않은 사항</h2><ul>{unresolved}</ul>
<div class="flag">발행기관 원본 인증 FALSE · 유료 지수 권한 검증 FALSE · 재배포/상업적 이용 FALSE · Guard 실행 FALSE · 거래 실행 FALSE</div>
<p class="foot">이 HTML은 입력된 정규화 검토 패킷과 권리 검토표의 내부 무결성을 재확인해 생성한 로컬 표시물입니다. 권리 검토표의 해시값은 발행기관 서명이나 출처 인증을 대신하지 않습니다. 실제 원본 재검산에는 SEC/시장 데이터 바이트가 필요합니다. 원본 JSON 검토 문서를 함께 보관하세요. 네트워크·외부 CSS/스크립트·모델 호출·데이터베이스 쓰기 없음.</p>
</main>
</body>
</html>
"""
    raw = result.encode("utf-8")
    if len(raw) > _MAX_HTML:
        raise ValueError("REVIEW_HTML_TOO_LARGE")
    return raw
