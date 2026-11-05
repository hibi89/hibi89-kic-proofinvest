"""Korean equity demo using only locally uploaded CSV, never live KRX data."""
from __future__ import annotations
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
from io import StringIO
import re

_RE = re.compile(r"[0-9]{1,13}(?:\.[0-9]{1,8})?\Z")

def analyze_kr_prices(raw: bytes, *, ticker: str, benchmark: str,
                      as_of: str) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= 131072:
        raise ValueError("KR_INPUT_SIZE")
    if type(ticker) is not str or re.fullmatch(r"[0-9]{6}", ticker) is None:
        raise ValueError("KR_STOCK_CODE")
    if benchmark not in ("KOSPI", "KOSDAQ"):
        raise ValueError("KR_BENCHMARK")
    try:
        cutoff = date.fromisoformat(as_of)
        if cutoff.isoformat() != as_of:
            raise ValueError()
        decoded = raw.decode("utf-8-sig")
        if "\x00" in decoded:
            raise ValueError()
        reader = csv.reader(StringIO(decoded, newline=""), strict=True)
        if next(reader, None) != ["date", "stock_close", "benchmark_close"]:
            raise ValueError()
        rows = list(reader)
    except (ValueError, UnicodeError, csv.Error, TypeError):
        raise ValueError("KR_INPUT_FORMAT") from None
    if not 31 <= len(rows) <= 501:
        raise ValueError("KR_INPUT_COUNT")
    dates, a, b = [], [], []
    for row in rows:
        if len(row) != 3 or any(not isinstance(x, str) or not _RE.fullmatch(x)
                                 for x in row[1:]):
            raise ValueError("KR_PRICE_FORMAT")
        try:
            day = date.fromisoformat(row[0])
            x, y = Decimal(row[1]), Decimal(row[2])
        except (ValueError, InvalidOperation):
            raise ValueError("KR_ROW_INVALID") from None
        if (day.isoformat() != row[0] or day > cutoff or day.weekday() >= 5
                or x <= 0 or y <= 0
                or dates and not 1 <= (day - dates[-1]).days <= 10):
            raise ValueError("KR_PRICE_OR_DATE_INVALID")
        dates.append(day)
        a.append(x)
        b.append(y)
    with localcontext() as ctx:
        ctx.prec = 40
        ra = [a[i]/a[i-1]-1 for i in range(1,len(a))]
        rb = [b[i]/b[i-1]-1 for i in range(1,len(b))]
        n = Decimal(len(ra))
        ma, mb = sum(ra)/n, sum(rb)/n
        va = sum((v-ma)**2 for v in ra)
        vb = sum((v-mb)**2 for v in rb)
        cov = sum((x-ma)*(y-mb) for x,y in zip(ra,rb))
        beta = cov/vb if vb else None
        alpha = (ma-beta*mb)*100 if beta is not None else None
        r2 = cov*cov/(va*vb) if va and vb else None
        stock_return = (a[-1]/a[0]-1)*100
        index_return = (b[-1]/b[0]-1)*100
        fmt = lambda v: format(v.quantize(Decimal("0.0001")), "f") if v is not None else None
        result = {"stock_return_pct":fmt(stock_return),"index_return_pct":fmt(index_return),
                  "beta":fmt(beta),"ols_intercept_daily_pct":fmt(alpha),"r_squared":fmt(r2)}
    return {"schema":"kuodra.kr-local-stock.v1",
            "status":"LOCAL_DESCRIPTIVE_UNVERIFIED" if beta is not None else "INSUFFICIENT_VARIANCE",
            "ticker":ticker,"benchmark":benchmark,"as_of":as_of,
            "period_start":dates[0].isoformat(),"period_end":dates[-1].isoformat(),
            "observations":len(dates),**result,
            "original_sha256":sha256(raw).hexdigest(),
            "source_authenticated":False,"source_rights_verified":False,
            "external_sharing_allowed":False,"full_a_b_c_ready":False,
            "market_bubble_proven":False,"guard_policy_preview":"HOLD",
            "network_requests":0}
