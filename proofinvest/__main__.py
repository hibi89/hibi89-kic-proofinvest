"""CLI: safe synthetic demo by default, explicit opt-in for actual API."""
import argparse,json
from pathlib import Path
from .engine import calculate
from .dart_adapter import fetch_major_accounts

def main():
    p=argparse.ArgumentParser(description="ProofInvest evidence-first research prototype")
    p.add_argument("--live",action="store_true",help="Explicitly request live OpenDART data")
    p.add_argument("--corp-code",help="8-digit OpenDART company code")
    p.add_argument("--year",type=int,default=2024)
    p.add_argument("--claim-revenue-growth-pct",default=None)
    args=p.parse_args()
    if args.live:
        if not args.corp_code:p.error("--live requires --corp-code")
        rows=fetch_major_accounts(args.corp_code,args.year)
        is_demo=False
    else:
        rows=json.loads((Path(__file__).parent.parent/"fixtures"/"synthetic_annual.json").read_text(encoding="utf-8"))
        is_demo=True
    print(json.dumps(calculate(rows,args.year,args.claim_revenue_growth_pct,is_demo),ensure_ascii=False,indent=2))
if __name__=="__main__":main()
