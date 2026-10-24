"""No LLM in numeric verification; never invent data for missing evidence."""
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import re

ACCOUNTS = {"매출액": "revenue", "영업이익": "operating_profit", "당기순이익": "net_profit", "자산총계": "assets", "부채총계": "liabilities", "자본총계": "equity"}

@dataclass(frozen=True)
class Check:
    metric: str
    state: str  # verified | conflict | unavailable
    value: str | None
    source: str | None
    explanation: str


def amount(raw: Any) -> Decimal | None:
    if raw is None or str(raw).strip() in ("", "-", "N/A"):
        return None
    try:
        s=str(raw).strip().replace(",", "").replace(" ", "")
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?",s):return None
        return Decimal(s)
    except InvalidOperation:return None


def _period_end(raw: Any) -> date | None:
    """Read the last complete OpenDART date (end of a displayed date range)."""
    if not isinstance(raw, str):
        return None
    dates = re.findall(r"(?<!\d)(\d{4})[.-](\d{2})[.-](\d{2})(?!\d)", raw)
    if not dates:
        return None
    try:
        return date(*(int(part) for part in dates[-1]))
    except ValueError:
        return None


def _consistent_annual_period(rows: list[dict], year: int) -> bool:
    """Selected statement rows must describe one annual reporting period.

    All-missing metadata supports the historical synthetic fixture only.
    Mixed years, interim codes, partial metadata, or different period ends
    are not safe to calculate as a single annual statement.
    """
    if not rows:
        return False
    has_report_metadata = any(
        "bsns_year" in row or "reprt_code" in row for row in rows
    )
    if has_report_metadata and any(
        str(row.get("bsns_year", "")) != str(year)
        or str(row.get("reprt_code", "")) != "11011"
        for row in rows
    ):
        return False
    has_dates = any(
        "thstrm_dt" in row or "frmtrm_dt" in row for row in rows
    )
    if has_dates:
        end_pairs = set()
        for row in rows:
            current = _period_end(row.get("thstrm_dt"))
            previous = _period_end(row.get("frmtrm_dt"))
            if current is None or previous is None or previous >= current:
                return False
            end_pairs.add((current, previous))
        if len(end_pairs) != 1:
            return False
    return True


def parse_accounts(rows: list[dict], year: int, preferred_fs: str = "CFS") -> dict[str,dict]:
    """Pick one statement type; never combine CFS and OFS in ratios."""
    valid=[r for r in rows if r.get("account_nm") in ACCOUNTS]
    fs_set={r.get("fs_div") for r in valid}
    fs=preferred_fs if preferred_fs in fs_set else ("OFS" if "OFS" in fs_set else None)
    if not fs:return {}
    selected=[r for r in valid if r.get("fs_div")==fs]
    # Never rescue only favorable rows from a mixed-period report.
    if not _consistent_annual_period(selected, year):
        return {}
    out={}
    ambiguous=set()
    for r in selected:
        key=ACCOUNTS[r["account_nm"]]
        # Never silently accept the first of repeated rows for the same
        # metric within the selected financial statement type.
        if key in ambiguous:continue
        if key in out:
            del out[key]
            ambiguous.add(key)
            continue
        out[key]={"current":amount(r.get("thstrm_amount")),"previous":amount(r.get("frmtrm_amount")),
                  "source": ("https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+r["rcept_no"])
                    if re.fullmatch(r"\d{14}",str(r.get("rcept_no",""))) else None,
                  "currency":r.get("currency", "KRW"),"fs_div":fs,"year":year,"account":r["account_nm"]}
    return out


def calculate(rows:list[dict], year:int, claim_revenue_growth_pct:str|None=None, is_demo:bool=False)->dict:
    data=parse_accounts(rows,year)
    sourcekind="SYNTHETIC_FIXTURE" if is_demo else "OPENDART"
    checks=[]; signals=[]
    rev=data.get("revenue")
    if not rev or rev["current"] is None or rev["previous"] in (None,Decimal(0)):
        checks.append(Check("revenue_yoy_pct","unavailable",None,None,"매출액 현재·전기 수치 또는 분모가 없음"))
    else:
        growth=(rev["current"]-rev["previous"])/abs(rev["previous"])*100
        explanation="공시 수치로 전년 대비 증감률 재계산 (분모는 전기 절댓값)"
        state="verified"
        if claim_revenue_growth_pct is not None:
            claim=amount(claim_revenue_growth_pct)
            if claim is None:state="unavailable";explanation="사용자 주장 수치 형식 오류"
            elif abs(claim-growth)>Decimal("0.1"):state="conflict";explanation=f"주장 {claim}% 와 계산 결과 차이 0.1%p 초과"
        checks.append(Check("revenue_yoy_pct",state,str(growth.quantize(Decimal("0.01"))),rev["source"],explanation))
    debt=data.get("liabilities");equity=data.get("equity")
    if debt and equity and debt["current"] is not None and equity["current"] not in (None,Decimal(0)):
        ratio=debt["current"]/equity["current"]*100
        signals.append({"rule":"debt_to_equity_pct", "value":str(ratio.quantize(Decimal("0.01"))),
                        "triggered":ratio>=Decimal(200),"threshold_pct":200,"source":debt["source"],
                        "note":"200%는 시연용 탐색 임계값이며 투자 판단 기준이 아님"})
    else:
        signals.append({"rule":"debt_to_equity_pct","value":None,"triggered":None,"source":None,"note":"근거 부족 또는 분모 0 — 계산 중단"})
    return {"status":"demo_not_real" if is_demo else "financial_checks_only", "year":year,
            "source_kind":sourcekind,"accounts_found":sorted(data.keys()),
            "checks":[asdict(c) for c in checks],"risk_signals":signals,
            "limitations":["매수·매도 추천 아님", "산업 리서치·LLM 요약은 아직 미구현", "연결/별도 재무 혼합 방지"]}
