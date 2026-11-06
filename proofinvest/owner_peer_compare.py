"""Two independently replayed owner-supplied issuer 10-K histories -> peer comparison.

Caller uploads 8 SEC-format source bytes; this never claims SEC authentication,
peer-sector representativeness, lawful use rights, market authorization, LLM
inference or permission to trade. Zero outbound HTTP, DB writes, persistence.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from html import escape
import json
from typing import Any

from .ticker_local_workflow import run_local_ticker_workflow
from .ticker_local_report import verify_local_report
from .ticker_research_intake import _TICKER
from .ticker_sec_financial_bridge import _KEYS, _LIMITS

_SCHEMA="kuodra.owner-peer-original-compare.v1"
_STATUS="TWO_DISTINCT_OWNER_FILINGS_REPLAYED_UNVERIFIED"
_MAX_OFFSET=45


def _blocked(reason:str)->dict[str,Any]:
    return {
        "schema":_SCHEMA,"status":"BLOCKED","reason_code":reason,
        "guard":"HOLD","network_requests":0,"tool_calls":0,
        "source_authenticated":False,"source_rights_verified":False,
        "peer_originals_authenticated":False,
        "peer_reuse_rights_verified":False,"sector_representative":False,
        "comparison_is_investment_advice":False,
        "external_sharing_allowed":False,"ai_agent_executed":False,
        "trade_executed":False,
    }


def _canonical(value:dict[str,Any])->bytes:
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _source_shape(ticker:Any,sources:Any)->bool:
    return (type(ticker) is str and _TICKER.fullmatch(ticker) is not None
            and type(sources) is dict and set(sources)==set(_KEYS)
            and all(type(sources[key]) is bytes and
                    0<len(sources[key])<=_LIMITS[key] for key in _KEYS))


def _one(ticker:str,as_of:str,sources:dict[str,bytes])->tuple[dict,dict]:
    wf=run_local_ticker_workflow(ticker=ticker,as_of=as_of,sources=sources)
    if (wf.get("status")!="READY_FOR_HUMAN_REVIEW_UNVERIFIED"
            or wf.get("tool_calls_executed")!=7
            or len(wf.get("tool_trace",[]))!=7
            or not all(x.get("accepted") is True for x in wf["tool_trace"])
            or wf.get("network_requests")!=0
            or wf.get("source_authenticated") is not False
            or wf.get("source_rights_verified") is not False
            or wf.get("trade_executed") is not False
            or type(wf.get("report")) is not dict):
        raise ValueError("SEVEN_STEP_ISSUER_REPLAY_FAILED")
    proof=verify_local_report(wf["report"],sources=sources)
    if (proof.get("status")!="PASS"
            or proof.get("report_semantics_recomputed") is not True
            or proof.get("source_authenticated") is not False
            or proof.get("source_rights_verified") is not False
            or proof.get("trade_executed") is not False):
        raise ValueError("ISSUER_REPORT_INDEPENDENT_REPLAY_FAILED")
    r=wf["receipt"]
    rev=wf["revenue"]
    if (r.get("ticker")!=ticker or rev.get("ticker")!=ticker
            or rev.get("issuer_cik")!=r.get("cik")
            or rev.get("accession")!=r.get("selected_10k_accession")
            or rev.get("filing_date")!=r.get("selected_10k_filing_date")
            or wf["report"].get("guard_policy_preview") not in ("HOLD","REJECT")):
        raise ValueError("ISSUER_METADATA_IDENTITY_MISMATCH")
    return wf,r


def compare_owner_peer(
    *,ticker:str,peer_ticker:str,as_of:str,
    sources:dict[str,bytes],peer_sources:dict[str,bytes],
)->dict[str,Any]:
    """One human-triggered comparable-period pair; only structurally attested."""
    if (not _source_shape(ticker,sources)
            or not _source_shape(peer_ticker,peer_sources)
            or ticker==peer_ticker or type(as_of) is not str):
        return _blocked("TWO_DISTINCT_BOUNDED_ISSUERS_REQUIRED")
    try:
        if date.fromisoformat(as_of).isoformat()!=as_of:
            return _blocked("CUTOFF_DATE_INVALID")
        first,primary=_one(ticker,as_of,sources)
        second,peer=_one(peer_ticker,as_of,peer_sources)
        if primary["cik"]==peer["cik"]:
            return _blocked("PEER_CIK_NOT_DISTINCT")
        if (primary["selected_10k_accession"]==
                peer["selected_10k_accession"]):
            return _blocked("SAME_FILING_CANNOT_BE_COMPETITOR")
        if primary["source_sha256"]["companyfacts"]==peer["source_sha256"]["companyfacts"]:
            return _blocked("CROSS_ISSUER_COMPANYFACTS_BYTES_DUPLICATED")
        rev_a,rev_b=first["revenue"],second["revenue"]
        date_cur_a=date.fromisoformat(rev_a["current_end"])
        date_cur_b=date.fromisoformat(rev_b["current_end"])
        date_old_a=date.fromisoformat(rev_a["prior_end"])
        date_old_b=date.fromisoformat(rev_b["prior_end"])
        date_offset=max(abs((date_cur_a-date_cur_b).days),
                        abs((date_old_a-date_old_b).days))
        aligned=date_offset<=_MAX_OFFSET
        growth=[]
        for rev in (rev_a,rev_b):
            x=Decimal(rev["growth_pct"])
            if (not x.is_finite() or abs(x)>Decimal("100000000")
                    or len(rev["growth_pct"])>32):
                return _blocked("GROWTH_SOURCE_NUMERIC_NOT_BOUNDED")
            growth.append(x)
        diff=(growth[0]-growth[1]).quantize(
            Decimal("0.01"),rounding=ROUND_HALF_UP) if aligned else None
        def issuer(wf:dict,receipt:dict)->dict:
            rev=wf["revenue"]
            return {
                "ticker":receipt["ticker"],"cik":receipt["cik"],
                "accession":receipt["selected_10k_accession"],
                "filing_date":receipt["selected_10k_filing_date"],
                "current_end":rev["current_end"],"prior_end":rev["prior_end"],
                "revenue_growth_pct":rev["growth_pct"],
                "source_sha256":dict(receipt["source_sha256"]),
                "original_10k_source_url":receipt["source_urls"]["original_10k"],
                "report_sha256":wf["report"]["report_sha256"],
                "guard":wf["report"]["guard_policy_preview"],
                "source_verified_by_sec":False,"rights_verified":False,
            }
        guard=("REJECT" if "REJECT" in (
            first["report"]["guard_policy_preview"],
            second["report"]["guard_policy_preview"]) else "HOLD")
        out={
            "schema":_SCHEMA,"status":_STATUS,
            "as_of":as_of,"primary":issuer(first,primary),
            "peer":issuer(second,peer),
            "comparison_status":(
                "SAME_VINTAGE_DESCRIPTIVE_GROWTH_ONLY"
                if aligned else "UNAVAILABLE_FISCAL_PERIODS_NOT_ALIGNED"),
            "max_fiscal_end_offset_days":date_offset,
            "max_allowed_offset_days":_MAX_OFFSET,
            "growth_gap_primary_minus_peer_pp":str(diff) if aligned else None,
            "comparison_guard":guard,
            "source_scope":"TWO_CALLER_PROVIDED_10K_STRUCTURES_ONLY",
            "source_authenticated":False,
            "source_rights_verified":False,
            "peer_originals_authenticated":False,
            "peer_reuse_rights_verified":False,
            "sector_representative":False,
            "complete_engine_c":False,
            "comparison_is_investment_advice":False,
            "external_sharing_allowed":False,
            "ai_agent_executed":False,"trade_executed":False,
            "network_requests":0,"tool_calls":14,
            "limitations":[
                "Both issuer 10-K sources are caller-supplied, not SEC authenticated",
                "Peer relationship, sector representativeness and rights not verified",
                "Different fiscal cutoffs may be incomparable",
                "Financial arithmetic is not a trading or fraud verdict",
            ],
        }
        if len(_canonical(out))>20000:
            return _blocked("PEER_REPORT_TOO_LARGE")
        out["integrity_sha256"]=sha256(_canonical(out)).hexdigest()
        return out
    except (ValueError,TypeError,KeyError,AttributeError,RecursionError,
            InvalidOperation,OverflowError,UnicodeError):
        return _blocked("PAIR_SOURCE_OR_PERIOD_REPLAY_FAILED")


def verify_owner_peer(
    packet:Any,*,ticker:Any,peer_ticker:Any,as_of:Any,
    sources:Any,peer_sources:Any,
)->bool:
    if (type(packet) is not dict or packet.get("status")!=_STATUS
            or type(packet.get("integrity_sha256")) is not str):
        return False
    try:
        unsigned=dict(packet)
        digest=unsigned.pop("integrity_sha256")
        if len(digest)!=64 or sha256(_canonical(unsigned)).hexdigest()!=digest:
            return False
        return compare_owner_peer(
            ticker=ticker,peer_ticker=peer_ticker,as_of=as_of,
            sources=sources,peer_sources=peer_sources)==packet
    except (ValueError,TypeError,KeyError,RecursionError,OverflowError):
        return False


def render_owner_peer_html(
    packet:Any,*,ticker:Any,peer_ticker:Any,as_of:Any,
    sources:Any,peer_sources:Any,
)->bytes:
    if not verify_owner_peer(
        packet,ticker=ticker,peer_ticker=peer_ticker,as_of=as_of,
        sources=sources,peer_sources=peer_sources):
        raise ValueError("PAIR_HTML_SOURCE_REPLAY_REQUIRED")
    e=lambda x:escape(str(x),quote=True)
    cols="".join(
        "<tr><th>"+e(key)+"</th><td>"+e(packet["primary"][key])+
        "</td><td>"+e(packet["peer"][key])+"</td></tr>"
        for key in ("ticker","cik","accession","filing_date",
                    "current_end","prior_end","revenue_growth_pct","guard"))
    citations=""
    for item in ("primary","peer"):
        row=packet[item]
        citations+=("<h2>"+e(row["ticker"])+" 4개 파일 SHA-256</h2><table>"+
            "".join("<tr><th>"+e(k)+"</th><td><code>"+e(v)+
                    "</code></td></tr>"
                    for k,v in sorted(row["source_sha256"].items()))+
            "<tr><th>내부 검산 보고서</th><td><code>"+
            e(row["report_sha256"])+"</code></td></tr></table>")
    html=(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src '
        '&apos;none&apos;; style-src &apos;unsafe-inline&apos;; img-src '
        '&apos;none&apos;; base-uri &apos;none&apos;; form-action &apos;none&apos;">'
        '<meta name="referrer" content="no-referrer">'
        '<title>KUODRA · 2개 미국기업 원본 대조</title>'
        '<style>body{font:16px/1.65 system-ui;max-width:950px;'
        'margin:2rem auto;padding:0 1rem;color:#222}'
        'table{width:100%;border-collapse:collapse}'
        'td,th{border:1px solid #aaa;padding:.5rem;text-align:left}'
        'td,code{overflow-wrap:anywhere}</style></head><body>'
        '<h1>KUODRA · 두 회사 원문 기반 제한 비교 · '+e(packet["comparison_guard"])+'</h1>'
        '<p>로컬 개인 검토용 · 실제 SEC 원본 인증 아님 · '
        '기업간 비교 관계 및 이용권 미인증 · 매매/회계부정 판정 불가</p>'
        '<p>자료 기준일 '+e(packet["as_of"])+'</p><table><tr>'
        '<th>항목</th><th>대상기업</th><th>비교기업</th></tr>'+
        cols+'</table><p>결산 기간 최대 격차 '+e(packet["max_fiscal_end_offset_days"])+
        '일, 허용 '+e(packet["max_allowed_offset_days"])+
        '일 · 비교 상태 '+e(packet["comparison_status"])+
        ' · 매출성장률 차이(대상-비교, pp): '+
        e(packet["growth_gap_primary_minus_peer_pp"] or "UNAVAILABLE")+
        '</p>'+citations+
        '<p>발행처 진위·사용권·완전한 업종 비교 미확인. '
        '추가 HTTP 0회 · 투자권고/매매 0건.</p></body></html>'
    ).encode("utf-8")
    if not 0<len(html)<=32768 or b"<script" in html.lower():
        raise ValueError("PEER_HTML_UNSAFE")
    return html
