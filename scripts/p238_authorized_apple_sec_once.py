"""P238 Apple SEC direct GET: owner-initiated exact consent only.

Never used in CI; P105 blocked NVDA target remains forbidden.
"""
from __future__ import annotations
import getpass
import json
import sys

from proofinvest.sec_apple_2026_authorized_once import (
    _APPROVAL,_failure,read_apple_2026_sec_original_once,validate_owner_contact,
)


def main() -> int:
    if len(sys.argv)!=1:
        print(json.dumps(_failure("NO_ARGUMENTS_ACCEPTED"),sort_keys=True))
        return 2
    if not sys.stdin.isatty():
        print(json.dumps(_failure("INTERACTIVE_LOCAL_TERMINAL_REQUIRED"),
                         sort_keys=True))
        return 2
    print("APPLE FY2026: ONE SEC HTTPS GET, no proxy, redirect, retry or raw save.")
    print("403/429 => STOP. This does NOT retry the prior blocked NVDA endpoint.")
    try:
        typed=input("One-time authorization: type "+_APPROVAL+": ").strip()
    except (EOFError,KeyboardInterrupt):
        typed=""
    if typed!=_APPROVAL:
        print(json.dumps(_failure("EXPLICIT_OWNER_APPROVAL_REQUIRED"),sort_keys=True))
        return 2
    try:
        contact=getpass.getpass("Real SEC contact email (hidden, no save): ").strip()
    except (EOFError,KeyboardInterrupt,OSError):
        contact=""
    ua=validate_owner_contact(contact)
    contact=""
    if ua is None:
        print(json.dumps(_failure("REACHABLE_SEC_CONTACT_REQUIRED"),sort_keys=True))
        return 2
    result=read_apple_2026_sec_original_once(authorized=True,user_agent=ua)
    ua=""
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False))
    return 0 if result["status"]=="SEC_DIRECT_HTTPS_APPLE_2026_SIX_FACTS_OBSERVED" else 2


if __name__=="__main__":
    raise SystemExit(main())
