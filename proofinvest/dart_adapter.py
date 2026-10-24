"""OPENDART read-only adapter. Live call requires explicit --live and environment key."""
import json,os,re
from urllib.parse import urlencode
from urllib.request import urlopen

API_BASE="https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"

def fetch_major_accounts(corp_code:str,year:int,api_key:str|None=None)->list[dict]:
    key=api_key or os.environ.get("OPENDART_API_KEY")
    if not key:raise RuntimeError("OPENDART_API_KEY missing; live request not executed")
    if not re.fullmatch(r"\d{8}",corp_code):raise ValueError("corp_code must be 8 digits")
    if year<2015 or year>2100:raise ValueError("invalid business year")
    url=API_BASE+"?"+urlencode({"crtfc_key":key,"corp_code":corp_code,"bsns_year":year,"reprt_code":"11011"})
    # Credential-bearing URL is never logged, returned or persisted.
    try:
        with urlopen(url,timeout=12) as resp: result=json.load(resp)
    except Exception:
        raise RuntimeError("OpenDART request failed; details intentionally suppressed to avoid key leakage") from None
    if result.get("status")!="000":
        raise RuntimeError(f"OpenDART returned non-success status {str(result.get('status','unknown'))[:5]}")
    if not isinstance(result.get("list"),list):raise RuntimeError("Malformed OpenDART payload")
    return result["list"]
